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

  // Check API health on component mount
  useEffect(() => {
    checkApiHealth();
    // Set up periodic task status checking
    const interval = setInterval(updateAllTaskStatuses, 2000);
    return () => clearInterval(interval);
  }, []);

  const checkApiHealth = async () => {
    try {
      const response = await axios.get(`${API_BASE_URL}/health`);
      setApiStatus(response.data.status === 'healthy' ? 'healthy' : 'unhealthy');
    } catch (error) {
      setApiStatus('unhealthy');
      console.error('API health check failed:', error);
    }
  };

  const updateAllTaskStatuses = async () => {
    const taskIds = Object.keys(tasks);
    if (taskIds.length === 0) return;

    for (const taskId of taskIds) {
      if (tasks[taskId]?.status === 'completed' || tasks[taskId]?.status === 'failed') {
        continue; // Skip already finished tasks
      }
      
      try {
        const response = await axios.get(`${API_BASE_URL}/tasks/${taskId}`);
        setTasks(prev => ({
          ...prev,
          [taskId]: response.data
        }));
      } catch (error) {
        console.error(`Error updating task ${taskId}:`, error);
      }
    }
  };

  const downloadResults = async (taskId) => {
    try {
      const response = await axios.get(`${API_BASE_URL}/download/${taskId}`, {
        responseType: 'blob'
      });
      
      const blob = new Blob([response.data]);
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `results_${taskId}.zip`;
      document.body.appendChild(link);
      link.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(link);
    } catch (error) {
      console.error('Download failed:', error);
      alert('Download failed: ' + error.message);
    }
  };

  const cleanupTask = async (taskId) => {
    try {
      await axios.delete(`${API_BASE_URL}/tasks/${taskId}`);
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
          <PPTXTranslationTester tasks={tasks} setTasks={setTasks} />
          <TextTranslationTester tasks={tasks} setTasks={setTasks} />
          <AudioTranscriptionTester tasks={tasks} setTasks={setTasks} />
          <PPTXConversionTester tasks={tasks} setTasks={setTasks} />
          <TextToSpeechTester tasks={tasks} setTasks={setTasks} />
        </div>

        <TaskManager 
          tasks={tasks} 
          onDownload={downloadResults}
          onCleanup={cleanupTask}
        />
      </div>
    </div>
  );
}

// PPTX Translation Component
function PPTXTranslationTester({ tasks, setTasks }) {
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

    setIsSubmitting(true);
    const formData = new FormData();
    formData.append('source_lang', sourceLang);
    formData.append('target_lang', targetLang);
    
    files.forEach(file => {
      formData.append('files', file);
    });

    try {
      const response = await axios.post(`${API_BASE_URL}/translate/pptx`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
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
function TextTranslationTester({ tasks, setTasks }) {
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

    setIsSubmitting(true);
    const formData = new FormData();
    formData.append('source_lang', sourceLang);
    formData.append('target_lang', targetLang);
    
    files.forEach(file => {
      formData.append('files', file);
    });

    try {
      const response = await axios.post(`${API_BASE_URL}/translate/text`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
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
function AudioTranscriptionTester({ tasks, setTasks }) {
  const [files, setFiles] = useState([]);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (files.length === 0) {
      alert('Please select audio files');
      return;
    }

    setIsSubmitting(true);
    const formData = new FormData();
    
    files.forEach(file => {
      formData.append('files', file);
    });

    try {
      const response = await axios.post(`${API_BASE_URL}/transcribe/audio`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
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
function PPTXConversionTester({ tasks, setTasks }) {
  const [files, setFiles] = useState([]);
  const [outputFormat, setOutputFormat] = useState('pdf');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (files.length === 0) {
      alert('Please select PPTX files');
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
        headers: { 'Content-Type': 'multipart/form-data' }
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
function TextToSpeechTester({ tasks, setTasks }) {
  const [files, setFiles] = useState([]);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (files.length === 0) {
      alert('Please select TXT files');
      return;
    }

    setIsSubmitting(true);
    const formData = new FormData();
    
    files.forEach(file => {
      formData.append('files', file);
    });

    try {
      const response = await axios.post(`${API_BASE_URL}/tts`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
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
function TaskManager({ tasks, onDownload, onCleanup }) {
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
      {taskArray.map(([taskId, task]) => (
        <div key={taskId} className="task-status">
          <h4>Task: {taskId.substring(0, 8)}...</h4>
          <div>
            <span className={`status-badge status-${task.status}`}>
              {task.status === 'running' && <span className="loading-spinner"></span>}
              {task.status}
            </span>
            {task.status === 'completed' && (
              <button 
                className="btn btn-success" 
                onClick={() => onDownload(taskId)}
              >
                📥 Download Results
              </button>
            )}
            <button 
              className="btn btn-danger" 
              onClick={() => onCleanup(taskId)}
            >
              🗑️ Cleanup
            </button>
          </div>
          
          {task.progress && (
            <div className="progress-log">
              Last update: {task.progress}
            </div>
          )}
          
          {task.error && (
            <div className="error">
              Error: {task.error}
            </div>
          )}
          
          {task.result_files && task.result_files.length > 0 && (
            <div className="success">
              ✅ {task.result_files.length} result file(s) ready for download
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

export default App;