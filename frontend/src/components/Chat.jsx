import React, { useState, useRef, useEffect } from 'react';
import { Send, Bot, User, Paperclip, X, FileText, Image, File } from 'lucide-react';

const Chat = ({ backendConnector }) => {
  const [messages, setMessages] = useState([
    { id: 1, text: "Hello! I'm here to help. What would you like to chat about?", sender: 'bot', timestamp: new Date() }
  ]);
  const [input, setInput] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamingMessage, setStreamingMessage] = useState('');
  const [attachedFiles, setAttachedFiles] = useState([]);
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);
  const fileInputRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, streamingMessage]);

  const getFileIcon = (fileType) => {
    if (fileType.startsWith('image/')) return Image;
    if (fileType.includes('text') || fileType.includes('document')) return FileText;
    return File;
  };

  const formatFileSize = (bytes) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const handleFileSelect = (event) => {
    const files = Array.from(event.target.files);
    const newFiles = files.map(file => ({
      id: Date.now() + Math.random(),
      file: file,
      name: file.name,
      size: file.size,
      type: file.type
    }));
    
    setAttachedFiles(prev => [...prev, ...newFiles]);
    // Reset file input
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const removeFile = (fileId) => {
    setAttachedFiles(prev => prev.filter(f => f.id !== fileId));
  };

  const handleFileUpload = () => {
    fileInputRef.current?.click();
  };

  const simulateStreamingResponse = async (userMessage, files) => {
    // Simulate different responses based on user input and files
    let responses = [
      "That's an interesting question! Let me think about this carefully. Streaming responses are great for creating more engaging user experiences because they provide immediate feedback and make the interaction feel more natural and conversational.",
      "I understand what you're asking about. Real-time streaming in chat applications works by sending data in chunks rather than waiting for the complete response. This creates a more dynamic and responsive feel for users.",
      "Great point! When implementing streaming functionality, you'll want to consider factors like error handling, connection stability, and user experience. The key is to balance responsiveness with reliability.",
      "Thanks for that question! Streaming chat interfaces have become increasingly popular because they reduce perceived latency and keep users engaged throughout longer responses. The technical implementation can vary depending on your backend architecture."
    ];

    if (files && files.length > 0) {
      const fileTypes = files.map(f => f.type);
      if (fileTypes.some(type => type.startsWith('image/'))) {
        responses = [
          "I can see you've uploaded some images! While I can't actually process images in this demo, in a real implementation I would analyze the visual content and provide relevant insights or descriptions.",
          "Thanks for sharing those images! In a production chat system, I would be able to examine the visual content, identify objects, read text, and answer questions about what I see in the images.",
          "Great! You've attached some image files. Image analysis capabilities would allow me to describe scenes, identify objects, read text from images, and help with visual questions."
        ];
      } else if (fileTypes.some(type => type.includes('text') || type.includes('document'))) {
        responses = [
          "I notice you've uploaded some documents! In a real implementation, I would read through the content and help you analyze, summarize, or answer questions about the text.",
          "Thanks for the document upload! With proper file processing, I could extract the text content, provide summaries, answer questions about the material, or help with analysis.",
          "Excellent! You've shared some text documents. Document processing would allow me to read the content and assist with comprehension, analysis, or specific questions about the material."
        ];
      } else {
        responses = [
          "I see you've uploaded some files! While this is a demo interface, a production system would process these files appropriately based on their type and provide relevant assistance.",
          "Thanks for the file upload! Different file types would be handled accordingly - images analyzed, documents read, data files processed, etc.",
          "Great! You've attached some files. In a real implementation, I would process these based on their format and help you work with the content."
        ];
      }
    }
    
    const response = responses[Math.floor(Math.random() * responses.length)];
    const words = response.split(' ');
    
    setIsStreaming(true);
    setStreamingMessage('');
    
    for (let i = 0; i < words.length; i++) {
      await new Promise(resolve => setTimeout(resolve, 50 + Math.random() * 100));
      setStreamingMessage(prev => prev + (i === 0 ? words[i] : ' ' + words[i]));
    }
    
    // Complete the streaming and add to messages
    const newMessage = {
      id: Date.now(),
      text: response,
      sender: 'bot',
      timestamp: new Date()
    };
    
    setMessages(prev => [...prev, newMessage]);
    setStreamingMessage('');
    setIsStreaming(false);
  };

  const handleSend = async () => {
    if ((!input.trim() && attachedFiles.length === 0) || isStreaming) return;
    
    const userMessage = {
      id: Date.now(),
      text: input.trim(),
      sender: 'user',
      timestamp: new Date(),
      files: attachedFiles.length > 0 ? [...attachedFiles] : undefined
    };
    
    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setAttachedFiles([]);
    
    // Start streaming response
    await simulateStreamingResponse(userMessage.text, userMessage.files);
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const formatTime = (timestamp) => {
    return timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  };

  return (
    <div className="flex flex-col h-screen w-full bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b border-gray-200 p-3 sm:p-4 shadow-sm flex-shrink-0">
        <h1 className="text-lg sm:text-xl font-semibold text-gray-800 flex items-center gap-2">
          <Bot className="w-5 h-5 sm:w-6 sm:h-6 text-blue-600" />
          <span className="hidden sm:inline">Streaming Chat</span>
          <span className="sm:hidden">Chat</span>
        </h1>
      </div>

      {/* Messages Container */}
      <div className="flex-1 overflow-y-auto p-2 sm:p-4 space-y-3 sm:space-y-4 min-h-0">
        {messages.map((message) => (
          <div key={message.id} className={`flex ${message.sender === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div className={`flex w-full max-w-[85%] sm:max-w-sm md:max-w-md lg:max-w-lg xl:max-w-xl ${message.sender === 'user' ? 'flex-row-reverse' : 'flex-row'} items-start gap-2 sm:gap-3`}>
              <div className={`flex-shrink-0 w-6 h-6 sm:w-8 sm:h-8 rounded-full flex items-center justify-center ${
                message.sender === 'user' ? 'bg-blue-600' : 'bg-gray-600'
              }`}>
                {message.sender === 'user' ? (
                  <User className="w-3 h-3 sm:w-4 sm:h-4 text-white" />
                ) : (
                  <Bot className="w-3 h-3 sm:w-4 sm:h-4 text-white" />
                )}
              </div>
              <div className={`rounded-lg px-3 py-2 sm:px-4 sm:py-2 flex-1 min-w-0 ${
                message.sender === 'user' 
                  ? 'bg-blue-600 text-white' 
                  : 'bg-white text-gray-800 border border-gray-200'
              }`}>
                <p className="text-sm sm:text-base break-words">{message.text}</p>
                
                {/* File attachments */}
                {message.files && message.files.length > 0 && (
                  <div className="mt-2 space-y-1">
                    {message.files.map((file) => {
                      const IconComponent = getFileIcon(file.type);
                      return (
                        <div key={file.id} className={`flex items-center gap-2 p-2 rounded text-xs ${
                          message.sender === 'user' 
                            ? 'bg-blue-500 bg-opacity-50' 
                            : 'bg-gray-50'
                        }`}>
                          <IconComponent className="w-3 h-3 flex-shrink-0" />
                          <span className="flex-1 truncate">{file.name}</span>
                          <span className="text-xs opacity-75">{formatFileSize(file.size)}</span>
                        </div>
                      );
                    })}
                  </div>
                )}
                
                <p className={`text-xs mt-1 ${
                  message.sender === 'user' ? 'text-blue-100' : 'text-gray-500'
                }`}>
                  {formatTime(message.timestamp)}
                </p>
              </div>
            </div>
          </div>
        ))}

        {/* Streaming Message */}
        {isStreaming && (
          <div className="flex justify-start">
            <div className="flex w-full max-w-[85%] sm:max-w-sm md:max-w-md lg:max-w-lg xl:max-w-xl items-start gap-2 sm:gap-3">
              <div className="flex-shrink-0 w-6 h-6 sm:w-8 sm:h-8 rounded-full bg-gray-600 flex items-center justify-center">
                <Bot className="w-3 h-3 sm:w-4 sm:h-4 text-white" />
              </div>
              <div className="rounded-lg px-3 py-2 sm:px-4 sm:py-2 bg-white text-gray-800 border border-gray-200 flex-1 min-w-0">
                <p className="text-sm sm:text-base break-words">
                  {streamingMessage}
                  <span className="inline-block w-0.5 h-4 sm:h-5 bg-gray-400 ml-1 animate-pulse"></span>
                </p>
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input Area */}
      <div className="bg-white border-t border-gray-200 flex-shrink-0">
        {/* File Preview */}
        {attachedFiles.length > 0 && (
          <div className="p-3 border-b border-gray-200">
            <div className="flex flex-wrap gap-2">
              {attachedFiles.map((file) => {
                const IconComponent = getFileIcon(file.type);
                return (
                  <div key={file.id} className="flex items-center gap-2 bg-gray-100 rounded-lg p-2 text-sm">
                    <IconComponent className="w-4 h-4 text-gray-600 flex-shrink-0" />
                    <span className="flex-1 truncate max-w-32">{file.name}</span>
                    <span className="text-xs text-gray-500">{formatFileSize(file.size)}</span>
                    <button
                      onClick={() => removeFile(file.id)}
                      className="text-gray-400 hover:text-red-500 transition-colors"
                    >
                      <X className="w-3 h-3" />
                    </button>
                  </div>
                );
              })}
            </div>
          </div>
        )}
        
        <div className="p-3 sm:p-4">
          <div className="flex gap-2 sm:gap-3">
            <button
              onClick={handleFileUpload}
              disabled={isStreaming}
              className="flex-shrink-0 p-2 text-gray-500 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              title="Attach file"
            >
              <Paperclip className="w-4 h-4 sm:w-5 sm:h-5" />
            </button>
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder={isStreaming ? "Please wait for response..." : "Type your message..."}
              disabled={isStreaming}
              className="flex-1 resize-none border border-gray-300 rounded-lg px-3 py-2 sm:px-4 sm:py-2 text-sm sm:text-base focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 disabled:bg-gray-100 disabled:cursor-not-allowed transition-colors"
              rows="1"
              style={{ minHeight: '36px', maxHeight: '120px' }}
            />
            <button
              onClick={handleSend}
              disabled={(!input.trim() && attachedFiles.length === 0) || isStreaming}
              className="px-3 py-2 sm:px-4 sm:py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors flex-shrink-0"
            >
              <Send className="w-4 h-4 sm:w-5 sm:h-5" />
            </button>
          </div>
          <p className="text-xs text-gray-500 mt-2 hidden sm:block">
            Press Enter to send, Shift+Enter for new line
          </p>
          <p className="text-xs text-gray-500 mt-2 sm:hidden">
            Tap send or press Enter
          </p>
        </div>
        
        {/* Hidden file input */}
        <input
          ref={fileInputRef}
          type="file"
          multiple
          onChange={handleFileSelect}
          className="hidden"
          accept="*/*"
        />
      </div>
    </div>
  );
};

export default StreamingChat;