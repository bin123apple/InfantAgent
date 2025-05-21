// DOM Elements
const chatMessages = document.getElementById('chatMessages');
const userInput = document.getElementById('userInput');
const sendButton = document.getElementById('sendButton');
const resetButton = document.getElementById('resetButton');
const settingsLink = document.getElementById('settingsLink');
const settingsModal = document.getElementById('settingsModal');
const closeSettings = document.getElementById('closeSettings');
const settingsForm = document.getElementById('settingsForm');
const temperatureSlider = document.getElementById('temperatureSlider');
const temperatureValue = document.getElementById('temperatureValue');
const agentStatus = document.getElementById('agentStatus');
const currentTask = document.getElementById('currentTask');
const modelInfo = document.getElementById('modelInfo');

// Initialize backend connector
const backendConnector = new InfantBackendConnector({
    apiUrl: '/api'
});

// Event Listeners
document.addEventListener('DOMContentLoaded', () => {
    // Send message on button click
    sendButton.addEventListener('click', sendMessage);

    // Send message on Enter key (but allow Shift+Enter for new lines)
    userInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    // Reset conversation
    resetButton.addEventListener('click', resetConversation);

    // Settings modal
    settingsLink.addEventListener('click', (e) => {
        e.preventDefault();
        settingsModal.style.display = 'flex';
    });

    closeSettings.addEventListener('click', () => {
        settingsModal.style.display = 'none';
    });

    // Close modal when clicking outside
    window.addEventListener('click', (e) => {
        if (e.target === settingsModal) {
            settingsModal.style.display = 'none';
        }
    });

    // Update temperature value display
    temperatureSlider.addEventListener('input', () => {
        temperatureValue.textContent = temperatureSlider.value;
    });

    // Save settings
    settingsForm.addEventListener('submit', (e) => {
        e.preventDefault();
        saveSettings();
        settingsModal.style.display = 'none';
    });
});

// Functions
function sendMessage() {
    const message = userInput.value.trim();
    if (message === '') return;

    // Add user message to chat
    addMessageToChat('user', message);

    // Clear input
    userInput.value = '';

    // Update status
    updateStatus('Processing', 'Analyzing your request...');

    // In a real implementation, this would send the message to the backend
    // For now, we'll simulate a response after a delay
    simulateResponse(message);
}

function addMessageToChat(sender, content) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${sender}`;

    const messageContent = document.createElement('div');
    messageContent.className = 'message-content';

    // Split content by newlines and create paragraph for each
    const paragraphs = content.split('
').filter(p => p.trim() !== '');
    paragraphs.forEach(paragraph => {
        const p = document.createElement('p');
        p.textContent = paragraph;
        messageContent.appendChild(p);
    });

    messageDiv.appendChild(messageContent);
    chatMessages.appendChild(messageDiv);

    // Scroll to bottom
    chatMessages.scrollTop = chatMessages.scrollHeight;
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

async function saveSettings() {
    try {
        // Get values from form
        const model = document.getElementById('modelSelect').value;
        const temperature = temperatureSlider.value;
        const maxTokens = document.getElementById('maxTokensInput').value;

        // Update displayed model info
        modelInfo.textContent = document.getElementById('modelSelect').options[document.getElementById('modelSelect').selectedIndex].text;

        // Send settings to the backend
        const settings = { model, temperature, maxTokens };
        const result = await backendConnector.updateSettings(settings);

        if (result.success) {
            // Show confirmation
            addMessageToChat('system', 'Settings updated successfully.');
        } else {
            // Handle error
            console.error('Error updating settings:', result.error);
            addMessageToChat('system', 'There was an error updating settings. Please try again.');
        }

        // Scroll to bottom
        chatMessages.scrollTop = chatMessages.scrollHeight;
    } catch (error) {
        console.error('Error in saveSettings:', error);
        addMessageToChat('system', 'There was an unexpected error updating settings. Please try again.');
    }
}

// Function to connect to backend (placeholder for now)
async function connectToBackend() {
    try {
        // Connect to the backend using our connector
        const connected = await backendConnector.connect();

        if (connected) {
            console.log('Connected to Infant backend');
            // Get initial status
            const status = await backendConnector.getStatus();
            if (status.success) {
                updateStatus(status.status, status.currentTask);
                modelInfo.textContent = status.model.split('-').map(word => word.charAt(0).toUpperCase() + word.slice(1)).join(' ');
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

// Initialize connection on page load
connectToBackend();
