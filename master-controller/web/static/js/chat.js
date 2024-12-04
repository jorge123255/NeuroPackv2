class ChatClient {
    constructor() {
        this.ws = null;
        this.isConnected = false;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.reconnectDelay = 2000;
        this.statusDot = document.querySelector('.status-dot');
        this.statusText = document.querySelector('.status-text');
        this.modelSelect = document.querySelector('#model-select');
        this.messageContainer = document.querySelector('.message-container');
        
        this.setupWebSocket();
        this.loadModels();
        
        // Setup event listeners
        document.querySelector('.send-button').addEventListener('click', () => this.sendMessage());
        document.querySelector('.chat-input').addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });
    }
    
    setupWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const host = window.location.hostname;
        const wsUrl = `${protocol}//${host}:8765/ws`;
        console.log('Connecting to WebSocket:', wsUrl);
        
        this.ws = new WebSocket(wsUrl);
        
        this.ws.onopen = () => {
            console.log('WebSocket connected');
            this.isConnected = true;
            this.reconnectAttempts = 0;
            this.updateStatus(true);
        };
        
        this.ws.onclose = () => {
            console.log('WebSocket disconnected');
            this.isConnected = false;
            this.updateStatus(false);
            this.attemptReconnect();
        };
        
        this.ws.onerror = (error) => {
            console.error('WebSocket error:', error);
            this.updateStatus(false);
        };
        
        this.ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                this.handleMessage(data);
            } catch (e) {
                console.error('Error parsing message:', e);
            }
        };
    }
    
    updateStatus(connected) {
        if (this.statusDot) {
            this.statusDot.classList.toggle('connected', connected);
        }
        if (this.statusText) {
            this.statusText.textContent = connected ? 'Connected' : 'Disconnected';
        }
    }
    
    attemptReconnect() {
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
            this.reconnectAttempts++;
            console.log(`Attempting to reconnect (${this.reconnectAttempts}/${this.maxReconnectAttempts})...`);
            setTimeout(() => this.setupWebSocket(), this.reconnectDelay);
        } else {
            console.error('Max reconnection attempts reached');
        }
    }
    
    async loadModels() {
        try {
            const response = await fetch('/api/models');
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const data = await response.json();
            
            // Clear existing options
            this.modelSelect.innerHTML = '';
            
            // Ensure data.models is an array
            const models = Array.isArray(data.models) ? data.models : [];
            
            if (models.length === 0) {
                // Add a default option if no models are available
                const option = document.createElement('option');
                option.value = '';
                option.textContent = 'No models available';
                option.disabled = true;
                option.selected = true;
                this.modelSelect.appendChild(option);
            } else {
                // Add models to select
                models.forEach(model => {
                    const option = document.createElement('option');
                    option.value = model.name;
                    option.textContent = `${model.name} (${model.type})`;
                    this.modelSelect.appendChild(option);
                });
            }
        } catch (error) {
            console.error('Error fetching models:', error);
            // Add error option
            this.modelSelect.innerHTML = '';
            const option = document.createElement('option');
            option.value = '';
            option.textContent = 'Error loading models';
            option.disabled = true;
            option.selected = true;
            this.modelSelect.appendChild(option);
        }
    }
    
    async downloadModel(modelName) {
        try {
            const response = await fetch('/api/models/download', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    model_name: modelName,
                    source: modelName.split('/')[0] // 'ollama' or 'huggingface'
                }),
            });
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const data = await response.json();
            return data;
        } catch (error) {
            console.error('Error downloading model:', error);
            throw error;
        }
    }
    
    async sendMessage() {
        const input = document.querySelector('.chat-input');
        const message = input.value.trim();
        
        if (!message) return;
        
        const selectedModel = this.modelSelect.value;
        if (!selectedModel) {
            alert('Please select a model first');
            return;
        }
        
        // Clear input
        input.value = '';
        
        // Add user message to chat
        this.addMessage('user', message);
        
        try {
            // Send message to server
            if (this.isConnected) {
                this.ws.send(JSON.stringify({
                    type: 'chat',
                    model: selectedModel,
                    message: message
                }));
            } else {
                throw new Error('Not connected to server');
            }
        } catch (error) {
            console.error('Error sending message:', error);
            this.addMessage('system', 'Error: Failed to send message. Please try again.');
        }
    }
    
    addMessage(role, content) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${role}`;
        messageDiv.innerHTML = `
            <div class="message-role">${role}</div>
            <div class="message-content">${content}</div>
        `;
        this.messageContainer.appendChild(messageDiv);
        this.messageContainer.scrollTop = this.messageContainer.scrollHeight;
    }
    
    handleMessage(data) {
        if (data.type === 'chat_response') {
            this.addMessage('assistant', data.content);
        } else if (data.type === 'error') {
            this.addMessage('system', `Error: ${data.message}`);
        }
    }
}

// Initialize chat client when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.chatClient = new ChatClient();
}); 