// src/components/VMClient.js
import React, { useState, useEffect } from 'react';

// Default NoMachine web client URL based on infant/computer/run_docker.sh
// NOMACHINE_HTTPS_WEB_PORT_IN_HOST defaults to 23003
const DEFAULT_NOMACHINE_URL = 'https://localhost:4443/';

function VMClient() {
    const [nomachineUrl, setNomachineUrl] = useState(DEFAULT_NOMACHINE_URL);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState(null);

    const handleLoad = () => {
        setIsLoading(false);
        setError(null);
        console.log(`NoMachine iframe content loaded from ${nomachineUrl}`);
    };

    const handleError = (e) => {
        setIsLoading(false);
        const specificError = `Failed to load NoMachine. Ensure it's running and accessible at ${nomachineUrl}. Common issues: Docker container not running, port not mapped, NoMachine server (nxserver) not started in the container, or HTTPS certificate issues (you might need to accept a self-signed certificate in a separate browser tab first).`;
        setError(specificError);
        console.error("Iframe load error event:", e);
        console.error(specificError);
    };

    useEffect(() => {
        setIsLoading(true);
        setError(null);
    }, [nomachineUrl]);

    return (
        <div className="vm-client">
            <h3>NoMachine VM</h3>
            <p>
                Attempting to connect to NoMachine web client at: <strong>{nomachineUrl}</strong>
            </p>
            <p>
                <em>
                    If the VM view below remains blank or shows an error:
                    <ol>
                        <li>Ensure your InfantAgent Docker container is running.</li>
                        <li>Verify that host port <strong>{DEFAULT_NOMACHINE_URL.split(':').pop().split('/')[0]}</strong> is correctly mapped to the NoMachine HTTPS port within the container (usually 4443). Check your <code>run_docker.sh</code> script; it should be mapped to <code>NOMACHINE_HTTPS_WEB_PORT_IN_HOST</code> (default 23003).</li>
                        <li>The NoMachine server (<code>nxserver</code>) must be running inside the Docker container.</li>
                        <li>
                            If NoMachine is using a self-signed HTTPS certificate, you might need to open{' '}
                            <a href={nomachineUrl} target="_blank" rel="noopener noreferrer">{nomachineUrl}</a>{' '}
                            in a new browser tab first and accept the certificate warning before it can load in this iframe.
                        </li>
                    </ol>
                </em>
            </p>
            {isLoading && <p className="loading-message">Loading NoMachine interface... If this takes a long time, please check the troubleshooting steps above.</p>}
            {error && <p className="error-message">Error: {error}</p>}
            <div className="nomachine-iframe-container" style={{ display: isLoading || error ? 'none' : 'block' }}>
                <iframe
                    src={nomachineUrl}
                    title="NoMachine VM"
                    width="100%"
                    height="600px" // Adjust as needed
                    frameBorder="0"
                    onLoad={handleLoad}
                    onError={handleError}
                    // allow="fullscreen" // Optional: allows the iframe to go fullscreen
                >
                    Your browser does not support iframes. Please open{' '}
                    <a href={nomachineUrl} target="_blank" rel="noopener noreferrer">{nomachineUrl}</a>{' '}
                    directly.
                </iframe>
            </div>
        </div>
    );
}

export default VMClient;