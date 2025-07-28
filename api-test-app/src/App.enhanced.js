import React, { useState, useEffect } from 'react';
import axios from 'axios';
import './App.css';

// API Configuration
const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

// Language options for testing
const LANGUAGE_OPTIONS = {
  source_languages: {
    'en': 'English',
    'fr': 'French', 
    'es': 'Spanish',
    'de': 'German',
    'it': 'Italian',
    'pt': 'Portuguese',
    'nl': 'Dutch',
    'ja': 'Japanese',
    'zh': 'Chinese',
    'ru': 'Russian'
  },
  target_languages: {
    'en': 'English',
    'fr': 'French',
    'es': 'Spanish', 
    'de': 'German',
    'it': 'Italian',
    'pt': 'Portuguese',
    'nl': 'Dutch',
    'ja': 'Japanese',
    'zh': 'Chinese',
    'ru': 'Russian'
  }
};

// Known ElevenLabs voices from elevenlabs_voices.json
const ELEVENLABS_VOICES = {
  "DavidStOnge": "0PfKe742JfrBvOr7Gyx9",
  "Fanis": "HIRH46f2SFLDptj86kJG",
  "Rogzy": "RmicS1jU3ei6Vxlpkqj4",
  "Renaud": "UVJB9VPhLrNHNsH4ZatL",
  "Giacomo": "gFpPxLJAJCez7afCJ8Pd",
  "Loic": "hOYgbRZsrkPHWJ2kdEIu",
  "TheoMogenet": "ld8UrJoCOHSibD1DlYXB",
  "TheoPantamis": "naFOP0Eb03OaLMVhdCxd"
};

// API Endpoints documentation
const API_ENDPOINTS = [
  { method: 'GET', path: '/health', desc: 'Health check', auth: false },
  { method: 'GET', path: '/docs', desc: 'API documentation', auth: false },
  { method: 'GET', path: '/tasks', desc: 'List all tasks', auth: true },
  { method: 'GET', path: '/tasks/{task_id}', desc: 'Get task status', auth: true },
  { method: 'DELETE', path: '/tasks/{task_id}', desc: 'Delete task', auth: true },
  { method: 'POST', path: '/translate/pptx', desc: 'Translate PPTX files', auth: true },
  { method: 'POST', path: '/translate/text', desc: 'Translate text files', auth: true },
  { method: 'POST', path: '/transcribe/audio', desc: 'Transcribe audio files', auth: true },
  { method: 'POST', path: '/convert/pptx', desc: 'Convert PPTX to PDF/PNG', auth: true },
  { method: 'POST', path: '/tts', desc: 'Text to speech conversion', auth: true },
  { method: 'GET', path: '/download/{task_id}', desc: 'Download results', auth: true },
  { method: 'GET', path: '/download/{task_id}/{file_index}', desc: 'Download specific file', auth: true }
];

function App() {
  const [apiStatus, setApiStatus] = useState('checking');
  const [tasks, setTasks] = useState({});
  const [authToken, setAuthToken] = useState('token_admin_abc123def456');
  const [authStatus, setAuthStatus] = useState('unchecked');
  const [activeTab, setActiveTab] = useState('tools');
  const [requestLog, setRequestLog] = useState([]);
  const [showRawRequests, setShowRawRequests] = useState(false);

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

  // Intercept axios requests/responses for logging
  useEffect(() => {
    // Request interceptor
    const requestInterceptor = axios.interceptors.request.use(
      (config) => {
        if (showRawRequests) {
          const logEntry = {
            id: Date.now(),
            type: 'request',
            method: config.method.toUpperCase(),
            url: config.url,
            headers: config.headers,
            data: config.data,
            timestamp: new Date().toISOString()
          };
          setRequestLog(prev => [logEntry, ...prev].slice(0, 50)); // Keep last 50 entries
        }
        return config;
      },
      (error) => Promise.reject(error)
    );

    // Response interceptor
    const responseInterceptor = axios.interceptors.response.use(
      (response) => {
        if (showRawRequests) {
          const logEntry = {
            id: Date.now(),
            type: 'response',
            status: response.status,
            statusText: response.statusText,
            url: response.config.url,
            data: response.data,
            headers: response.headers,
            timestamp: new Date().toISOString()
          };
          setRequestLog(prev => [logEntry, ...prev].slice(0, 50));
        }
        return response;
      },
      (error) => {
        if (showRawRequests && error.response) {
          const logEntry = {
            id: Date.now(),
            type: 'error',
            status: error.response.status,
            statusText: error.response.statusText,
            url: error.config.url,
            data: error.response.data,
            timestamp: new Date().toISOString()
          };
          setRequestLog(prev => [logEntry, ...prev].slice(0, 50));
        }
        return Promise.reject(error);
      }
    );

    return () => {
      axios.interceptors.request.eject(requestInterceptor);
      axios.interceptors.response.eject(responseInterceptor);
    };
  }, [showRawRequests]);

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
        const response = await axios.get(`${API_BASE_URL}/tasks/${taskId}`, {
          headers: {
            'Authorization': `Bearer ${authToken}`
          }
        });
        setTasks(prev => ({
          ...prev,
          [taskId]: response.data
        }));
      } catch (error) {
        console.error(`Error updating task ${taskId}:`, error);
        if (error.response?.status === 404) {
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
      const url = fileIndex !== null 
        ? `${API_BASE_URL}/download/${taskId}/${fileIndex}`
        : `${API_BASE_URL}/download/${taskId}`;
        
      const response = await axios.get(url, {
        responseType: 'blob',
        headers: {
          'Authorization': `Bearer ${authToken}`
        }
      });
      
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
        const extensionMap = {
          'application/vnd.openxmlformats-officedocument.presentationml.presentation': '.pptx',
          'application/pdf': '.pdf',
          'text/plain': '.txt',
          'audio/mpeg': '.mp3',
          'image/png': '.png',
          'image/jpeg': '.jpg',
          'image/webp': '.webp',
          'application/zip': '.zip'
        };
        
        for (const [mimeType, ext] of Object.entries(extensionMap)) {
          if (contentType.includes(mimeType)) {
            filename += ext;
            break;
          }
        }
        
        if (!filename.includes('.')) {
          filename += '.zip'; // Default to zip if unknown
        }
      }
      
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      window.URL.revokeObjectURL(downloadUrl);
      document.body.removeChild(link);
      
      console.log(`Download completed: ${filename}`);
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

  const createTestFile = (content, filename) => {
    const blob = new Blob([content], { type: 'text/plain' });
    const file = new File([blob], filename, { type: 'text/plain' });
    return file;
  };

  return (
    <div className="App">
      <div className="container">
        <div className="header">
          <h1>🛠️ Language Toolkit API Tester</h1>
          <p>Enhanced testing interface for Language Toolkit API</p>
          
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
          
          <div style={{marginTop: '10px', display: 'flex', justifyContent: 'space-between', alignItems: 'center'}}>
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
            
            <div style={{display: 'flex', gap: '10px'}}>
              <label style={{fontSize: '14px'}}>
                <input
                  type="checkbox"
                  checked={showRawRequests}
                  onChange={(e) => setShowRawRequests(e.target.checked)}
                  style={{marginRight: '5px'}}
                />
                Show Raw Requests
              </label>
            </div>
          </div>
        </div>

        <div className="tabs" style={{marginTop: '20px', marginBottom: '20px'}}>
          <button 
            className={`tab ${activeTab === 'tools' ? 'active' : ''}`}
            onClick={() => setActiveTab('tools')}
          >
            🛠️ API Tools
          </button>
          <button 
            className={`tab ${activeTab === 'endpoints' ? 'active' : ''}`}
            onClick={() => setActiveTab('endpoints')}
          >
            📚 Endpoints
          </button>
          <button 
            className={`tab ${activeTab === 'voices' ? 'active' : ''}`}
            onClick={() => setActiveTab('voices')}
          >
            🎤 Voices
          </button>
          <button 
            className={`tab ${activeTab === 'test-data' ? 'active' : ''}`}
            onClick={() => setActiveTab('test-data')}
          >
            🧪 Test Data
          </button>
          <button 
            className={`tab ${activeTab === 'config' ? 'active' : ''}`}
            onClick={() => setActiveTab('config')}
          >
            ⚙️ Config
          </button>
        </div>

        {activeTab === 'tools' && (
          <>
            <div className="grid">
              <PPTXTranslationTester tasks={tasks} setTasks={setTasks} authToken={authToken} />
              <TextTranslationTester tasks={tasks} setTasks={setTasks} authToken={authToken} />
              <AudioTranscriptionTester tasks={tasks} setTasks={setTasks} authToken={authToken} />
              <PPTXConversionTester tasks={tasks} setTasks={setTasks} authToken={authToken} />
              <TextToSpeechTester tasks={tasks} setTasks={setTasks} authToken={authToken} />
              <BatchOperationsTester tasks={tasks} setTasks={setTasks} authToken={authToken} />
            </div>

            <TaskManager 
              tasks={tasks} 
              onDownload={downloadResults}
              onCleanup={cleanupTask}
              onRefresh={updateAllTaskStatuses}
            />
          </>
        )}

        {activeTab === 'endpoints' && <EndpointsViewer />}
        {activeTab === 'voices' && <VoicesViewer />}
        {activeTab === 'test-data' && <TestDataGenerator />}
        {activeTab === 'config' && <ConfigPanel />}

        {showRawRequests && (
          <RequestLogViewer 
            requestLog={requestLog} 
            onClear={() => setRequestLog([])}
          />
        )}
      </div>
    </div>
  );
}

// New component: Batch Operations Tester
function BatchOperationsTester({ tasks, setTasks, authToken }) {
  const [operations, setOperations] = useState([]);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const addOperation = (type) => {
    const newOp = {
      id: Date.now(),
      type,
      files: [],
      params: {
        sourceLang: 'en',
        targetLang: 'fr',
        outputFormat: 'pdf'
      }
    };
    setOperations([...operations, newOp]);
  };

  const removeOperation = (id) => {
    setOperations(operations.filter(op => op.id !== id));
  };

  const updateOperation = (id, updates) => {
    setOperations(operations.map(op => 
      op.id === id ? { ...op, ...updates } : op
    ));
  };

  const executeBatch = async () => {
    setIsSubmitting(true);
    
    for (const op of operations) {
      if (op.files.length === 0) continue;
      
      const formData = new FormData();
      op.files.forEach(file => formData.append('files', file));
      
      let endpoint = '';
      switch (op.type) {
        case 'translate-pptx':
          endpoint = '/translate/pptx';
          formData.append('source_lang', op.params.sourceLang);
          formData.append('target_lang', op.params.targetLang);
          break;
        case 'translate-text':
          endpoint = '/translate/text';
          formData.append('source_lang', op.params.sourceLang);
          formData.append('target_lang', op.params.targetLang);
          break;
        case 'transcribe':
          endpoint = '/transcribe/audio';
          break;
        case 'convert':
          endpoint = '/convert/pptx';
          formData.append('output_format', op.params.outputFormat);
          break;
        case 'tts':
          endpoint = '/tts';
          break;
        default:
          continue;
      }
      
      try {
        const response = await axios.post(`${API_BASE_URL}${endpoint}`, formData, {
          headers: { 
            'Content-Type': 'multipart/form-data',
            'Authorization': `Bearer ${authToken}`
          }
        });
        
        setTasks(prev => ({
          ...prev,
          [response.data.task_id]: response.data
        }));
      } catch (error) {
        console.error(`Batch operation failed for ${op.type}:`, error);
      }
    }
    
    setOperations([]);
    setIsSubmitting(false);
  };

  return (
    <div className="api-section">
      <h2>🚀 Batch Operations</h2>
      <p>Queue multiple operations and execute them all at once</p>
      
      <div style={{marginBottom: '15px'}}>
        <button onClick={() => addOperation('translate-pptx')} className="btn btn-secondary">+ PPTX Translation</button>
        <button onClick={() => addOperation('translate-text')} className="btn btn-secondary">+ Text Translation</button>
        <button onClick={() => addOperation('transcribe')} className="btn btn-secondary">+ Transcription</button>
        <button onClick={() => addOperation('convert')} className="btn btn-secondary">+ Conversion</button>
        <button onClick={() => addOperation('tts')} className="btn btn-secondary">+ Text to Speech</button>
      </div>
      
      {operations.map(op => (
        <div key={op.id} style={{border: '1px solid #ddd', padding: '10px', marginBottom: '10px', borderRadius: '5px'}}>
          <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px'}}>
            <h4>{op.type.replace('-', ' ').toUpperCase()}</h4>
            <button 
              onClick={() => removeOperation(op.id)}
              className="btn btn-danger"
              style={{padding: '4px 8px', fontSize: '12px'}}
            >
              Remove
            </button>
          </div>
          
          {(op.type === 'translate-pptx' || op.type === 'translate-text') && (
            <div style={{display: 'flex', gap: '10px', marginBottom: '10px'}}>
              <select 
                value={op.params.sourceLang} 
                onChange={(e) => updateOperation(op.id, { params: { ...op.params, sourceLang: e.target.value }})}
              >
                {Object.entries(LANGUAGE_OPTIONS.source_languages).map(([code, name]) => (
                  <option key={code} value={code}>{code} - {name}</option>
                ))}
              </select>
              <span>→</span>
              <select 
                value={op.params.targetLang} 
                onChange={(e) => updateOperation(op.id, { params: { ...op.params, targetLang: e.target.value }})}
              >
                {Object.entries(LANGUAGE_OPTIONS.target_languages).map(([code, name]) => (
                  <option key={code} value={code}>{code} - {name}</option>
                ))}
              </select>
            </div>
          )}
          
          {op.type === 'convert' && (
            <div style={{marginBottom: '10px'}}>
              <select 
                value={op.params.outputFormat} 
                onChange={(e) => updateOperation(op.id, { params: { ...op.params, outputFormat: e.target.value }})}
              >
                <option value="pdf">PDF</option>
                <option value="png">PNG</option>
                <option value="webp">WEBP</option>
              </select>
            </div>
          )}
          
          <input
            type="file"
            multiple
            onChange={(e) => updateOperation(op.id, { files: Array.from(e.target.files) })}
            accept={
              op.type === 'translate-pptx' || op.type === 'convert' ? '.pptx' :
              op.type === 'translate-text' || op.type === 'tts' ? '.txt' :
              op.type === 'transcribe' ? '.mp3,.wav,.m4a' : ''
            }
          />
          
          {op.files.length > 0 && (
            <div style={{marginTop: '5px', fontSize: '12px', color: '#666'}}>
              {op.files.length} file(s) selected
            </div>
          )}
        </div>
      ))}
      
      {operations.length > 0 && (
        <button 
          onClick={executeBatch} 
          className="btn btn-primary"
          disabled={isSubmitting || operations.every(op => op.files.length === 0)}
        >
          {isSubmitting && <span className="loading-spinner"></span>}
          Execute All Operations ({operations.length})
        </button>
      )}
    </div>
  );
}

// New component: Endpoints Viewer
function EndpointsViewer() {
  return (
    <div className="api-section">
      <h2>📚 API Endpoints Reference</h2>
      <table style={{width: '100%', borderCollapse: 'collapse'}}>
        <thead>
          <tr style={{borderBottom: '2px solid #ddd'}}>
            <th style={{textAlign: 'left', padding: '10px'}}>Method</th>
            <th style={{textAlign: 'left', padding: '10px'}}>Path</th>
            <th style={{textAlign: 'left', padding: '10px'}}>Description</th>
            <th style={{textAlign: 'center', padding: '10px'}}>Auth</th>
          </tr>
        </thead>
        <tbody>
          {API_ENDPOINTS.map((endpoint, i) => (
            <tr key={i} style={{borderBottom: '1px solid #eee'}}>
              <td style={{padding: '10px'}}>
                <span className={`method-badge method-${endpoint.method.toLowerCase()}`}>
                  {endpoint.method}
                </span>
              </td>
              <td style={{padding: '10px', fontFamily: 'monospace', fontSize: '13px'}}>
                {endpoint.path}
              </td>
              <td style={{padding: '10px', fontSize: '14px'}}>
                {endpoint.desc}
              </td>
              <td style={{padding: '10px', textAlign: 'center'}}>
                {endpoint.auth ? '🔐' : '🌐'}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      
      <div style={{marginTop: '20px', padding: '15px', background: '#f8f9fa', borderRadius: '5px'}}>
        <h3>🔑 Authentication</h3>
        <p>Protected endpoints require a Bearer token in the Authorization header:</p>
        <code style={{display: 'block', padding: '10px', background: '#e9ecef', borderRadius: '3px', marginTop: '10px'}}>
          Authorization: Bearer YOUR_TOKEN_HERE
        </code>
      </div>
      
      <div style={{marginTop: '20px', padding: '15px', background: '#f8f9fa', borderRadius: '5px'}}>
        <h3>📖 Interactive API Documentation</h3>
        <p>Visit the interactive API documentation for detailed endpoint information:</p>
        <a 
          href={`${API_BASE_URL}/docs`} 
          target="_blank" 
          rel="noopener noreferrer"
          className="btn btn-primary"
          style={{marginTop: '10px'}}
        >
          Open Swagger UI →
        </a>
      </div>
    </div>
  );
}

// New component: Voices Viewer
function VoicesViewer() {
  const [apiVoices, setApiVoices] = useState([]);
  const [loading, setLoading] = useState(false);

  const testVoiceNaming = (filename, voiceName) => {
    const parts = filename.split(/[_\-\s]+/);
    return parts.includes(voiceName);
  };

  return (
    <div className="api-section">
      <h2>🎤 ElevenLabs Voice Configuration</h2>
      
      <div style={{marginBottom: '20px'}}>
        <h3>📁 Local Voice Mapping (elevenlabs_voices.json)</h3>
        <p>These voices are configured locally and will be used for text-to-speech:</p>
        
        <table style={{width: '100%', borderCollapse: 'collapse', marginTop: '10px'}}>
          <thead>
            <tr style={{borderBottom: '2px solid #ddd'}}>
              <th style={{textAlign: 'left', padding: '10px'}}>Voice Name</th>
              <th style={{textAlign: 'left', padding: '10px'}}>Voice ID</th>
              <th style={{textAlign: 'left', padding: '10px'}}>Test Filenames</th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(ELEVENLABS_VOICES).map(([name, id]) => (
              <tr key={name} style={{borderBottom: '1px solid #eee'}}>
                <td style={{padding: '10px', fontWeight: 'bold'}}>{name}</td>
                <td style={{padding: '10px', fontFamily: 'monospace', fontSize: '12px'}}>{id}</td>
                <td style={{padding: '10px', fontSize: '12px'}}>
                  <div>✅ test_{name}_transcript.txt</div>
                  <div>✅ story_{name}_english.txt</div>
                  <div>✅ content-{name}-v2.txt</div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      
      <div style={{marginTop: '30px', padding: '15px', background: '#f0f8ff', borderRadius: '5px'}}>
        <h3>💡 Voice Extraction Logic</h3>
        <p>The system extracts voice names from filenames using these rules:</p>
        <ol>
          <li>Splits filename by underscores (_), hyphens (-), and spaces</li>
          <li>Checks each part against the voice mapping (case-insensitive)</li>
          <li>Uses the first matching voice name found</li>
          <li>Falls back to API voices if no local match</li>
        </ol>
        
        <h4>Test Voice Detection:</h4>
        <input 
          type="text" 
          placeholder="Enter a filename to test (e.g., test_Loic_transcript_fr.txt)"
          style={{width: '100%', padding: '8px', marginTop: '10px'}}
          onChange={(e) => {
            const filename = e.target.value;
            if (filename) {
              const parts = filename.split(/[_\-\s]+/);
              const foundVoice = Object.keys(ELEVENLABS_VOICES).find(voice => 
                parts.some(part => part.toLowerCase() === voice.toLowerCase())
              );
              
              if (foundVoice) {
                alert(`✅ Voice detected: ${foundVoice} → ${ELEVENLABS_VOICES[foundVoice]}`);
              } else {
                alert(`❌ No voice found. Parts: ${parts.join(', ')}`);
              }
            }
          }}
        />
      </div>
    </div>
  );
}

// New component: Test Data Generator
function TestDataGenerator() {
  const [generatedFiles, setGeneratedFiles] = useState([]);

  const generateTestFile = (type, voiceName = null) => {
    let content = '';
    let filename = '';
    
    switch (type) {
      case 'simple-text':
        content = `This is a simple test text file.\n\nIt contains multiple lines of text that can be used for testing translation or text-to-speech functionality.\n\nThe quick brown fox jumps over the lazy dog.`;
        filename = 'test_simple.txt';
        break;
        
      case 'voice-text':
        content = `Hello, this is a test for the ${voiceName} voice.\n\nThis text should be converted to speech using the ${voiceName} voice configuration from elevenlabs_voices.json.\n\nTesting multilingual capabilities with different voices.`;
        filename = `test_${voiceName}_content.txt`;
        break;
        
      case 'multilang-text':
        content = `English: Hello world!\nFrench: Bonjour le monde!\nSpanish: ¡Hola mundo!\nGerman: Hallo Welt!\nItalian: Ciao mondo!`;
        filename = 'test_multilingual.txt';
        break;
        
      case 'long-text':
        content = Array(50).fill('Lorem ipsum dolor sit amet, consectetur adipiscing elit. ').join('\n\n');
        filename = 'test_long_content.txt';
        break;
    }
    
    const blob = new Blob([content], { type: 'text/plain' });
    const file = new File([blob], filename, { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    
    setGeneratedFiles(prev => [...prev, { file, url, filename, type }]);
  };

  const downloadFile = (url, filename) => {
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.click();
  };

  return (
    <div className="api-section">
      <h2>🧪 Test Data Generator</h2>
      <p>Generate test files for API testing</p>
      
      <div style={{marginBottom: '20px'}}>
        <h3>📝 Text Files</h3>
        <div style={{display: 'flex', gap: '10px', flexWrap: 'wrap'}}>
          <button 
            onClick={() => generateTestFile('simple-text')}
            className="btn btn-secondary"
          >
            Generate Simple Text
          </button>
          <button 
            onClick={() => generateTestFile('multilang-text')}
            className="btn btn-secondary"
          >
            Generate Multilingual Text
          </button>
          <button 
            onClick={() => generateTestFile('long-text')}
            className="btn btn-secondary"
          >
            Generate Long Text
          </button>
        </div>
      </div>
      
      <div style={{marginBottom: '20px'}}>
        <h3>🎤 Voice-Specific Text Files</h3>
        <div style={{display: 'flex', gap: '10px', flexWrap: 'wrap'}}>
          {Object.keys(ELEVENLABS_VOICES).map(voice => (
            <button 
              key={voice}
              onClick={() => generateTestFile('voice-text', voice)}
              className="btn btn-secondary"
            >
              Generate for {voice}
            </button>
          ))}
        </div>
      </div>
      
      {generatedFiles.length > 0 && (
        <div style={{marginTop: '30px'}}>
          <h3>📁 Generated Files</h3>
          <table style={{width: '100%', borderCollapse: 'collapse'}}>
            <thead>
              <tr style={{borderBottom: '2px solid #ddd'}}>
                <th style={{textAlign: 'left', padding: '10px'}}>Filename</th>
                <th style={{textAlign: 'left', padding: '10px'}}>Type</th>
                <th style={{textAlign: 'right', padding: '10px'}}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {generatedFiles.map((item, i) => (
                <tr key={i} style={{borderBottom: '1px solid #eee'}}>
                  <td style={{padding: '10px', fontFamily: 'monospace'}}>{item.filename}</td>
                  <td style={{padding: '10px'}}>{item.type}</td>
                  <td style={{padding: '10px', textAlign: 'right'}}>
                    <button 
                      onClick={() => downloadFile(item.url, item.filename)}
                      className="btn btn-primary"
                      style={{fontSize: '12px', padding: '4px 8px'}}
                    >
                      Download
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          
          <button 
            onClick={() => {
              generatedFiles.forEach(item => URL.revokeObjectURL(item.url));
              setGeneratedFiles([]);
            }}
            className="btn btn-danger"
            style={{marginTop: '10px'}}
          >
            Clear All
          </button>
        </div>
      )}
      
      <div style={{marginTop: '30px', padding: '15px', background: '#fff3cd', borderRadius: '5px'}}>
        <h3>📌 Test Scenarios</h3>
        <ul>
          <li><strong>Translation Test:</strong> Use simple or multilingual text files</li>
          <li><strong>TTS Voice Test:</strong> Use voice-specific files (e.g., test_Loic_content.txt)</li>
          <li><strong>Audio Transcription:</strong> Use existing MP3 files from test-app folder</li>
          <li><strong>PPTX Operations:</strong> Use existing PPTX files from test-app folder</li>
        </ul>
      </div>
    </div>
  );
}

// New component: Config Panel
function ConfigPanel() {
  const [apiUrl, setApiUrl] = useState(API_BASE_URL);
  const [testTokens, setTestTokens] = useState([
    'token_admin_abc123def456',
    'token_user_xyz789ghi012',
    'invalid_token_test'
  ]);

  return (
    <div className="api-section">
      <h2>⚙️ Configuration</h2>
      
      <div style={{marginBottom: '20px'}}>
        <h3>🌐 API Settings</h3>
        <div className="form-group">
          <label>API Base URL:</label>
          <input
            type="text"
            value={apiUrl}
            onChange={(e) => setApiUrl(e.target.value)}
            style={{fontFamily: 'monospace'}}
          />
          <p style={{fontSize: '12px', color: '#666', marginTop: '5px'}}>
            Current: {API_BASE_URL}
          </p>
        </div>
      </div>
      
      <div style={{marginBottom: '20px'}}>
        <h3>🔑 Test Tokens</h3>
        <p>Quick access to test authentication tokens:</p>
        <div style={{display: 'flex', flexDirection: 'column', gap: '10px', marginTop: '10px'}}>
          {testTokens.map((token, i) => (
            <div key={i} style={{display: 'flex', gap: '10px', alignItems: 'center'}}>
              <code style={{flex: 1, padding: '8px', background: '#f8f9fa', borderRadius: '3px', fontSize: '12px'}}>
                {token}
              </code>
              <button 
                onClick={() => navigator.clipboard.writeText(token)}
                className="btn btn-secondary"
                style={{fontSize: '12px', padding: '4px 8px'}}
              >
                Copy
              </button>
            </div>
          ))}
        </div>
      </div>
      
      <div style={{marginBottom: '20px'}}>
        <h3>📊 Environment Info</h3>
        <table style={{width: '100%', fontSize: '14px'}}>
          <tbody>
            <tr>
              <td style={{padding: '5px', fontWeight: 'bold'}}>React App URL:</td>
              <td style={{padding: '5px', fontFamily: 'monospace'}}>{window.location.origin}</td>
            </tr>
            <tr>
              <td style={{padding: '5px', fontWeight: 'bold'}}>API URL:</td>
              <td style={{padding: '5px', fontFamily: 'monospace'}}>{API_BASE_URL}</td>
            </tr>
            <tr>
              <td style={{padding: '5px', fontWeight: 'bold'}}>User Agent:</td>
              <td style={{padding: '5px', fontSize: '12px'}}>{navigator.userAgent}</td>
            </tr>
          </tbody>
        </table>
      </div>
      
      <div style={{marginTop: '30px', padding: '15px', background: '#e8f5e9', borderRadius: '5px'}}>
        <h3>🚀 Quick Actions</h3>
        <div style={{display: 'flex', gap: '10px', flexWrap: 'wrap'}}>
          <a 
            href={`${API_BASE_URL}/docs`} 
            target="_blank" 
            rel="noopener noreferrer"
            className="btn btn-primary"
          >
            Open API Docs
          </a>
          <a 
            href={`${API_BASE_URL}/health`} 
            target="_blank" 
            rel="noopener noreferrer"
            className="btn btn-primary"
          >
            Check Health Endpoint
          </a>
          <button 
            onClick={() => {
              localStorage.clear();
              sessionStorage.clear();
              alert('Local storage cleared!');
            }}
            className="btn btn-danger"
          >
            Clear Storage
          </button>
        </div>
      </div>
    </div>
  );
}

// New component: Request Log Viewer
function RequestLogViewer({ requestLog, onClear }) {
  return (
    <div className="api-section" style={{marginTop: '20px', maxHeight: '400px', overflow: 'auto'}}>
      <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px'}}>
        <h3>🔍 Request/Response Log</h3>
        <button onClick={onClear} className="btn btn-secondary" style={{fontSize: '12px'}}>
          Clear Log
        </button>
      </div>
      
      {requestLog.length === 0 ? (
        <p style={{fontSize: '14px', color: '#666'}}>No requests logged yet.</p>
      ) : (
        <div style={{fontSize: '12px', fontFamily: 'monospace'}}>
          {requestLog.map(entry => (
            <details key={entry.id} style={{marginBottom: '10px', border: '1px solid #ddd', borderRadius: '3px', padding: '5px'}}>
              <summary style={{cursor: 'pointer', fontWeight: 'bold', color: entry.type === 'error' ? 'red' : entry.type === 'request' ? 'blue' : 'green'}}>
                {entry.type.toUpperCase()} {entry.method || ''} {entry.url} - {new Date(entry.timestamp).toLocaleTimeString()}
              </summary>
              <pre style={{margin: '10px 0', padding: '10px', background: '#f8f9fa', borderRadius: '3px', overflow: 'auto'}}>
                {JSON.stringify(entry, null, 2)}
              </pre>
            </details>
          ))}
        </div>
      )}
    </div>
  );
}

// Keep all existing components (PPTXTranslationTester, TextTranslationTester, etc.) from the original file
// They remain unchanged but are included in the enhanced version

// Add styles for new components
const styles = `
  .tabs {
    display: flex;
    gap: 10px;
    border-bottom: 2px solid #ddd;
  }
  
  .tab {
    padding: 10px 20px;
    background: none;
    border: none;
    cursor: pointer;
    font-size: 16px;
    border-bottom: 3px solid transparent;
    transition: all 0.3s;
  }
  
  .tab:hover {
    background: #f8f9fa;
  }
  
  .tab.active {
    border-bottom-color: #007bff;
    color: #007bff;
    font-weight: bold;
  }
  
  .method-badge {
    padding: 2px 8px;
    border-radius: 3px;
    font-size: 11px;
    font-weight: bold;
    color: white;
  }
  
  .method-get { background: #28a745; }
  .method-post { background: #007bff; }
  .method-put { background: #ffc107; color: #333; }
  .method-delete { background: #dc3545; }
`;

// Export all the original component functions here (copy from original App.js)
function PPTXTranslationTester({ tasks, setTasks, authToken }) {
  // ... copy from original
}

function TextTranslationTester({ tasks, setTasks, authToken }) {
  // ... copy from original
}

function AudioTranscriptionTester({ tasks, setTasks, authToken }) {
  // ... copy from original
}

function PPTXConversionTester({ tasks, setTasks, authToken }) {
  // ... copy from original
}

function TextToSpeechTester({ tasks, setTasks, authToken }) {
  // ... copy from original
}

function FileUploader({ files, setFiles, accept, multiple, label }) {
  // ... copy from original
}

function TaskManager({ tasks, onDownload, onCleanup, onRefresh }) {
  // ... copy from original
}

export default App;