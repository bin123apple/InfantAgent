// src/App.jsx
import { useState } from 'react';
import './App.css';
import Chat from './components/Chat';
import InfantBackendConnector from './services/BackendService';

function App() {
  const backendConnector = new InfantBackendConnector({ apiUrl: '/api' });


  return (
    <div className="App">
      <Chat backendConnector={backendConnector}/>


    </div>
  );
}

export default App;