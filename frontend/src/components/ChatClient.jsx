// src/components/ChatClient.js
import React, { useState, useEffect, useRef, useCallback } from 'react';
import createWebSocket from '../services/WebSocketService';

const clientId = `client_${Math.random().toString(36).substring(2, 15)}`;
const CHAT_WS_URL = `ws://localhost:4000/ws/chat/${clientId}`;

function ChatClient() {
    const [messages, setMessages] = useState([]);
    const [inputValue, setInputValue] = useState('');
    const [isConnected, setIsConnected] = useState(false);
    const socketRef = useRef(null);

    const addMessage = useCallback((sender, text) => {
        setMessages(prevMessages => [...prevMessages, { sender, text, id: Date.now() + Math.random() }]);
    }, []);

    useEffect(() => {
        socketRef.current = createWebSocket(
            CHAT_WS_URL,
            () => {
                setIsConnected(true);
                addMessage('System', 'Connected to chat server.');
            },
            (data) => {
                // Assuming messages from server are prefixed, e.g., "Agent: ..." or "You: ..."
                // Or just display raw data
                if (data.startsWith("You: ")) { // Avoid duplicating our own echoed messages if server echoes them
                    // Potentially handle differently or ignore if it's an echo of own message
                } else if (data.startsWith("Agent: ")) {
                     addMessage('Agent', data.substring("Agent: ".length));
                } else {
                     addMessage('Server', data);
                }
            },
            () => {
                setIsConnected(false);
                addMessage('System', 'Disconnected from chat server.');
                socketRef.current = null; // Clear ref on close
            },
            (error) => {
                addMessage('System', `Chat connection error: ${error.message || 'Unknown error'}`);
            }
        );

        return () => {
            if (socketRef.current) {
                socketRef.current.close();
                socketRef.current = null;
            }
        };
    }, [addMessage]);

    const handleSendMessage = () => {
        if (inputValue.trim() && socketRef.current && socketRef.current.readyState === WebSocket.OPEN) {
            socketRef.current.send(inputValue);
            addMessage('You', inputValue); // Optimistically add user's message
            setInputValue('');
        } else {
            addMessage('System', 'Not connected or message empty.');
        }
    };

    return (
        <div className="chat-client">
            <h3>Chat</h3>
            <div className="messages-area">
                {messages.map((msg) => (
                    <div key={msg.id} className={`message ${msg.sender.toLowerCase()}`}>
                        <strong>{msg.sender}:</strong> {msg.text}
                    </div>
                ))}
            </div>
            <div className="input-area">
                <input
                    type="text"
                    value={inputValue}
                    onChange={(e) => setInputValue(e.target.value)}
                    onKeyPress={(e) => e.key === 'Enter' && handleSendMessage()}
                    placeholder="Type your message..."
                />
                <button onClick={handleSendMessage} disabled={!isConnected}>Send</button>
            </div>
            <p>Status: {isConnected ? 'Connected' : 'Disconnected'}</p>
        </div>
    );
}

export default ChatClient;