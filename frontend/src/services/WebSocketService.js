// src/services/WebSocketService.js

const createWebSocket = (url, onOpen, onMessage, onClose, onError) => {
    const socket = new WebSocket(url);

    socket.onopen = () => {
        console.log(`WebSocket connected to ${url}`);
        if (onOpen) onOpen();
    };

    socket.onmessage = (event) => {
        if (onMessage) onMessage(event.data);
    };

    socket.onclose = (event) => {
        console.log(`WebSocket disconnected from ${url}`, event.wasClean ? `Cleanly, code=${event.code} reason=${event.reason}` : 'Connection died');
        if (onClose) onClose(event);
    };

    socket.onerror = (error) => {
        console.error(`WebSocket error on ${url}:`, error);
        if (onError) onError(error);
    };

    return socket;
};

export default createWebSocket;