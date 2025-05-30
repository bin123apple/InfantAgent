// Backend Connector for Infant AI Assistant
// This file provides the interface between the frontend and the Infant backend

class InfantBackendConnector {
    constructor(config = {}) {
        this.apiUrl = config.apiUrl || '/api';
        this.connected = false;
        this.sessionId = null;
    }

    // Initialize connection to the backend
    async connect() {
        try {
            // In a real implementation, this would establish a connection to the backend
            // For now, we'll simulate a successful connection
            this.connected = true;
            this.sessionId = 'session-' + Math.random().toString(36).substring(2, 15);
            console.log('Connected to Infant backend with session ID:', this.sessionId);
            return true;
        } catch (error) {
            console.error('Failed to connect to Infant backend:', error);
            this.connected = false;
            return false;
        }
    }

    // Send a user request to the backend
    async sendRequest(message, options = {}) {
        if (!this.connected) {
            await this.connect();
        }

        try {
            console.log('Sending request to backend:', message);

            // Make an actual API call to the backend
            const response = await fetch(`${this.apiUrl}/chat`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    message: message,
                    session_id: this.sessionId,
                    options: options
                })
            });

            if (!response.ok) {
                throw new Error(`API request failed with status ${response.status}`);
            }

            return await response.json();
        } catch (error) {
            console.error('Error sending request to backend:', error);
            return {
                success: false,
                error: error.message || 'Unknown error occurred'
            };
        }
    }

    // Reset the conversation by calling your real backend endpoint
    async resetConversation() {
        try {
        // 1) 发起真正的 POST 请求到 /api/reset
        const res = await fetch('/api/reset', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
            // 如果需要带 body，就加在这里
        });
    
        // 2) 解析后端返回的 JSON
        const data = await res.json();
    
        // 3) 如果后端返回 success，就更新本地 sessionId（可选）
        if (data.success && data.newSessionId) {
            this.sessionId = data.newSessionId;
        }
    
        // 4) 直接把后端返回的数据透传出去
        return data;
    
        } catch (error) {
        console.error('Error resetting conversation:', error);
        return {
            success: false,
            error: error.message || 'Unknown error occurred'
        };
        }
    }
  
    // Update settings in the backend
    async updateSettings(settings) {
        try {
            // In a real implementation, this would update settings in the backend
            console.log('Updating settings in backend:', settings);

            // Simulate network delay
            return new Promise((resolve) => {
                setTimeout(() => {
                    resolve({
                        success: true,
                        message: "Settings updated successfully",
                        appliedSettings: settings
                    });
                }, 1000);
            });
        } catch (error) {
            console.error('Error updating settings:', error);
            return {
                success: false,
                error: error.message || 'Unknown error occurred'
            };
        }
    }

    // Get current status from the backend
    async getStatus() {
        try {
            // In a real implementation, this would fetch the current status from the backend
            console.log('Fetching status from backend');

            // Simulate network delay
            return new Promise((resolve) => {
                setTimeout(() => {
                    resolve({
                        success: true,
                        status: "ready",
                        currentTask: "none",
                        model: "claude-3-7-sonnet-latest",
                        sessionActive: this.connected
                    });
                }, 500);
            });
        } catch (error) {
            console.error('Error fetching status:', error);
            return {
                success: false,
                error: error.message || 'Unknown error occurred'
            };
        }
    }

    // Disconnect from the backend
    async disconnect() {
        try {
            // In a real implementation, this would properly close the connection to the backend
            console.log('Disconnecting from Infant backend');
            this.connected = false;
            this.sessionId = null;
            return true;
        } catch (error) {
            console.error('Error disconnecting from backend:', error);
            return false;
        }
    }
}

// Export the connector
window.InfantBackendConnector = InfantBackendConnector;