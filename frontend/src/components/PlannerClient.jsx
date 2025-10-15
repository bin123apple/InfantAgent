// src/components/PlannerClient.js
import React, { useState, useEffect } from 'react';

// Use the same client_id as chat for consistency if planner is tied to chat's agent session
// Or generate a new one if planner can be independent.
// For simplicity, let's assume it needs a client_id known to the server.
// We'll use a placeholder here. You might need to pass the chat's clientId.
// const plannerClientId = `planner_${Math.random().toString(36).substring(2, 15)}`;
const plannerClientId = 'planner_xgxkxiubua'; // Example static ID for testing
const PLANNER_API_URL = `http://localhost:4000/api/planner/${plannerClientId}`;


function PlannerClient() {
    const [plannerData, setPlannerData] = useState(null);
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState(null);
    const [currentClientId, setCurrentClientId] = useState(plannerClientId); // Example: allow changing later

    const fetchPlannerData = () => {
        if (!currentClientId) {
            setError("Client ID is not set for planner.");
            return;
        }
        setIsLoading(true);
        setError(null);
        const url = `http://localhost:4000/api/planner/${currentClientId}`;
        fetch(url)
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                setPlannerData(data);
                setIsLoading(false);
            })
            .catch(err => {
                setError(err.message);
                setPlannerData(null);
                setIsLoading(false);
            });
    };

    useEffect(() => {
        // Fetch data when component mounts if client ID is available
        // Or trigger with a button if client ID needs to be set first (e.g., after chat connects)
        fetchPlannerData();
    }, [currentClientId]); // Refetch if client ID changes


    return (
        <div className="planner-client">
            <h3>Planner</h3>
            <button onClick={fetchPlannerData} disabled={isLoading}>
                {isLoading ? 'Loading...' : 'Refresh Planner'}
            </button>
            {/* This div will handle scrolling for planner details */}
            <div className="planner-details-container">
                {error && <p style={{ color: 'red' }}>Error: {error}</p>}
                {plannerData ? (
                    <div className="planner-details">
                        <p><strong>Goal:</strong> {plannerData.goal || 'N/A'}</p>
                        <p><strong>Status:</strong> {plannerData.status || 'N/A'}</p>
                        <p><strong>Assessment:</strong> {plannerData.main_task_assessment || 'N/A'}</p>
                        <h4>Sub-tasks:</h4>
                        {plannerData.sub_tasks && plannerData.sub_tasks.length > 0 ? (
                            <ul>
                                {plannerData.sub_tasks.map((task, index) => (
                                    <li key={index}>
                                        {typeof task === 'string' ? task : JSON.stringify(task)}
                                        {index === plannerData.current_sub_task_index && <strong> (Current)</strong>}
                                    </li>
                                ))}
                            </ul>
                        ) : (
                            <p>No sub-tasks.</p>
                        )}
                        <p><strong>Last Error:</strong> {plannerData.last_error || 'N/A'}</p>
                    </div>
                ) : (
                    !isLoading && <p>No planner data available.</p>
                )}
            </div>
        </div>
    );
}

export default PlannerClient;