import React, { useState, useEffect } from 'react';
import axios from 'axios';
import './App.css';

// API Configuration
const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

// Default client credentials from client_credentials.json
const DEFAULT_CLIENT_ID = 'client_1UXDGN0fwVYaZr2Ibt6k9w';
const DEFAULT_CLIENT_SECRET = 'zW8KKAhhNrtHMXkrdXBZ6reHSNVyZhUroGXli0V2WQM';

// Language options for testing - use lowercase for API compatibility
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
    'en-us': 'English (US)',
    'en-gb': 'English (UK)',
    'fr': 'French',
    'es': 'Spanish', 
    'de': 'German',
    'it': 'Italian',
    'pt-pt': 'Portuguese (EU)',
    'pt-br': 'Portuguese (BR)',
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
  { method: 'POST', path: '/token', desc: 'Get JWT token', auth: false },
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
  const [authToken, setAuthToken] = useState('');
  const [authStatus, setAuthStatus] = useState('unchecked');
  const [activeTab, setActiveTab] = useState('tools');
  const [requestLog, setRequestLog] = useState([]);
  const [showRawRequests, setShowRawRequests] = useState(false);
  const [tokenExpiry, setTokenExpiry] = useState(null);
  const [isObtainingToken, setIsObtainingToken] = useState(false);

  // Automatically obtain JWT token on startup
  useEffect(() => {
    checkApiHealth();
    obtainJwtToken();
  }, []);

  // Check auth when token changes
  useEffect(() => {
    if (authToken) {
      checkAuthentication();
    }
  }, [authToken]);

  // Check token expiry periodically
  useEffect(() => {
    const interval = setInterval(() => {
      if (tokenExpiry && new Date() > new Date(tokenExpiry)) {
        console.log('Token expired, obtaining new token...');
        obtainJwtToken();
      }
    }, 30000); // Check every 30 seconds
    return () => clearInterval(interval);
  }, [tokenExpiry]);

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
            id: Date.now() + 1,
            type: 'response',
            status: response.status,
            statusText: response.statusText,
            url: response.config.url,
            data: response.data,
            timestamp: new Date().toISOString()
          };
          setRequestLog(prev => [logEntry, ...prev].slice(0, 50));
        }
        return response;
      },
      (error) => {
        if (showRawRequests && error.response) {
          const logEntry = {
            id: Date.now() + 1,
            type: 'error',
            status: error.response.status,
            statusText: error.response.statusText,
            url: error.config?.url,
            data: error.response.data,
            timestamp: new Date().toISOString()
          };
          setRequestLog(prev => [logEntry, ...prev].slice(0, 50));
        }
        return Promise.reject(error);
      }
    );

    // Cleanup
    return () => {
      axios.interceptors.request.eject(requestInterceptor);
      axios.interceptors.response.eject(responseInterceptor);
    };
  }, [showRawRequests]);

  const obtainJwtToken = async () => {
    setIsObtainingToken(true);
    setAuthStatus('obtaining');
    
    try {
      const formData = new URLSearchParams();
      formData.append('username', DEFAULT_CLIENT_ID);
      formData.append('password', DEFAULT_CLIENT_SECRET);
      
      const response = await axios.post(`${API_BASE_URL}/token`, formData, {
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded'
        }
      });
      
      const { access_token, expires_in } = response.data;
      setAuthToken(access_token);
      
      // Calculate token expiry time
      const expiryTime = new Date();
      expiryTime.setSeconds(expiryTime.getSeconds() + expires_in);
      setTokenExpiry(expiryTime);
      
      console.log('JWT token obtained successfully, expires at:', expiryTime);
      setAuthStatus('valid');
    } catch (error) {
      console.error('Failed to obtain JWT token:', error);
      setAuthStatus('error');
    } finally {
      setIsObtainingToken(false);
    }
  };

  const checkApiHealth = async () => {
    try {
      const response = await axios.get(`${API_BASE_URL}/health`);
      setApiStatus(response.data.status === 'healthy' ? 'healthy' : 'degraded');
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
      await axios.get(`${API_BASE_URL}/tasks`, {
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
    if (!authToken || authStatus !== 'valid') return;
    
    // Update status for all active tasks
    const activeTasks = Object.entries(tasks).filter(([_, task]) => 
      task.status === 'pending' || task.status === 'running'
    );
    
    console.log('Updating tasks:', activeTasks.length, 'active tasks');
    
    for (const [taskId, _] of activeTasks) {
      try {
        const response = await axios.get(`${API_BASE_URL}/tasks/${taskId}`, {
          headers: {
            'Authorization': `Bearer ${authToken}`
          }
        });
        
        console.log(`Task ${taskId} status:`, response.data.status);
        setTasks(prev => ({
          ...prev,
          [taskId]: response.data
        }));
      } catch (error) {
        console.error(`Failed to update task ${taskId}:`, error);
      }
    }
  };

  const handleFileUpload = async (endpoint, files, params = {}) => {
    const formData = new FormData();
    
    // Add files
    files.forEach(file => {
      formData.append('files', file);
    });
    
    // Add other parameters
    Object.entries(params).forEach(([key, value]) => {
      formData.append(key, value);
    });
    
    try {
      const response = await axios.post(`${API_BASE_URL}${endpoint}`, formData, {
        headers: {
          'Authorization': `Bearer ${authToken}`,
          'Content-Type': 'multipart/form-data'
        }
      });
      
      const taskId = response.data.task_id;
      console.log('Task created:', taskId, response.data);
      setTasks(prev => {
        const newTasks = {
          ...prev,
          [taskId]: response.data
        };
        console.log('Updated tasks:', newTasks);
        return newTasks;
      });
      
      return taskId;
    } catch (error) {
      console.error('Upload failed:', error);
      alert('Upload failed: ' + (error.response?.data?.detail || error.message));
      return null;
    }
  };

  const downloadResult = async (taskId, fileIndex = null) => {
    try {
      const url = fileIndex !== null 
        ? `${API_BASE_URL}/download/${taskId}/${fileIndex}`
        : `${API_BASE_URL}/download/${taskId}`;
        
      const response = await axios.get(url, {
        headers: {
          'Authorization': `Bearer ${authToken}`
        },
        responseType: 'blob'
      });
      
      // Extract filename from content-disposition header
      const contentDisposition = response.headers['content-disposition'];
      let filename = `download_${taskId}`;
      if (contentDisposition) {
        const filenameMatch = contentDisposition.match(/filename="(.+)"/);
        if (filenameMatch) {
          filename = filenameMatch[1];
        }
      }
      
      // Create download link
      const blob = new Blob([response.data]);
      const url2 = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url2;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url2);
    } catch (error) {
      console.error('Download failed:', error);
      alert('Download failed: ' + (error.response?.data?.detail || error.message));
    }
  };

  const deleteTask = async (taskId) => {
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
      console.error('Delete failed:', error);
      alert('Delete failed: ' + (error.response?.data?.detail || error.message));
    }
  };

  // Generate test files
  const createTestFile = (content, filename = 'test.txt') => {
    const blob = new Blob([content], { type: 'text/plain' });
    return new File([blob], filename, { type: 'text/plain' });
  };

  const generateTestTextFile = (voiceName) => {
    const content = `This is a test file for the ${voiceName} voice. 
The Language Toolkit API will convert this text to speech using the ElevenLabs API.
This file was automatically generated for testing purposes.
The filename includes the voice name "${voiceName}" which will be automatically detected.`;
    
    const filename = `test_${voiceName}_content.txt`;
    return createTestFile(content, filename);
  };

  // Set up periodic task status checking
  useEffect(() => {
    if (!authToken || authStatus !== 'valid') return;
    
    const interval = setInterval(() => {
      updateAllTaskStatuses();
    }, 2000);
    
    return () => clearInterval(interval);
  }, [authToken, authStatus, tasks]);

  // Render different tabs
  const renderToolsTab = () => (
    <div className="tools-section">
      <h3>🛠️ API Tools</h3>
      
      {/* Text to Speech */}
      <div className="tool-card">
        <h4>🎙️ Text to Speech</h4>
        <div>
          <input 
            type="file" 
            multiple 
            accept=".txt"
            onChange={async (e) => {
              if (e.target.files.length > 0) {
                const taskId = await handleFileUpload('/tts', Array.from(e.target.files));
                if (taskId) {
                  alert(`TTS task created: ${taskId}`);
                }
              }
            }}
          />
          <p style={{fontSize: '12px', marginTop: '5px'}}>
            💡 Tip: Include voice name in filename (e.g., test_Loic_content.txt)
          </p>
        </div>
      </div>

      {/* PPTX Translation */}
      <div className="tool-card">
        <h4>📊 PPTX Translation</h4>
        <div style={{display: 'flex', gap: '10px', flexWrap: 'wrap'}}>
          <select id="pptx-source">
            {Object.entries(LANGUAGE_OPTIONS.source_languages).map(([code, name]) => (
              <option key={code} value={code}>{name}</option>
            ))}
          </select>
          <select id="pptx-target">
            {Object.entries(LANGUAGE_OPTIONS.target_languages).map(([code, name]) => (
              <option key={code} value={code}>{name}</option>
            ))}
          </select>
          <input 
            type="file" 
            multiple 
            accept=".pptx"
            onChange={async (e) => {
              if (e.target.files.length > 0) {
                const sourceLang = document.getElementById('pptx-source').value;
                const targetLang = document.getElementById('pptx-target').value;
                const taskId = await handleFileUpload('/translate/pptx', Array.from(e.target.files), {
                  source_lang: sourceLang,
                  target_lang: targetLang
                });
                if (taskId) {
                  alert(`Translation task created: ${taskId}`);
                }
              }
            }}
          />
        </div>
        <p style={{fontSize: '12px', marginTop: '5px', color: '#9ca3af'}}>
          💡 Note: For English targets, use en-us or en-gb. For Portuguese, use pt-pt or pt-br.
        </p>
      </div>

      {/* Text Translation */}
      <div className="tool-card">
        <h4>📝 Text Translation</h4>
        <div style={{display: 'flex', gap: '10px', flexWrap: 'wrap'}}>
          <select id="text-source">
            {Object.entries(LANGUAGE_OPTIONS.source_languages).map(([code, name]) => (
              <option key={code} value={code}>{name}</option>
            ))}
          </select>
          <select id="text-target">
            {Object.entries(LANGUAGE_OPTIONS.target_languages).map(([code, name]) => (
              <option key={code} value={code}>{name}</option>
            ))}
          </select>
          <input 
            type="file" 
            multiple 
            accept=".txt"
            onChange={async (e) => {
              if (e.target.files.length > 0) {
                const sourceLang = document.getElementById('text-source').value;
                const targetLang = document.getElementById('text-target').value;
                const taskId = await handleFileUpload('/translate/text', Array.from(e.target.files), {
                  source_lang: sourceLang,
                  target_lang: targetLang
                });
                if (taskId) {
                  alert(`Translation task created: ${taskId}`);
                }
              }
            }}
          />
        </div>
        <p style={{fontSize: '12px', marginTop: '5px', color: '#9ca3af'}}>
          💡 Note: Use language codes from dropdowns. Don't include language codes in filenames (e.g., avoid "_en_").
        </p>
      </div>

      {/* Audio Transcription */}
      <div className="tool-card">
        <h4>🎵 Audio Transcription</h4>
        <input 
          type="file" 
          multiple 
          accept=".mp3,.wav,.m4a"
          onChange={async (e) => {
            if (e.target.files.length > 0) {
              const taskId = await handleFileUpload('/transcribe/audio', Array.from(e.target.files));
              if (taskId) {
                alert(`Transcription task created: ${taskId}`);
              }
            }
          }}
        />
      </div>

      {/* PPTX Conversion */}
      <div className="tool-card">
        <h4>🔄 PPTX Conversion</h4>
        <div style={{display: 'flex', gap: '10px', flexWrap: 'wrap'}}>
          <select id="convert-format">
            <option value="pdf">PDF</option>
            <option value="png">PNG</option>
            <option value="webp">WEBP</option>
          </select>
          <input 
            type="file" 
            multiple 
            accept=".pptx"
            onChange={async (e) => {
              if (e.target.files.length > 0) {
                const format = document.getElementById('convert-format').value;
                const taskId = await handleFileUpload('/convert/pptx', Array.from(e.target.files), {
                  output_format: format
                });
                if (taskId) {
                  alert(`Conversion task created: ${taskId}`);
                }
              }
            }}
          />
        </div>
      </div>
    </div>
  );

  const renderTasksTab = () => (
    <div className="tasks-section">
      <h3>📋 Task Manager</h3>
      {Object.keys(tasks).length === 0 ? (
        <p>No active tasks</p>
      ) : (
        <div className="task-list">
          {Object.entries(tasks).map(([taskId, task]) => (
            <div key={taskId} className={`task-card status-${task.status}`}>
              <div className="task-header">
                <span className="task-id">{taskId}</span>
                <span className={`task-status status-${task.status}`}>
                  {task.status}
                </span>
              </div>
              <div className="task-details">
                {task.messages && task.messages.length > 0 && (
                  <div className="task-messages">
                    {task.messages.slice(-3).map((msg, idx) => (
                      <div key={idx} className="task-message">{msg}</div>
                    ))}
                  </div>
                )}
                {task.output_files && task.output_files.length > 0 && (
                  <div className="task-files">
                    <strong>Output files:</strong>
                    {task.output_files.map((file, idx) => (
                      <button
                        key={idx}
                        className="btn btn-small"
                        onClick={() => downloadResult(taskId, idx)}
                      >
                        📥 {file}
                      </button>
                    ))}
                  </div>
                )}
              </div>
              <div className="task-actions">
                {task.status === 'completed' && (
                  <button 
                    className="btn btn-primary"
                    onClick={() => downloadResult(taskId)}
                  >
                    Download All
                  </button>
                )}
                <button 
                  className="btn btn-danger"
                  onClick={() => deleteTask(taskId)}
                >
                  Delete
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );

  const renderEndpointsTab = () => (
    <div className="endpoints-section">
      <h3>📚 API Endpoints</h3>
      <table className="endpoints-table">
        <thead>
          <tr>
            <th>Method</th>
            <th>Path</th>
            <th>Description</th>
            <th>Auth</th>
          </tr>
        </thead>
        <tbody>
          {API_ENDPOINTS.map((endpoint, idx) => (
            <tr key={idx}>
              <td className={`method-${endpoint.method.toLowerCase()}`}>
                {endpoint.method}
              </td>
              <td><code>{endpoint.path}</code></td>
              <td>{endpoint.desc}</td>
              <td>{endpoint.auth ? '🔐' : '🌐'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );

  const renderVoicesTab = () => (
    <div className="voices-section">
      <h3>🎤 Available Voices</h3>
      <div className="voices-grid">
        {Object.entries(ELEVENLABS_VOICES).map(([name, id]) => (
          <div key={id} className="voice-card">
            <div className="voice-name">{name}</div>
            <div className="voice-id">{id}</div>
            <button 
              className="btn btn-small"
              onClick={() => {
                const file = generateTestTextFile(name);
                const url = URL.createObjectURL(file);
                const a = document.createElement('a');
                a.href = url;
                a.download = file.name;
                a.click();
                URL.revokeObjectURL(url);
              }}
            >
              Generate Test File
            </button>
          </div>
        ))}
      </div>
    </div>
  );

  const renderTestDataTab = () => {
    const [testContent, setTestContent] = useState('');
    const [testFilename, setTestFilename] = useState('test.txt');
    
    return (
      <div className="test-data-section">
        <h3>🧪 Test Data Generator</h3>
        
        <div className="test-generator">
          <h4>Quick Test Files</h4>
          <div className="quick-test-buttons">
            {Object.keys(ELEVENLABS_VOICES).map(voiceName => (
              <button
                key={voiceName}
                className="btn btn-secondary"
                onClick={() => {
                  const file = generateTestTextFile(voiceName);
                  const url = URL.createObjectURL(file);
                  const a = document.createElement('a');
                  a.href = url;
                  a.download = file.name;
                  a.click();
                  URL.revokeObjectURL(url);
                }}
              >
                📄 Generate for {voiceName}
              </button>
            ))}
          </div>
        </div>

        <div className="custom-generator">
          <h4>Custom Test File</h4>
          <input
            type="text"
            placeholder="Filename (e.g., test_Loic_custom.txt)"
            value={testFilename}
            onChange={(e) => setTestFilename(e.target.value)}
            style={{width: '100%', marginBottom: '10px'}}
          />
          <textarea
            placeholder="Enter test content..."
            value={testContent}
            onChange={(e) => setTestContent(e.target.value)}
            rows={6}
            style={{width: '100%', marginBottom: '10px'}}
          />
          <button
            className="btn btn-primary"
            onClick={() => {
              if (!testContent.trim()) {
                alert('Please enter some content');
                return;
              }
              const file = createTestFile(testContent, testFilename);
              const url = URL.createObjectURL(file);
              const a = document.createElement('a');
              a.href = url;
              a.download = file.name;
              a.click();
              URL.revokeObjectURL(url);
            }}
          >
            💾 Download Custom File
          </button>
        </div>
      </div>
    );
  };

  const renderConfigTab = () => (
    <div className="config-section">
      <h3>⚙️ Configuration</h3>
      
      <div className="config-card">
        <h4>API Base URL</h4>
        <code>{API_BASE_URL}</code>
      </div>

      <div className="config-card">
        <h4>Authentication</h4>
        <div>
          <strong>Client ID:</strong> <code>{DEFAULT_CLIENT_ID}</code>
        </div>
        <div>
          <strong>JWT Token:</strong>
          <textarea
            readOnly
            value={authToken}
            style={{width: '100%', height: '100px', marginTop: '10px'}}
          />
        </div>
        <div style={{marginTop: '10px'}}>
          <strong>Token Expiry:</strong> {tokenExpiry ? new Date(tokenExpiry).toLocaleString() : 'N/A'}
        </div>
        <button 
          className="btn btn-secondary" 
          onClick={obtainJwtToken}
          disabled={isObtainingToken}
          style={{marginTop: '10px'}}
        >
          {isObtainingToken ? 'Obtaining...' : '🔄 Refresh Token'}
        </button>
      </div>

      <div className="config-card">
        <h4>Request Logging</h4>
        <label>
          <input
            type="checkbox"
            checked={showRawRequests}
            onChange={(e) => setShowRawRequests(e.target.checked)}
          />
          Show raw HTTP requests/responses
        </label>
        
        {showRawRequests && requestLog.length > 0 && (
          <div className="request-log">
            <h5>Recent Requests ({requestLog.length})</h5>
            <button 
              className="btn btn-small"
              onClick={() => setRequestLog([])}
            >
              Clear Log
            </button>
            {requestLog.map(entry => (
              <div key={entry.id} className={`log-entry log-${entry.type}`}>
                <div className="log-header">
                  <span>{entry.type.toUpperCase()}</span>
                  <span>{entry.timestamp}</span>
                </div>
                {entry.type === 'request' && (
                  <>
                    <div>{entry.method} {entry.url}</div>
                    {entry.data && (
                      <pre>{JSON.stringify(entry.data, null, 2)}</pre>
                    )}
                  </>
                )}
                {(entry.type === 'response' || entry.type === 'error') && (
                  <>
                    <div>Status: {entry.status} {entry.statusText}</div>
                    <pre>{JSON.stringify(entry.data, null, 2)}</pre>
                  </>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );

  // File uploader component
  const FileUploader = ({ endpoint, params = {}, accept = "*" }) => {
    const [files, setFiles] = useState([]);
    
    return (
      <div className="file-uploader">
        <input
          type="file"
          multiple
          accept={accept}
          onChange={(e) => setFiles(Array.from(e.target.files))}
        />
        {files.length > 0 && (
          <div>
            <p>{files.length} file(s) selected</p>
            <button
              className="btn btn-primary"
              onClick={() => handleFileUpload(endpoint, files, params)}
            >
              Upload
            </button>
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="App">
      <header className="App-header">
        <h1>🚀 Language Toolkit API Tester</h1>
        <p>Enhanced testing interface for Language Toolkit API</p>
      </header>
      
      <main className="App-main">
        <div className="status-section">
          <div className="auth-section">
            <h3>🔐 Authentication</h3>
            <div>
              <div style={{display: 'flex', gap: '10px', alignItems: 'center'}}>
                <input
                  type="text"
                  placeholder="JWT Token"
                  value={authToken}
                  onChange={(e) => setAuthToken(e.target.value)}
                  style={{flex: 1}}
                  readOnly={isObtainingToken}
                />
                <button 
                  className="btn btn-secondary" 
                  onClick={checkAuthentication}
                  disabled={isObtainingToken}
                >
                  Test Auth
                </button>
              </div>
              <div style={{marginTop: '5px'}}>
                Auth Status: 
                <span className={`status-badge status-${authStatus}`}>
                  {authStatus === 'unchecked' && '❓ Unchecked'}
                  {authStatus === 'obtaining' && '⏳ Obtaining Token...'}
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
                {apiStatus === 'checking' && '⏳ Checking...'}
                {apiStatus === 'healthy' && '✅ Healthy'}
                {apiStatus === 'degraded' && '⚠️ Degraded'}
                {apiStatus === 'unhealthy' && '❌ Unhealthy'}
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
            className={activeTab === 'tools' ? 'active' : ''}
            onClick={() => setActiveTab('tools')}
          >
            🛠️ API Tools
          </button>
          <button
            className={activeTab === 'tasks' ? 'active' : ''}
            onClick={() => setActiveTab('tasks')}
          >
            📋 Tasks
          </button>
          <button
            className={activeTab === 'endpoints' ? 'active' : ''}
            onClick={() => setActiveTab('endpoints')}
          >
            📚 Endpoints
          </button>
          <button
            className={activeTab === 'voices' ? 'active' : ''}
            onClick={() => setActiveTab('voices')}
          >
            🎤 Voices
          </button>
          <button
            className={activeTab === 'testdata' ? 'active' : ''}
            onClick={() => setActiveTab('testdata')}
          >
            🧪 Test Data
          </button>
          <button
            className={activeTab === 'config' ? 'active' : ''}
            onClick={() => setActiveTab('config')}
          >
            ⚙️ Config
          </button>
        </div>

        <div className="tab-content">
          {activeTab === 'tools' && renderToolsTab()}
          {activeTab === 'tasks' && renderTasksTab()}
          {activeTab === 'endpoints' && renderEndpointsTab()}
          {activeTab === 'voices' && renderVoicesTab()}
          {activeTab === 'testdata' && renderTestDataTab()}
          {activeTab === 'config' && renderConfigTab()}
        </div>
      </main>
    </div>
  );
}

export default App;