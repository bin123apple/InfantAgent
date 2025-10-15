import os
import sys
import json
import asyncio
from aiohttp import web
from pathlib import Path

# Add the parent directory to the path so we can import the infant modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from infant.main import initialize_agent, run_single_step, cleanup
except ImportError:
    print("Warning: Could not import infant modules. Running in demo mode.")
    initialize_agent = None
    run_single_step = None
    cleanup = None

# Global variables to store agent and computer instances
agent = None
computer = None

# Initialize the web application
app = web.Application()
routes = web.RouteTableDef()

@routes.get('/')
async def index(request):
    """Serve the index.html file"""
    return web.FileResponse(Path(__file__).parent / 'index.html')

@routes.post('/api/chat')
async def chat(request):
    """Handle chat requests"""
    global agent, computer

    try:
        data = await request.json()
        user_message = data.get('message', '')

        if not user_message:
            return web.json_response({
                'success': False,
                'error': 'No message provided'
            })

        # If we're in demo mode or agent is not initialized
        if run_single_step is None or agent is None:
            # Return a demo response
            await asyncio.sleep(1)  # Simulate processing time
            return web.json_response({
                'success': True,
                'response': f"Demo mode: I received your message: '{user_message}'. In a real deployment, this would be processed by the Infant AI agent.",
                'status': 'completed'
            })

        # Process the message with the agent
        response = await run_single_step(agent, user_message)

        return web.json_response({
            'success': True,
            'response': response,
            'status': 'completed'
        })

    except Exception as e:
        print(f"Error in chat endpoint: {str(e)}")
        return web.json_response({
            'success': False,
            'error': str(e)
        })

@routes.post('/api/reset')
async def reset(request):
    """Reset the conversation"""
    global agent, computer

    try:
        # If we're in demo mode or agent is not initialized
        if agent is None:
            await asyncio.sleep(0.5)  # Simulate processing time
            return web.json_response({
                'success': True,
                'message': 'Demo mode: Conversation reset successfully',
                'newSessionId': 'demo-session'
            })

        # Reset the agent state
        agent.state.reset()

        # Reset accumulated cost
        for llm in agent._active_llms():
            llm.metrics.accumulated_cost = 0

        # Clean workspace
        exit_code, output = computer.execute(f'cd /workspace && rm -rf *')

        return web.json_response({
            'success': True,
            'message': 'Conversation reset successfully',
            'newSessionId': str(agent.state.session_id)
        })

    except Exception as e:
        print(f"Error in reset endpoint: {str(e)}")
        return web.json_response({
            'success': False,
            'error': str(e)
        })

@routes.post('/api/settings')
async def settings(request):
    """Update settings"""
    global agent

    try:
        data = await request.json()
        model = data.get('model')
        temperature = data.get('temperature')
        max_tokens = data.get('maxTokens')

        # In a real implementation, these settings would be applied to the agent
        # For now, we'll just return success

        return web.json_response({
            'success': True,
            'message': 'Settings updated successfully',
            'appliedSettings': {
                'model': model,
                'temperature': temperature,
                'maxTokens': max_tokens
            }
        })

    except Exception as e:
        print(f"Error in settings endpoint: {str(e)}")
        return web.json_response({
            'success': False,
            'error': str(e)
        })

@routes.get('/api/status')
async def status(request):
    """Get current status"""
    global agent

    try:
        # If we're in demo mode or agent is not initialized
        if agent is None:
            return web.json_response({
                'success': True,
                'status': 'ready',
                'currentTask': 'none',
                'model': 'claude-3-7-sonnet-latest',
                'sessionActive': True
            })

        # In a real implementation, we would get the actual status from the agent
        return web.json_response({
            'success': True,
            'status': 'ready',
            'currentTask': 'none',
            'model': agent._planning_llm.model,
            'sessionActive': True
        })

    except Exception as e:
        print(f"Error in status endpoint: {str(e)}")
        return web.json_response({
            'success': False,
            'error': str(e)
        })

async def init_agent():
    """Initialize the agent"""
    global agent, computer

    if initialize_agent is None:
        print("Running in demo mode - agent initialization skipped")
        return

    try:
        print("Initializing agent...")
        agent, computer = await initialize_agent()
        print("Agent initialized successfully")
    except Exception as e:
        print(f"Error initializing agent: {str(e)}")

async def cleanup_resources():
    """Clean up resources"""
    global agent, computer

    if cleanup is None or agent is None:
        return

    try:
        print("Cleaning up resources...")
        await cleanup(agent=agent, computer=computer)
        print("Resources cleaned up successfully")
    except Exception as e:
        print(f"Error cleaning up resources: {str(e)}")

async def start_background_tasks(app):
    """Start background tasks"""
    app['init_task'] = asyncio.create_task(init_agent())

async def cleanup_background_tasks(app):
    """Clean up background tasks"""
    app['init_task'].cancel()
    await cleanup_resources()

# Set up static routes
app.router.add_static('/css/', Path(__file__).parent / 'css')
app.router.add_static('/js/', Path(__file__).parent / 'js')
app.router.add_static('/img/', Path(__file__).parent / 'img')

# Add routes
app.add_routes(routes)

# Add startup and cleanup hooks
app.on_startup.append(start_background_tasks)
app.on_cleanup.append(cleanup_background_tasks)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    print(f"Starting server on port {port}...")
    web.run_app(app, port=port)
