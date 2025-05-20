// src/App.js
import React, { useState, useEffect, useRef, useCallback } from 'react';
import './App.css';
import ChatClient from './components/ChatClient';
import TerminalClient from './components/TerminalClient';
import PlannerClient from './components/PlannerClient';
import VMClient from './components/VMClient';

const MIN_PANEL_WIDTH = 200; // Minimum width for left panel in pixels
const DEFAULT_LEFT_PANEL_PERCENT = 35; // Default width as percentage

function App() {
    const [leftPanelWidth, setLeftPanelWidth] = useState(0); // Will be set in pixels
    const [isDragging, setIsDragging] = useState(false);
    
    const appMainRef = useRef(null); // Ref for the main container
    const dragStartXRef = useRef(0);
    const initialLeftWidthRef = useRef(0);

    // Initialize left panel width based on percentage and container width
    useEffect(() => {
        if (appMainRef.current) {
            const containerWidth = appMainRef.current.offsetWidth;
            const initialWidth = (DEFAULT_LEFT_PANEL_PERCENT / 100) * containerWidth;
            setLeftPanelWidth(Math.max(MIN_PANEL_WIDTH, initialWidth));
        }
    }, []); // Empty dependency array, runs once on mount

    // Recalculate on window resize to maintain percentage (optional, can be complex)
    // For simplicity, we'll stick to pixel-based resizing after initial setup.
    // If you want percentage-based resize persistence, this needs more logic.


    const handleMouseDown = (e) => {
        // Prevent text selection during drag
        e.preventDefault(); 
        setIsDragging(true);
        dragStartXRef.current = e.clientX;
        initialLeftWidthRef.current = leftPanelWidth;
    };

    const handleMouseUp = useCallback(() => {
        if (isDragging) {
            setIsDragging(false);
        }
    }, [isDragging]);

    const handleMouseMove = useCallback((e) => {
        if (!isDragging || !appMainRef.current) {
            return;
        }
        const dx = e.clientX - dragStartXRef.current;
        const containerWidth = appMainRef.current.offsetWidth;
        
        let newLeftWidth = initialLeftWidthRef.current + dx;

        // Enforce minimum width for left panel
        newLeftWidth = Math.max(MIN_PANEL_WIDTH, newLeftWidth);
        
        // Enforce minimum width for right panel (e.g., 30% or another pixel value)
        const minRightPanelWidth = containerWidth * 0.20; // Example: right panel at least 20%
        if (newLeftWidth > containerWidth - minRightPanelWidth) {
            newLeftWidth = containerWidth - minRightPanelWidth;
        }
        
        setLeftPanelWidth(newLeftWidth);

    }, [isDragging, appMainRef]);


    useEffect(() => {
        // Attach and detach listeners
        if (isDragging) {
            window.addEventListener('mousemove', handleMouseMove);
            window.addEventListener('mouseup', handleMouseUp);
        } else {
            window.removeEventListener('mousemove', handleMouseMove);
            window.removeEventListener('mouseup', handleMouseUp);
        }

        return () => {
            // Cleanup listeners
            window.removeEventListener('mousemove', handleMouseMove);
            window.removeEventListener('mouseup', handleMouseUp);
        };
    }, [isDragging, handleMouseMove, handleMouseUp]);

    return (
        <div className="App">
            <header className="App-header">
                <h1>Infant Agent Interface</h1>
            </header>
            <main className="App-main" ref={appMainRef}>
                <div 
                    className="left-panel" 
                    style={{ width: `${leftPanelWidth}px`, flexShrink: 0 }}
                >
                    <ChatClient />
                </div>
                <div 
                    className="resizer" 
                    onMouseDown={handleMouseDown}
                    title="Resize chat panel"
                />
                <div className="right-panel-grid-container">
                    {/* Grid for the other 4 components */}
                    <div className="grid-item planner-item">
                        <PlannerClient />
                    </div>
                    <div className="grid-item vm-item">
                        <VMClient />
                    </div>
                    <div className="grid-item terminal-item">
                        <TerminalClient wsUrlPath="ws/terminal" key="system-terminal" />
                    </div>
                    <div className="grid-item jupyter-item">
                        <TerminalClient wsUrlPath="ws/jupyter" key="jupyter-terminal" />
                    </div>
                </div>
            </main>
        </div>
    );
}

export default App;