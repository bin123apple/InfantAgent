// src/App.js
import React from 'react';
import './App.css';
import ChatClient from './components/ChatClient';
import TerminalClient from './components/TerminalClient';
import PlannerClient from './components/PlannerClient';
import VMClient from './components/VMClient';

function App() {
    // No activeTab state needed anymore for the right panel

    return (
        <div className="App">
            <header className="App-header">
                <h1>Infant Agent Interface</h1>
            </header>
            <main className="App-main">
                <div className="left-panel">
                    <ChatClient /> {/* Chat client is always here */}
                </div>
                <div className="right-panel-grid-container">
                    {/* Grid for the other 4 components */}
                    <div className="grid-item terminal-item">
                        <TerminalClient wsUrlPath="ws/terminal" key="system-terminal" />
                    </div>
                    <div className="grid-item vm-item">
                        <VMClient />
                    </div>
                    <div className="grid-item planner-item">
                        <PlannerClient />
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