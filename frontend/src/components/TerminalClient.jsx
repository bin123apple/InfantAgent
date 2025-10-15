// src/components/TerminalClient.js
import React, { useEffect, useRef, useState, useCallback } from 'react';
import { Terminal } from 'xterm';
import { FitAddon } from 'xterm-addon-fit';
import 'xterm/css/xterm.css';
import createWebSocket from '../services/WebSocketService';

// const clientId = `term_${Math.random().toString(36).substring(2, 15)}`; // Separate client ID for terminal
function TerminalClient({ wsUrlPath }) {
    const terminalContainerRef = useRef(null); // Renamed from terminalRef for clarity
    const xtermInstanceRef = useRef(null); // To store the XTerm instance
    const fitAddonRef = useRef(null);
    const socketRef = useRef(null);
    const [isConnected, setIsConnected] = useState(false);

    const TERMINAL_WS_URL = `ws://localhost:4000/${wsUrlPath}/${clientId}`; // Ensure clientId is defined

    const initializeTerminal = useCallback(() => {
        if (xtermInstanceRef.current || !terminalContainerRef.current) return;

        const term = new Terminal({
            cursorBlink: true,
            fontSize: 15, // Adjust as needed for smaller grid view
            rows: 15,     // Adjust default rows
            // theme: { background: '#282c34', foreground: '#abb2bf' } // Example theme
        });
        const fitAddon = new FitAddon();

        xtermInstanceRef.current = term;
        fitAddonRef.current = fitAddon;

        term.loadAddon(fitAddon);
        term.open(terminalContainerRef.current); // Attach to the inner div
        
        try {
            fitAddon.fit(); // Initial fit
        } catch (e) {
            console.error("Initial fit failed:", e);
        }


        term.writeln(`Welcome to ${wsUrlPath.includes('jupyter') ? 'Jupyter' : 'System'} Terminal!`);
        // ... rest of WebSocket logic ...

        term.onData(data => {
            if (socketRef.current && socketRef.current.readyState === WebSocket.OPEN) {
                socketRef.current.send(data);
            }
        });

    }, [TERMINAL_WS_URL, wsUrlPath]);


    useEffect(() => {
        initializeTerminal();

        const handleResize = () => {
            if (fitAddonRef.current) {
                try {
                     fitAddonRef.current.fit();
                } catch (e) {
                    console.error("Fit addon resize error:", e)
                }
            }
        };
        
        // Call resize after a short delay to ensure layout is stable
        const resizeTimeoutId = setTimeout(handleResize, 100);
        window.addEventListener('resize', handleResize);

        return () => {
            clearTimeout(resizeTimeoutId);
            window.removeEventListener('resize', handleResize);
            if (socketRef.current) {
                socketRef.current.close();
            }
            if (xtermInstanceRef.current) {
                xtermInstanceRef.current.dispose();
                xtermInstanceRef.current = null;
            }
        };
    }, [initializeTerminal]);

    return (
        <div className="terminal-client"> {/* This outer div is now flex item in grid */}
            <h3>{wsUrlPath.includes('jupyter') ? 'Jupyter Console' : 'System Shell'}</h3>
            {/* This wrapper helps control the terminal's flexible growth and scrolling area */}
            <div ref={terminalContainerRef} className="terminal-container-wrapper"></div>
            <p style={{marginTop: '5px', fontSize: '0.8em'}}>Status: {isConnected ? 'Connected' : 'Disconnected'}</p>
        </div>
    );
}
// Ensure clientId is defined, either passed as prop or generated within
// const clientId = `term_${Math.random().toString(36).substring(2, 15)}`;
const clientId = 'term_xgxkxiubua'; // Example static ID for testing
export default TerminalClient;