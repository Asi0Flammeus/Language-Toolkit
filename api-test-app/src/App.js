import React, { useState, useEffect } from 'react';
import axios from 'axios';
import './App.css';

// API Configuration
const API_BASE_URL = 'http://localhost:8000';

// Language options for testing
const LANGUAGE_OPTIONS = {
  source_languages: {
    'en': 'English',
    'fr': 'French', 
    'es': 'Spanish',
    'de': 'German',
    'it': 'Italian',
    'pt': 'Portuguese'
  },
  target_languages: {
    'en': 'English',
    'fr': 'French',
    'es': 'Spanish', 
    'de': 'German',
    'it': 'Italian',
    'pt': 'Portuguese'
  }
};

function App() {
  const [apiStatus, setApiStatus] = useState('checking');
  const [tasks, setTasks] = useState({});
  const [authToken, setAuthToken] = useState('token_admin_abc123def456');
  const [authStatus, setAuthStatus] = useState('unchecked');

  // Check API health and auth on component mount
  useEffect(() => {
    checkApiHealth();
    checkAuthentication();
    // Set up periodic task status checking
    const interval = setInterval(updateAllTaskStatuses, 2000);
    return () => clearInterval(interval);
  }, []);

  // Check auth when token changes
  useEffect(() => {
    if (authToken) {
      checkAuthentication();
    }
  }, [authToken]);

  const checkApiHealth = async () => {
    try {
      const response = await axios.get(`${API_BASE_URL}/health`);
      setApiStatus(response.data.status === 'healthy' ? 'healthy' : 'unhealthy');
    } catch (error) {
      setApiStatus('unhealthy');
      console.error('API health check failed:', error);
    }
  };

  const checkAuthentication = async () => {
    if (!authToken.trim()) {
      setAuthStatus('missing');
      return;
    }
    
    try {
      const response = await axios.get(`${API_BASE_URL}/tasks`, {
        headers: {
          'Authorization': `Bearer ${authToken}`
        }
      });
      setAuthStatus('valid');
    } catch (error) {
      if (error.response?.status === 401) {
        setAuthStatus('invalid');
      } else {
        setAuthStatus('error');
      }
      console.error('Authentication check failed:', error);
    }
  };

  const updateAllTaskStatuses = async () => {
    const taskIds = Object.keys(tasks);
    if (taskIds.length === 0 || !authToken) return;

    for (const taskId of taskIds) {
      if (tasks[taskId]?.status === 'completed' || tasks[taskId]?.status === 'failed') {
        continue; // Skip already finished tasks
      }
      
      try {
        console.log(`Checking status for task: ${taskId}`);
        const response = await axios.get(`${API_BASE_URL}/tasks/${taskId}`, {
          headers: {
            'Authorization': `Bearer ${authToken}`
          }
        });
        console.log(`Task ${taskId} status response:`, response.data);
        setTasks(prev => ({
          ...prev,
          [taskId]: response.data
        }));
      } catch (error) {
        console.error(`Error updating task ${taskId}:`, error);
        if (error.response?.status === 404) {
          // Task not found, mark as failed
          setTasks(prev => ({
            ...prev,
            [taskId]: { ...prev[taskId], status: 'failed', error: 'Task not found on server' }
          }));
        }
      }
    }
  };

  const downloadResults = async (taskId, fileIndex = null) => {
    try {
      console.log(`Starting download for task ${taskId}${fileIndex !== null ? `, file ${fileIndex}` : ''}`);
      
      const url = fileIndex !== null 
        ? `${API_BASE_URL}/download/${taskId}/${fileIndex}`
        : `${API_BASE_URL}/download/${taskId}`;
        
      const response = await axios.get(url, {
        responseType: 'blob',
        headers: {
          'Authorization': `Bearer ${authToken}`
        }
      });
      
      console.log('Download response:', response);
      
      if (response.data.size === 0) {
        alert('Download failed: No data received');
        return;
      }
      
      const blob = new Blob([response.data]);
      const downloadUrl = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = downloadUrl;
      
      // Try to get filename from response headers
      const contentDisposition = response.headers['content-disposition'];
      const contentType = response.headers['content-type'] || '';
      
      let filename = `results_${taskId}${fileIndex !== null ? `_file_${fileIndex}` : ''}`;
      
      // First try to get filename from Content-Disposition header
      if (contentDisposition) {
        const filenameMatch = contentDisposition.match(/filename="(.+)"/);
        if (filenameMatch) {
          filename = filenameMatch[1];
        }
      } else {
        // If no Content-Disposition, determine extension from Content-Type
        if (contentType.includes('application/vnd.openxmlformats-officedocument.presentationml.presentation')) {
          filename += '.pptx';
        } else if (contentType.includes('application/pdf')) {
          filename += '.pdf';
        } else if (contentType.includes('text/plain')) {
          filename += '.txt';
        } else if (contentType.includes('audio/mpeg')) {
          filename += '.mp3';
        } else if (contentType.includes('image/png')) {
          filename += '.png';
        } else if (contentType.includes('image/jpeg')) {
          filename += '.jpg';
        } else if (contentType.includes('application/zip')) {
          filename += '.zip';
        } else {
          // Default to zip if unknown
          filename += '.zip';
        }
      }
      
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      window.URL.revokeObjectURL(downloadUrl);
      document.body.removeChild(link);
      
      console.log(`Download completed: ${filename}`);
      
      // Show file type specific success message
      let fileTypeEmoji = "📄";
      let fileTypeDesc = "file";
      
      if (contentType.includes('application/vnd.openxmlformats-officedocument.presentationml.presentation')) {
        fileTypeEmoji = "📊";
        fileTypeDesc = "PPTX presentation";
      } else if (contentType.includes('application/pdf')) {
        fileTypeEmoji = "📕";
        fileTypeDesc = "PDF document";
      } else if (contentType.includes('text/plain')) {
        fileTypeEmoji = "📝";
        fileTypeDesc = "text file";
      } else if (contentType.includes('audio/mpeg')) {
        fileTypeEmoji = "🎵";
        fileTypeDesc = "MP3 audio";
      } else if (contentType.includes('image/png')) {
        fileTypeEmoji = "🖼️";
        fileTypeDesc = "PNG image";
      } else if (contentType.includes('application/zip')) {
        fileTypeEmoji = "📦";
        fileTypeDesc = "ZIP archive";
      }
      
      alert(`✅ ${fileTypeEmoji} Download completed: ${filename}\n📋 Type: ${fileTypeDesc}`);
    } catch (error) {
      console.error('Download failed:', error);
      if (error.response?.status === 404) {
        alert('Download failed: Results not found. The task may still be processing or may have failed.');
      } else if (error.response?.status === 401) {
        alert('Download failed: Authentication required. Please check your token.');
      } else {
        alert('Download failed: ' + (error.response?.data?.detail || error.message));
      }
    }
  };

  const cleanupTask = async (taskId) => {
    try {
      await axios.delete(`${API_BASE_URL}/tasks/${taskId}`, {
        headers: {
          'Authorization': `Bearer ${authToken}`
        }
      });
      setTasks(prev => {
        const newTasks = { ...prev };
        delete newTasks[taskId];
        return newTasks;
      });
    } catch (error) {
      console.error('Cleanup failed:', error);
      alert('Cleanup failed: ' + error.message);
    }
  };

  return (
    <div className="App">
      <div className="container">
        <div className="header">
          <h1>🛠️ Language Toolkit API Tester</h1>
          <p>Test all endpoints of the Language Toolkit API</p>
          
          <div className="auth-section">
            <div className="form-group">
              <label>🔐 Authentication Token:</label>
              <div style={{display: 'flex', gap: '10px', alignItems: 'center'}}>
                <input
                  type="text"
                  value={authToken}
                  onChange={(e) => setAuthToken(e.target.value)}
                  placeholder="Enter your Bearer token"
                  style={{flex: 1, fontFamily: 'monospace', fontSize: '12px'}}
                />
                <button className="btn btn-secondary" onClick={checkAuthentication}>
                  Test Auth
                </button>
              </div>
              <div style={{marginTop: '5px'}}>
                Auth Status: 
                <span className={`status-badge status-${authStatus}`}>
                  {authStatus === 'unchecked' && '❓ Unchecked'}
                  {authStatus === 'valid' && '✅ Valid'}
                  {authStatus === 'invalid' && '❌ Invalid Token'}
                  {authStatus === 'missing' && '⚠️ Missing Token'}
                  {authStatus === 'error' && '🔥 Error'}
                </span>
              </div>
            </div>
          </div>
          
          <div>
            API Status: 
            <span className={`status-badge status-${apiStatus}`}>
              {apiStatus === 'checking' && <span className="loading-spinner"></span>}
              {apiStatus}
            </span>
            <button className="btn btn-secondary" onClick={checkApiHealth} style={{marginLeft: '10px'}}>
              Refresh
            </button>
          </div>
        </div>

        <div className="grid">
          <PPTXTranslationTester tasks={tasks} setTasks={setTasks} authToken={authToken} />
          <TextTranslationTester tasks={tasks} setTasks={setTasks} authToken={authToken} />
          <AudioTranscriptionTester tasks={tasks} setTasks={setTasks} authToken={authToken} />
          <PPTXConversionTester tasks={tasks} setTasks={setTasks} authToken={authToken} />
          <TextToSpeechTester tasks={tasks} setTasks={setTasks} authToken={authToken} />
        </div>

        <TaskManager 
          tasks={tasks} 
          onDownload={downloadResults}
          onCleanup={cleanupTask}
          onRefresh={updateAllTaskStatuses}
        />
      </div>
    </div>
  );
}

// PPTX Translation Component
function PPTXTranslationTester({ tasks, setTasks, authToken }) {
  const [files, setFiles] = useState([]);
  const [sourceLang, setSourceLang] = useState('en');
  const [targetLang, setTargetLang] = useState('fr');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (files.length === 0) {
      alert('Please select PPTX files');
      return;
    }

    if (!authToken) {
      alert('Please enter an authentication token');
      return;
    }

    setIsSubmitting(true);
    const formData = new FormData();
    formData.append('source_lang', sourceLang);
    formData.append('target_lang', targetLang);
    
    files.forEach(file => {
      formData.append('files', file);
    });

    try {
      const response = await axios.post(`${API_BASE_URL}/translate/pptx`, formData, {
        headers: { 
          'Content-Type': 'multipart/form-data',
          'Authorization': `Bearer ${authToken}`
        }
      });
      
      setTasks(prev => ({
        ...prev,
        [response.data.task_id]: response.data
      }));
      
      setFiles([]);
    } catch (error) {
      console.error('PPTX translation failed:', error);
      alert('PPTX translation failed: ' + error.message);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="api-section">
      <h2>📄 PPTX Translation</h2>
      <form onSubmit={handleSubmit}>
        <div className="form-group">
          <label>Source Language:</label>
          <select value={sourceLang} onChange={(e) => setSourceLang(e.target.value)}>
            {Object.entries(LANGUAGE_OPTIONS.source_languages).map(([code, name]) => (
              <option key={code} value={code}>{code} - {name}</option>
            ))}
          </select>
        </div>

        <div className="form-group">
          <label>Target Language:</label>
          <select value={targetLang} onChange={(e) => setTargetLang(e.target.value)}>
            {Object.entries(LANGUAGE_OPTIONS.target_languages).map(([code, name]) => (
              <option key={code} value={code}>{code} - {name}</option>
            ))}
          </select>
        </div>

        <FileUploader 
          files={files}
          setFiles={setFiles}
          accept=".pptx"
          multiple={true}
          label="Select PPTX files (use ECO102-FR-V001-2.1.pptx or btc204-v001-1.1.pptx from test-app folder)"
        />

        <button type="submit" className="btn" disabled={isSubmitting}>
          {isSubmitting && <span className="loading-spinner"></span>}
          Translate PPTX
        </button>
      </form>
    </div>
  );
}

// Text Translation Component
function TextTranslationTester({ tasks, setTasks, authToken }) {
  const [files, setFiles] = useState([]);
  const [sourceLang, setSourceLang] = useState('en');
  const [targetLang, setTargetLang] = useState('fr');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (files.length === 0) {
      alert('Please select TXT files');
      return;
    }

    if (!authToken) {
      alert('Please enter an authentication token');
      return;
    }

    setIsSubmitting(true);
    const formData = new FormData();
    formData.append('source_lang', sourceLang);
    formData.append('target_lang', targetLang);
    
    files.forEach(file => {
      formData.append('files', file);
    });

    try {
      const response = await axios.post(`${API_BASE_URL}/translate/text`, formData, {
        headers: { 
          'Content-Type': 'multipart/form-data',
          'Authorization': `Bearer ${authToken}`
        }
      });
      
      setTasks(prev => ({
        ...prev,
        [response.data.task_id]: response.data
      }));
      
      setFiles([]);
    } catch (error) {
      console.error('Text translation failed:', error);
      alert('Text translation failed: ' + error.message);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="api-section">
      <h2>📝 Text Translation</h2>
      <form onSubmit={handleSubmit}>
        <div className="form-group">
          <label>Source Language:</label>
          <select value={sourceLang} onChange={(e) => setSourceLang(e.target.value)}>
            {Object.entries(LANGUAGE_OPTIONS.source_languages).map(([code, name]) => (
              <option key={code} value={code}>{code} - {name}</option>
            ))}
          </select>
        </div>

        <div className="form-group">
          <label>Target Language:</label>
          <select value={targetLang} onChange={(e) => setTargetLang(e.target.value)}>
            {Object.entries(LANGUAGE_OPTIONS.target_languages).map(([code, name]) => (
              <option key={code} value={code}>{code} - {name}</option>
            ))}
          </select>
        </div>

        <FileUploader 
          files={files}
          setFiles={setFiles}
          accept=".txt"
          multiple={true}
          label="Select TXT files (use .txt files from test-app/btc204/ folder)"
        />

        <button type="submit" className="btn" disabled={isSubmitting}>
          {isSubmitting && <span className="loading-spinner"></span>}
          Translate Text
        </button>
      </form>
    </div>
  );
}

// Audio Transcription Component
function AudioTranscriptionTester({ tasks, setTasks, authToken }) {
  const [files, setFiles] = useState([]);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (files.length === 0) {
      alert('Please select audio files');
      return;
    }

    if (!authToken) {
      alert('Please enter an authentication token');
      return;
    }

    setIsSubmitting(true);
    const formData = new FormData();
    
    files.forEach(file => {
      formData.append('files', file);
    });

    try {
      const response = await axios.post(`${API_BASE_URL}/transcribe/audio`, formData, {
        headers: { 
          'Content-Type': 'multipart/form-data',
          'Authorization': `Bearer ${authToken}`
        }
      });
      
      setTasks(prev => ({
        ...prev,
        [response.data.task_id]: response.data
      }));
      
      setFiles([]);
    } catch (error) {
      console.error('Audio transcription failed:', error);
      alert('Audio transcription failed: ' + error.message);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="api-section">
      <h2>🎵 Audio Transcription</h2>
      <form onSubmit={handleSubmit}>
        <FileUploader 
          files={files}
          setFiles={setFiles}
          accept=".mp3,.wav,.m4a,.webm,.mp4,.mpga,.mpeg"
          multiple={true}
          label="Select audio files (use .mp3 files from test-app/btc204/ or test_Loic.mp3)"
        />

        <button type="submit" className="btn" disabled={isSubmitting}>
          {isSubmitting && <span className="loading-spinner"></span>}
          Transcribe Audio
        </button>
      </form>
    </div>
  );
}

// PPTX Conversion Component
function PPTXConversionTester({ tasks, setTasks, authToken }) {
  const [files, setFiles] = useState([]);
  const [outputFormat, setOutputFormat] = useState('pdf');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (files.length === 0) {
      alert('Please select PPTX files');
      return;
    }

    if (!authToken) {
      alert('Please enter an authentication token');
      return;
    }

    setIsSubmitting(true);
    const formData = new FormData();
    formData.append('output_format', outputFormat);
    
    files.forEach(file => {
      formData.append('files', file);
    });

    try {
      const response = await axios.post(`${API_BASE_URL}/convert/pptx`, formData, {
        headers: { 
          'Content-Type': 'multipart/form-data',
          'Authorization': `Bearer ${authToken}`
        }
      });
      
      setTasks(prev => ({
        ...prev,
        [response.data.task_id]: response.data
      }));
      
      setFiles([]);
    } catch (error) {
      console.error('PPTX conversion failed:', error);
      alert('PPTX conversion failed: ' + error.message);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="api-section">
      <h2>🔄 PPTX Conversion</h2>
      <form onSubmit={handleSubmit}>
        <div className="form-group">
          <label>Output Format:</label>
          <select value={outputFormat} onChange={(e) => setOutputFormat(e.target.value)}>
            <option value="pdf">PDF</option>
            <option value="png">PNG (one per slide)</option>
          </select>
        </div>

        <FileUploader 
          files={files}
          setFiles={setFiles}
          accept=".pptx"
          multiple={true}
          label="Select PPTX files to convert"
        />

        <button type="submit" className="btn" disabled={isSubmitting}>
          {isSubmitting && <span className="loading-spinner"></span>}
          Convert PPTX
        </button>
      </form>
    </div>
  );
}

// Text to Speech Component
function TextToSpeechTester({ tasks, setTasks, authToken }) {
  const [files, setFiles] = useState([]);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (files.length === 0) {
      alert('Please select TXT files');
      return;
    }

    if (!authToken) {
      alert('Please enter an authentication token');
      return;
    }

    setIsSubmitting(true);
    const formData = new FormData();
    
    files.forEach(file => {
      formData.append('files', file);
    });

    try {
      const response = await axios.post(`${API_BASE_URL}/tts`, formData, {
        headers: { 
          'Content-Type': 'multipart/form-data',
          'Authorization': `Bearer ${authToken}`
        }
      });
      
      setTasks(prev => ({
        ...prev,
        [response.data.task_id]: response.data
      }));
      
      setFiles([]);
    } catch (error) {
      console.error('Text to speech failed:', error);
      alert('Text to speech failed: ' + error.message);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="api-section">
      <h2>🎤 Text to Speech</h2>
      <form onSubmit={handleSubmit}>
        <FileUploader 
          files={files}
          setFiles={setFiles}
          accept=".txt"
          multiple={true}
          label="Select TXT files (filename must contain voice name like 'Loic')"
        />

        <button type="submit" className="btn" disabled={isSubmitting}>
          {isSubmitting && <span className="loading-spinner"></span>}
          Convert to Speech
        </button>
      </form>
    </div>
  );
}

// File Upload Component
function FileUploader({ files, setFiles, accept, multiple, label }) {
  const [dragOver, setDragOver] = useState(false);

  const handleDrop = (e) => {
    e.preventDefault();
    setDragOver(false);
    const droppedFiles = Array.from(e.dataTransfer.files);
    if (multiple) {
      setFiles(prev => [...prev, ...droppedFiles]);
    } else {
      setFiles(droppedFiles.slice(0, 1));
    }
  };

  const handleFileSelect = (e) => {
    const selectedFiles = Array.from(e.target.files);
    if (multiple) {
      setFiles(prev => [...prev, ...selectedFiles]);
    } else {
      setFiles(selectedFiles);
    }
  };

  const removeFile = (index) => {
    setFiles(prev => prev.filter((_, i) => i !== index));
  };

  const formatFileSize = (bytes) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  return (
    <div className="form-group">
      <label>{label}</label>
      <div 
        className={`file-input ${dragOver ? 'drag-over' : ''}`}
        onDrop={handleDrop}
        onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onClick={() => document.getElementById('fileInput').click()}
      >
        <p>📁 Click to select files or drag and drop</p>
        <p style={{fontSize: '12px', color: '#666'}}>Accepted: {accept}</p>
      </div>
      <input
        id="fileInput"
        type="file"
        accept={accept}
        multiple={multiple}
        onChange={handleFileSelect}
        style={{ display: 'none' }}
      />
      
      {files.length > 0 && (
        <div className="file-list">
          {files.map((file, index) => (
            <div key={index} className="file-item">
              <div>
                <div className="file-name">{file.name}</div>
                <div className="file-size">{formatFileSize(file.size)}</div>
              </div>
              <button 
                type="button" 
                className="btn btn-danger"
                onClick={() => removeFile(index)}
                style={{padding: '4px 8px', fontSize: '12px'}}
              >
                Remove
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// Task Manager Component
function TaskManager({ tasks, onDownload, onCleanup, onRefresh }) {
  const taskArray = Object.entries(tasks);

  if (taskArray.length === 0) {
    return (
      <div className="api-section">
        <h2>📋 Task Manager</h2>
        <p>No active tasks. Submit a processing request above to see task status here.</p>
      </div>
    );
  }

  return (
    <div className="api-section">
      <h2>📋 Task Manager</h2>
      {taskArray.length > 0 && (
        <button 
          className="btn btn-secondary" 
          onClick={onRefresh}
          style={{marginBottom: '15px'}}
        >
          🔄 Refresh Task Status
        </button>
      )}
      {taskArray.map(([taskId, task]) => (
        <div key={taskId} className="task-status">
          <h4>Task: {taskId.substring(0, 8)}...</h4>
          <div style={{marginBottom: '10px'}}>
            <span className={`status-badge status-${task.status}`}>
              {task.status === 'running' && <span className="loading-spinner"></span>}
              {task.status}
            </span>
            {task.status === 'completed' && (
              <button 
                className="btn btn-success" 
                onClick={() => onDownload(taskId)}
                style={{marginLeft: '10px'}}
              >
                📥 Download Results
              </button>
            )}
            <button 
              className="btn btn-danger" 
              onClick={() => onCleanup(taskId)}
              style={{marginLeft: '10px'}}
            >
              🗑️ Cleanup
            </button>
          </div>
          
          {/* Debug: Show raw task data */}
          <details style={{marginBottom: '10px', fontSize: '12px'}}>
            <summary>🔍 Debug Info</summary>
            <div style={{background: '#f8f9fa', padding: '5px', borderRadius: '3px', overflow: 'auto'}}>
              <div><strong>Status:</strong> {task.status}</div>
              <div><strong>Result files count:</strong> {task.result_files ? task.result_files.length : 0}</div>
              <div><strong>Result files:</strong></div>
              <pre style={{fontSize: '10px', margin: '5px 0'}}>
                {JSON.stringify(task.result_files, null, 2)}
              </pre>
              <div><strong>Full task data:</strong></div>
              <pre style={{fontSize: '10px', margin: '5px 0'}}>
                {JSON.stringify(task, null, 2)}
              </pre>
            </div>
          </details>
          
          {task.progress && (
            <div className="progress-log">
              Last update: {task.progress}
            </div>
          )}
          
          {task.error && (
            <div className="error" style={{color: 'red', background: '#ffe6e6', padding: '5px', borderRadius: '3px'}}>
              Error: {task.error}
            </div>
          )}
          
          {task.result_files && task.result_files.length > 0 && (
            <div className="success" style={{color: 'green', background: '#e6ffe6', padding: '5px', borderRadius: '3px'}}>
              ✅ {task.result_files.length} result file(s) ready for download
              
              {task.result_files.length === 1 ? (
                // Single file - show simplified display
                <div style={{margin: '5px 0'}}>
                  <strong>{task.result_files[0].split('/').pop()}</strong>
                </div>
              ) : (
                // Multiple files - show list with individual download buttons
                <ul style={{margin: '5px 0', paddingLeft: '20px', listStyle: 'none'}}>
                  {task.result_files.map((file, index) => (
                    <li key={index} style={{fontSize: '11px', fontFamily: 'monospace', marginBottom: '5px', display: 'flex', alignItems: 'center', justifyContent: 'space-between'}}>
                      <span>{file.split('/').pop()}</span>
                      <button 
                        className="btn btn-success" 
                        onClick={() => onDownload(taskId, index)}
                        style={{padding: '2px 6px', fontSize: '10px', marginLeft: '10px'}}
                      >
                        📥 Download
                      </button>
                    </li>
                  ))}
                </ul>
              )}
              
              {task.result_files.length > 1 && (
                <div style={{marginTop: '10px', textAlign: 'center'}}>
                  <button 
                    className="btn btn-success" 
                    onClick={() => onDownload(taskId)}
                    style={{fontSize: '12px'}}
                  >
                    📦 Download All as ZIP
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

export default App;