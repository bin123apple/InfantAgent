// DOM Elements
const chatMessages    = document.getElementById('chatMessages');
const userInput       = document.getElementById('userInput');
const sendButton      = document.getElementById('sendButton');
const resetButton     = document.getElementById('resetButton');
const settingsLink    = document.getElementById('settingsLink');
const settingsModal   = document.getElementById('settingsModal');
const closeSettings   = document.getElementById('closeSettings');
const settingsForm    = document.getElementById('settingsForm');
const temperatureSlider = document.getElementById('temperatureSlider');
const temperatureValue  = document.getElementById('temperatureValue');
const agentStatus       = document.getElementById('agentStatus');
const currentTask       = document.getElementById('currentTask');
const modelInfo         = document.getElementById('modelInfo');
const displayedMemoryIds = new Set();
const displayedResultIds = new Set();

// Initialize backend connector
const backendConnector = new InfantBackendConnector({ apiUrl: '/api' });


// Send a system-style message into chat
function addSystemMessage(message) {
  addMessageToChat('system', message);
}

// Send a message to the assistant
function sendMessage() {
  const message = userInput.value.trim();
  if (message === '') return;

  // 1) 在聊天窗口里显示用户消息
  addMessageToChat('user', message);

  // 2) 清空输入框
  userInput.value = '';

  // 3) 更新状态到“Processing”
  updateStatus('Processing', 'Analyzing your request...');

  // 4) 将消息发送到后端 /api/chat
  fetch('/api/chat', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({ message })
  })
    .then(res => res.json())
    .then(response => {
      if (response.success) {
        // 5a) 成功：显示助理回复
        // addMessageToChat('assistant', response.response); // Already handled by fetchAndRenderMemory
      } else {
        // 5b) 失败：显示错误信息
        addMessageToChat('system', `Error: ${response.error || 'Unknown error occurred'}`);
      }
      // 6) 不管成功还是失败，都重置状态到“Ready”
      updateStatus('Ready', 'None');
    })
    .catch(error => {
      console.error('Error sending message:', error);
      addMessageToChat('system', `Error: ${error.message || 'Failed to communicate with the backend'}`);
      updateStatus('Ready', 'None');
    });
}

function updateStatus(status, task) {
    agentStatus.textContent = status;
    currentTask.textContent = task;

    // Visual indication of status
    if (status === 'Ready') {
        agentStatus.style.color = '#28a745';
    } else if (status === 'Processing') {
        agentStatus.style.color = '#ffc107';
    } else {
        agentStatus.style.color = '#dc3545';
    }
}

// 清空并格式化换行的函数
async function addMessageToChat(sender, content) {
  const messageDiv = document.createElement('div');
  messageDiv.className = `message ${sender}`;

  const messageContent = document.createElement('div');
  messageContent.className = 'message-content';
  
  // Add the message content container to the DOM immediately
  messageDiv.appendChild(messageContent);
  chatMessages.appendChild(messageDiv);
  
  // Parse markdown first
  const parsedContent = marked.parse(content);
  
  // Create a temporary container to hold the parsed HTML
  const tempDiv = document.createElement('div');
  tempDiv.innerHTML = parsedContent;
  
  // Get the text content for streaming
  const fullText = tempDiv.textContent || tempDiv.innerText;
  
  // Clear the message content and stream the text
  messageContent.innerHTML = '';
  
  // Stream the content character by character
  let i = 0;
  const speed = 5; // Adjust speed (lower is faster)
  
  // Function to stream content
  const streamContent = async () => {
    if (i < fullText.length) {
      // Get the character at current position
      const char = fullText.charAt(i);
      
      // Add the character to the content
      messageContent.textContent += char;
      
      // Scroll to bottom after each character
      chatMessages.scrollTop = chatMessages.scrollHeight;
      
      i++;
      // Adjust speed based on character type for more natural feel
      const delay = char.match(/[.,!?;:]/) ? speed * 10 : 
                   char === ' ' ? speed * 2 : speed;
      
      // Continue streaming
      setTimeout(streamContent, delay);
    } else {
      // When done streaming, set the actual HTML content with proper formatting
      messageContent.innerHTML = parsedContent;
      chatMessages.scrollTop = chatMessages.scrollHeight;
    }
  };
  
  // Start the streaming effect
  streamContent();
}

async function simulateResponse(userMessage) {
    // Use the backend connector to send the request
    try {
        // Update status to show processing
        updateStatus('Processing', 'Analyzing your request...');

        // Send the request to the backend
        const result = await backendConnector.sendRequest(userMessage);

        if (result.success) {
            // Add system response to chat
            addMessageToChat('system', result.response);

            // Update status based on the response
            updateStatus('Ready', 'None');
        } else {
            // Handle error
            addMessageToChat('system', `Sorry, there was an error processing your request: ${result.error || 'Unknown error'}`);            
            updateStatus('Error', 'Failed to process request');
        }
    } catch (error) {
        console.error('Error in simulateResponse:', error);
        addMessageToChat('system', `Sorry, there was an unexpected error: ${error.message || 'Unknown error'}`);        
        updateStatus('Error', 'Failed to process request');
    }
}

async function resetConversation() {
    try {
        // Update status
        updateStatus('Processing', 'Resetting conversation...');

        // Clear chat messages except the welcome message
        while (chatMessages.children.length > 1) {
            chatMessages.removeChild(chatMessages.lastChild);
        }

        // Reset the conversation in the backend
        const result = await backendConnector.resetConversation();

        if (result.success) {
            // Add system message
            addMessageToChat('system', 'Conversation has been reset. How can I help you?');
            updateStatus('Ready', 'None');
            console.log('displayedMemoryIds cleared')
            displayedMemoryIds.clear();
        } else {
            // Handle error
            console.error('Error resetting conversation:', result.error);
            addMessageToChat('system', 'There was an error resetting the conversation. Please try again.');
            updateStatus('Error', 'Failed to reset conversation');
        }
    } catch (error) {
        console.error('Error in resetConversation:', error);
        addMessageToChat('system', 'There was an unexpected error resetting the conversation. Please try again.');
        updateStatus('Error', 'Failed to reset conversation');
    }
}

function updateSubtasks(tasks) {
  const ul = document.getElementById('subtaskList');
  ul.innerHTML = '';
  
  if (!tasks || tasks.length === 0) {
      const li = document.createElement('li');
      li.textContent = 'No tasks yet';
      li.style.fontStyle = 'italic';
      li.style.color = '#666';
      ul.appendChild(li);
      return;
  }
  
  tasks.forEach((t, index) => {
      const li = document.createElement('li');
      li.className = 'task-item';
      li.setAttribute('data-task-id', t.id || index);
      
      // 创建任务内容
      const taskContent = document.createElement('div');
      taskContent.className = 'task-content';
      
      const taskName = document.createElement('span');
      taskName.className = 'task-name';
      taskName.textContent = t.name || 'Unnamed task';
      
      const taskStatus = document.createElement('span');
      taskStatus.className = `task-status status-${t.status || 'pending'}`;
      taskStatus.textContent = t.status || 'pending';
      
      taskContent.appendChild(taskName);
      taskContent.appendChild(taskStatus);
      
      // 如果有描述，添加描述
      if (t.description) {
          const taskDesc = document.createElement('div');
          taskDesc.className = 'task-description';
          taskDesc.textContent = t.description;
          taskContent.appendChild(taskDesc);
      }
      
      // 添加操作按钮
      const taskActions = document.createElement('div');
      taskActions.className = 'task-actions';
      
      if (t.status !== 'completed') {
          const completeBtn = document.createElement('button');
          completeBtn.className = 'task-btn complete-btn';
          completeBtn.textContent = '✓';
          completeBtn.title = 'Mark as completed';
          completeBtn.onclick = (e) => {
              e.stopPropagation();
              completeTask(t.id || index);
          };
          taskActions.appendChild(completeBtn);
      }
      
      const deleteBtn = document.createElement('button');
      deleteBtn.className = 'task-btn delete-btn';
      deleteBtn.textContent = '×';
      deleteBtn.title = 'Delete task';
      deleteBtn.onclick = (e) => {
          e.stopPropagation();
          deleteTask(t.id || index);
      };
      taskActions.appendChild(deleteBtn);
      
      li.appendChild(taskContent);
      li.appendChild(taskActions);
      
      // 添加状态样式
      if (t.status === 'completed') {
          li.classList.add('completed');
      } else if (t.status === 'running') {
          li.classList.add('running');
      }
      
      ul.appendChild(li);
  });
}


// 更新 Terminal 面板
function updateTerminal(commands) {
  const term = document.getElementById('terminalOutput');
  const currentContent = commands.map(c => 
    c.result ? `$ ${c.command}\n${c.result}\n` : `$ ${c.command}\n`
  ).join('');

  if (term.textContent !== currentContent) {
    term.textContent = currentContent;
    term.scrollTop = term.scrollHeight;
  }

}

// 更新 Jupyter Code 面板
function updateNotebook(codes) {
  const nb = document.getElementById('notebookOutput');
  const currentContent = codes.map(c => c.result ? c.code + c.result : c.code).join('');
  
  if (Array.from(nb.children).map(el => el.textContent).join('') !== currentContent) {
    nb.innerHTML = codes.map(c => `<pre>${c.result ? c.code + c.result : c.code}</pre>`).join('');
    nb.scrollTop = nb.scrollHeight;
  }
}

let lastMemIndex  = 0;
let lastCmdIndex  = 0;
let lastCodeIndex = 0;

async function fetchAndRenderMemory() {
  try {
    const res  = await fetch('/api/memory');
    const data = await res.json();
    if (!data.success) return;

    // 1) 更新面板
    updateSubtasks(data.tasks);
    updateTerminal(data.commands);
    updateNotebook(data.codes);

    // 2) 遍历所有 memories
    if (Array.isArray(data.memories)) {
      data.memories.forEach(mem => {
        console.log(Array.from(displayedMemoryIds));
        console.log(mem.id, mem.category, mem.thought);
        if (!displayedMemoryIds.has(mem.id) && mem.category === 'Message') {
          updateStatus('Awaiting for user input', 'None');
          console.log('Finish updateStatus');
        }
        if (!displayedMemoryIds.has(mem.id) && mem.thought) {
          addMessageToChat('system',
            `${mem.thought}`
          );
          displayedMemoryIds.add(mem.id);
        }
      });
    }
  } catch (e) {
    console.error('Failed to fetch memory:', e);
  }
}

// 启动轮询：每 2 秒刷新一次
setInterval(fetchAndRenderMemory, 2000);
// 页面加载后立即拉一次
document.addEventListener('DOMContentLoaded', fetchAndRenderMemory);

// Function to connect to backend
async function connectToBackend() {
    try {
      // Connect to the backend using our connector
      const connected = await backendConnector.connect();
  
      if (connected) {
        console.log('Connected to Infant backend');
        // Get initial status
        const status = await backendConnector.getStatus();
        if (status.success) {
          updateStatus(status.status.charAt(0).toUpperCase() + status.status.slice(1), status.currentTask);
          modelInfo.textContent = status.model
        }
        return true;
      } else {
        console.error('Failed to connect to Infant backend');
        addMessageToChat('system', 'Failed to connect to the backend. Some features may not work properly.');
        updateStatus('Disconnected', 'No connection to backend');
        return false;
      }
    } catch (error) {
      console.error('Error connecting to backend:', error);
      addMessageToChat('system', 'Error connecting to the backend. Some features may not work properly.');
      updateStatus('Error', 'Connection error');
      return false;
    }
  }

// 处理文件/文件夹上传
async function handleFileUpload(event) {
  const input = event.target;
  const files = Array.from(input.files);
  if (files.length === 0) return;

  addSystemMessage('📤 Uploading to workspace...');

  const formData = new FormData();
  files.forEach(file => {
    // 保留相对路径上传
    const relPath = file.webkitRelativePath || file.name;
    formData.append('files', file, relPath);
  });

  try {
    const response = await fetch('/api/upload', {
      method: 'POST',
      body: formData
    });
    const result = await response.json();

    if (result.success) {
      addSystemMessage('✅ Upload complete!');
    } else {
      addSystemMessage(`❌ Upload error: ${result.error}`);
    }
  } catch (err) {
    console.error('Upload failed:', err);
    addSystemMessage(`❌ Upload failed: ${err.message}`);
  }

  // ***关键***：清空 input.value，确保下次选同一批文件也会触发 change
  input.value = null;
}

// 其余功能函数略（sendMessage, resetConversation, updateStatus, saveSettings, connectToBackend）…
// 请保持你现有的这几段不变

async function saveSettings(){
  const modelSelect = document.getElementById('modelSelect');
  const apiKeyInput = document.getElementById('modelApiKey');
  const temperatureSlider = document.getElementById('temperatureSlider');
  const maxTokensInput = document.getElementById('maxTokensInput');

  const settings = {
    model: modelSelect.value,
    apiKey: apiKeyInput.value,
    temperature: temperatureSlider.value,
    maxTokens: maxTokensInput.value
  };

  localStorage.setItem('settings', JSON.stringify(settings));

  // 保存到后端
  const response = await fetch('/api/settings', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(settings)
  });
  updateStatus('Processing', 'None');
  modelInfo.textContent = settings.model;
  const result = await response.json();

  if (result.success) {   
    console.log(result);
    if (result.message.includes('updated')) {
      addSystemMessage('✅ Settings saved successfully! Agent is updated');
      updateStatus('Ready', 'None');
      return;
    }

    addSystemMessage('✅ Settings saved successfully! Initializing agent...');

    const init_response = await fetch('/api/initialize', {
      method: 'GET',
    });
    const init_result = await init_response.json();

    if (init_result.success) {
      addSystemMessage('✅ Agent initialized successfully!');
      updateStatus('Ready', 'None');

    } else {
      addSystemMessage(`❌ Failed to initialize agent: ${result.error}`);
    }
  } else {
    addSystemMessage(`❌ Failed to save settings: ${result.error}`);
  }
}

// --------------------
// 统一在这里注册所有事件
// --------------------
document.addEventListener('DOMContentLoaded', () => {
  // 发送消息
  sendButton.addEventListener('click', sendMessage);
  userInput.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  });

  // 重置对话
  resetButton.addEventListener('click', resetConversation);

  settingsModal.style.display = 'flex';
  // 模态框设置
  settingsLink.addEventListener('click', e => {
    e.preventDefault();
    settingsModal.style.display = 'flex';
  });
  closeSettings.addEventListener('click', () => settingsModal.style.display = 'none');
  window.addEventListener('click', e => {
    if (e.target === settingsModal) settingsModal.style.display = 'none';
  });

  // 温度滑块
  temperatureSlider.addEventListener('input', () => {
    temperatureValue.textContent = temperatureSlider.value;
  });
  settingsForm.addEventListener('submit', e => {
    e.preventDefault();
    saveSettings();
    settingsModal.style.display = 'none';
  });

  // 文件上传——文件
  const uploadFilesBtn    = document.getElementById('uploadFilesBtn');
  const fileUploadFiles   = document.getElementById('fileUploadFiles');
  uploadFilesBtn.addEventListener('click',    () => fileUploadFiles.click());
  fileUploadFiles.addEventListener('change', handleFileUpload);

  // 文件夹上传——文件夹
  const uploadFolderBtn  = document.getElementById('uploadFolderBtn');
  const fileUploadFolder = document.getElementById('fileUploadFolder');
  uploadFolderBtn.addEventListener('click',      () => fileUploadFolder.click());
  fileUploadFolder.addEventListener('change', handleFileUpload);

  // Initialize Guacamole desktop iframe with auth token
  loadGuacamoleDesktop();

  // 初始化连接
  console.log('[Debug] connectToBackend() 开始执行');
  connectToBackend();
});

// Load Guacamole desktop with auto-login
async function loadGuacamoleDesktop() {
  const frame = document.getElementById('desktopFrame');
  try {
    const res = await fetch('/api/guacamole-token');
    const data = await res.json();
    if (data.success) {
      // Connection ID: base64("GNOME Desktop (RDP)\0c\0default")
      frame.src = `/guacamole/#/client/R05PTUUgRGVza3RvcCAoUkRQKQBjAGRlZmF1bHQ?token=${data.token}`;
    } else {
      console.error('Failed to get Guacamole token:', data.error);
      frame.src = '/guacamole/';
    }
  } catch (e) {
    console.error('Failed to load Guacamole desktop:', e);
    frame.src = '/guacamole/';
  }
}

// 全局变量存储EventSource
let tasksEventSource = null;

// 启动Tasks实时监控
function startTasksMonitoring() {
    // 关闭现有连接
    if (tasksEventSource) {
        tasksEventSource.close();
    }
    
    // 创建新的SSE连接
    tasksEventSource = new EventSource('/api/tasks/stream');
    
    tasksEventSource.onmessage = function(event) {
        try {
            const data = JSON.parse(event.data);
            if (data.tasks) {
                updateSubtasks(data.tasks);
            } else if (data.error) {
                console.error('Tasks stream error:', data.error);
            }
        } catch (e) {
            console.error('Error parsing tasks stream data:', e);
        }
    };
    
    tasksEventSource.onerror = function(event) {
        console.error('Tasks EventSource error:', event);
        // 5秒后重连
        setTimeout(() => {
            if (tasksEventSource.readyState === EventSource.CLOSED) {
                startTasksMonitoring();
            }
        }, 5000);
    };
}

// 停止Tasks监控
function stopTasksMonitoring() {
    if (tasksEventSource) {
        tasksEventSource.close();
        tasksEventSource = null;
    }
}

// 完成任务
async function completeTask(taskId) {
    try {
        const response = await fetch(`/api/tasks/${taskId}/complete`, {
            method: 'POST',
        });
        const data = await response.json();
        
        if (!data.success) {
            console.error('Failed to complete task:', data.error);
            showNotification('Failed to complete task', 'error');
        } else {
            showNotification('Task completed!', 'success');
        }
    } catch (error) {
        console.error('Error completing task:', error);
        showNotification('Error completing task', 'error');
    }
}

// 删除任务
async function deleteTask(taskId) {
    if (!confirm('Are you sure you want to delete this task?')) {
        return;
    }
    
    try {
        const response = await fetch(`/api/tasks/${taskId}`, {
            method: 'DELETE',
        });
        const data = await response.json();
        
        if (!data.success) {
            console.error('Failed to delete task:', data.error);
            showNotification('Failed to delete task', 'error');
        } else {
            showNotification('Task deleted!', 'success');
        }
    } catch (error) {
        console.error('Error deleting task:', error);
        showNotification('Error deleting task', 'error');
    }
}

// 手动刷新Tasks
async function refreshTasks() {
    try {
        const response = await fetch('/api/tasks');
        const data = await response.json();
        
        if (data.success) {
            updateSubtasks(data.tasks);
        } else {
            console.error('Failed to fetch tasks');
        }
    } catch (error) {
        console.error('Error fetching tasks:', error);
    }
}

// 显示通知 (如果还没有的话)
function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.textContent = message;
    
    document.body.appendChild(notification);
    
    // 3秒后自动消失
    setTimeout(() => {
        notification.classList.add('fade-out');
        setTimeout(() => {
            document.body.removeChild(notification);
        }, 300);
    }, 3000);
}

// 页面加载时启动Tasks监控
document.addEventListener('DOMContentLoaded', function() {
    // 启动实时监控
    startTasksMonitoring();
    
    // 初始加载一次
    refreshTasks();
});

// 页面卸载时停止监控
window.addEventListener('beforeunload', function() {
    stopTasksMonitoring();
});