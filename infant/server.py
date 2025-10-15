# main_api.py
import asyncio
import os
import select # For non-blocking reads from file descriptors
import subprocess # For cleaning up ssh_tunnel_proc
from typing import Any, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException

# Assuming these can be imported and potentially adapted for async/await if needed
from infant.main import initialize_agent, run_single_step
from infant.computer.computer import Computer # For type hinting
from infant.agent.agent import Agent # For type hinting
# from infant.agent.state.task_state import TaskState # For type hinting if needed for planner

app = FastAPI()

class ActiveShell:
    """
    Manages an active shell process (e.g., pexpect.spawn instance)
    and bridges its I/O with a WebSocket connection using asyncio.
    """
    def __init__(self, process: Any, websocket: WebSocket, loop: asyncio.AbstractEventLoop):
        self.process = process # This should be a pexpect.spawn-like object
        self.websocket = websocket
        self.loop = loop
        self.fd = self.process.child_fd # File descriptor for reading
        self.reader_task: Optional[asyncio.Task] = None

    async def start_reading(self):
        """Starts the background task to read from the shell and send to WebSocket."""
        if self.reader_task is None or self.reader_task.done():
            self.reader_task = self.loop.create_task(self._read_loop())
            print(f"Shell reader task started for fd {self.fd}.")

    async def _read_loop(self):
        """Continuously reads from the shell process and sends data to the WebSocket."""
        try:
            while self.process.isalive():
                # Use run_in_executor for the blocking select call
                readable, _, _ = await self.loop.run_in_executor(
                    None, select.select, [self.fd], [], [], 0.1 # 0.1s timeout
                )
                if readable:
                    try:
                        # Use run_in_executor for the blocking os.read call
                        data = await self.loop.run_in_executor(None, os.read, self.fd, 4096)
                        if data:
                            await self.websocket.send_text(data.decode(errors='replace'))
                        else: # EOF
                            print(f"Shell fd {self.fd} EOF.")
                            break
                    except (BlockingIOError, InterruptedError):
                        await asyncio.sleep(0.01) # Try again shortly
                        continue
                    except Exception as e:
                        print(f"Shell read error on fd {self.fd}: {e}")
                        break
                else:
                    # No data, select timed out, pexpect might need a chance to process internal state
                    await asyncio.sleep(0.01) 

        except asyncio.CancelledError:
            print(f"Shell reader task for fd {self.fd} cancelled.")
        except Exception as e:
            print(f"Unexpected error in shell reader task for fd {self.fd}: {e}")
        finally:
            print(f"Shell read loop ended for fd {self.fd}.")
            # Consider closing WebSocket if shell dies unexpectedly, or notify client
            # await self.websocket.close(code=1011, reason="Shell process terminated")


    async def write(self, data: str):
        """Writes data to the shell process's stdin."""
        if self.process.isalive():
            try:
                # pexpect's send/sendline are typically synchronous.
                # Running in executor if they block significantly.
                # For simple 'send', direct call might be okay if it's just writing to a buffer.
                # self.process.send(data) # For pexpect
                # If self.fd is a true PTY master, os.write is appropriate
                await self.loop.run_in_executor(None, os.write, self.fd, data.encode())

            except Exception as e:
                print(f"Shell write error on fd {self.fd}: {e}")
                # Handle error, maybe close connection

    async def close(self):
        """Closes the shell process and cancels the reader task."""
        print(f"Closing ActiveShell for fd {self.fd}.")
        if self.reader_task and not self.reader_task.done():
            self.reader_task.cancel()
            try:
                await self.reader_task
            except asyncio.CancelledError:
                pass # Expected
        
        if self.process.isalive():
            try:
                # For pexpect, you'd use process.close() or process.terminate()
                # self.process.close(force=True)
                # If it's a raw PTY, os.close(self.fd) might be part of cleanup,
                # but pexpect usually handles its child process.
                # Here we assume pexpect's close() is the right method.
                await self.loop.run_in_executor(None, self.process.close, False) # force=False initially
                if self.process.isalive(): # If still alive, force
                     await self.loop.run_in_executor(None, self.process.close, True)

            except Exception as e:
                print(f"Error closing shell process for fd {self.fd}: {e}")
        print(f"ActiveShell for fd {self.fd} resources released.")


class ConnectionManager:
    def __init__(self):
        self.active_chat_connections: dict[str, WebSocket] = {}
        self.agent_instances: dict[str, tuple[Agent, Computer]] = {}
        # client_id -> { "terminal": ActiveShell, "jupyter": ActiveShell }
        self.active_shells: dict[str, dict[str, ActiveShell]] = {}
        self.loop = asyncio.get_event_loop()

    async def _ensure_agent_computer(self, client_id: str) -> tuple[Optional[Agent], Optional[Computer]]:
        if client_id not in self.agent_instances:
            try:
                print(f"Initializing agent/computer for client {client_id}.")
                agent, computer = await initialize_agent() # From your infant/main.py
                self.agent_instances[client_id] = (agent, computer)
                
                # Ensure Jupyter kernel server is running (idempotent call from infant/main.py)
                # This is typically called within initialize_agent or Computer's init
                # If not, you might need: await computer.start_jupyter_server()
                print(f"Agent/computer initialized for {client_id}.")
                return agent, computer
            except Exception as e:
                print(f"CRITICAL: Error initializing agent/computer for {client_id}: {e}")
                return None, None
        return self.agent_instances[client_id]

    async def connect_chat(self, websocket: WebSocket, client_id: str):
        await websocket.accept()
        self.active_chat_connections[client_id] = websocket
        _, computer = await self._ensure_agent_computer(client_id)
        if not computer: # Failed to initialize
            await websocket.close(code=1011, reason="Agent initialization failed")
            del self.active_chat_connections[client_id] # Clean up
            return
        print(f"Chat client {client_id} connected.")

    async def disconnect_chat(self, client_id: str):
        if client_id in self.active_chat_connections:
            del self.active_chat_connections[client_id]
        print(f"Chat client {client_id} disconnected.")
        await self.cleanup_client_resources_if_idle(client_id)

    async def process_chat_message(self, message: str, client_id: str):
        if client_id in self.agent_instances:
            agent, _ = self.agent_instances[client_id]
            try:
                # Ensure run_single_step is awaitable or adapt if it's synchronous
                print(message)
                agent_response_obj = await run_single_step(agent, user_request_text=message, images=None)
                print(agent_response_obj)
                response_text = ""
                if isinstance(agent_response_obj, dict):
                    # Try to extract a meaningful string representation
                    # This depends heavily on the structure of agent_response_obj
                    if "output" in agent_response_obj:
                        response_text = agent_response_obj["output"]
                    elif "plan" in agent_response_obj:
                         response_text = f"Plan: {agent_response_obj['plan']}"
                    else:
                        response_text = str(agent_response_obj) # Fallback
                elif isinstance(agent_response_obj, str):
                    response_text = agent_response_obj
                else:
                    response_text = str(agent_response_obj)

                await self.active_chat_connections[client_id].send_text(f"Agent: {response_text}")

            except Exception as e:
                print(f"Error processing chat message for agent {client_id}: {e}")
                await self.active_chat_connections[client_id].send_text(f"Error: Could not process message due to: {e}")
        else:
            await self.active_chat_connections[client_id].send_text("Error: Agent not initialized for chat.")

    async def connect_shell(self, websocket: WebSocket, client_id: str, shell_type: str):
        await websocket.accept()
        _, computer = await self._ensure_agent_computer(client_id)

        if not computer:
            await websocket.close(code=1011, reason="Agent/Computer initialization failed.")
            return

        # Ensure the computer's interactive SSH shell is ready.
        # The infant.computer.Computer.connect_ssh() initializes self.ssh_interactive_shell.
        # It uses pexpect.spawn(ssh_command...)
        if not computer.ssh_interactive_shell or not computer.ssh_interactive_shell.process.isalive():
            try:
                print(f"Re-establishing SSH interactive shell for {client_id} for {shell_type}.")
                await self.loop.run_in_executor(None, computer.connect_ssh) # connect_ssh is synchronous
            except Exception as e:
                print(f"Failed to establish SSH interactive shell for {client_id} ({shell_type}): {e}")
                await websocket.close(code=1011, reason="Shell backend SSH error")
                return
        
        pexpect_process = None
        if shell_type == "terminal":
            # For the terminal, we directly use the main interactive shell.
            # WARNING: This is a simplified approach. Ideally, you'd spawn a new, dedicated pexpect
            # session for each terminal, not share the agent's primary one.
            pexpect_process = computer.ssh_interactive_shell.process
            print(f"Terminal for {client_id} using agent's main interactive shell process.")
            # If the shell was just (re)created, it might have login banners.
            # You might want to consume initial output here before handing over.
            # await asyncio.sleep(0.5) # give it a moment to settle
            # initial_output = await self.loop.run_in_executor(None, pexpect_process.read_nonblocking, 4096, 1)
            # if initial_output:
            #     await websocket.send_text(initial_output.decode(errors='replace'))


        elif shell_type == "jupyter":
            # For Jupyter, run the execute_cli.py in interactive mode within the SSH shell.
            # The Jupyter Kernel Gateway (execute_server.py) must be running in the Docker env.
            # initialize_computer -> computer.start_jupyter_server() handles this.
            kernel_id = f"kernel_{client_id}_{shell_type.replace('-', '_')}" # Ensure valid kernel_id chars
            jupyter_cmd = f"python -u -m infant.tools.code_execute.execute_cli --kernel-id {kernel_id} --interactive\n"
            print(f"Starting Jupyter CLI for {client_id} with command: {jupyter_cmd.strip()}")
            
            # This sends the command to the *existing* interactive shell.
            # Output from this Jupyter CLI will be mixed with other shell output if not careful.
            # A dedicated pexpect process is much cleaner:
            # e.g., pexpect_process = await self.loop.run_in_executor(None, computer.pexpect_spawn_new_command, jupyter_cmd)
            # For now, sending to the main shell:
            await self.loop.run_in_executor(None, computer.ssh_interactive_shell.process.sendline, jupyter_cmd)
            pexpect_process = computer.ssh_interactive_shell.process # Still using the main shell's pexpect instance
            print(f"Jupyter CLI for {client_id} running in agent's main interactive shell.")


        if not pexpect_process or not pexpect_process.isalive():
            err_msg = f"Failed to obtain a live pexpect process for {shell_type} on client {client_id}."
            print(err_msg)
            await websocket.close(code=1011, reason=err_msg)
            return

        active_shell_instance = ActiveShell(pexpect_process, websocket, self.loop)
        
        if client_id not in self.active_shells:
            self.active_shells[client_id] = {}
        # Close any existing shell of the same type for this client
        if shell_type in self.active_shells[client_id]:
             print(f"Closing pre-existing {shell_type} shell for {client_id}.")
             await self.active_shells[client_id][shell_type].close()

        self.active_shells[client_id][shell_type] = active_shell_instance
        await active_shell_instance.start_reading()
        print(f"{shell_type.capitalize()} shell WebSocket connected for client {client_id}")

    async def disconnect_shell(self, client_id: str, shell_type: str):
        if client_id in self.active_shells and shell_type in self.active_shells[client_id]:
            shell = self.active_shells[client_id][shell_type]
            await shell.close()
            del self.active_shells[client_id][shell_type]
            if not self.active_shells[client_id]: # No more shells for this client type
                del self.active_shells[client_id]
        print(f"{shell_type.capitalize()} shell for client {client_id} disconnected.")
        await self.cleanup_client_resources_if_idle(client_id)

    async def forward_to_shell(self, data: str, client_id: str, shell_type: str):
        if client_id in self.active_shells and shell_type in self.active_shells[client_id]:
            shell = self.active_shells[client_id][shell_type]
            if shell.process.isalive():
                await shell.write(data)
            else:
                print(f"Cannot forward to {shell_type} shell: process is not alive for client {client_id}")
                # Optionally notify the WebSocket client
                await shell.websocket.close(1011, "Shell process terminated unexpectedly.")
                await self.disconnect_shell(client_id, shell_type) # Cleanup
        else:
            # This case should ideally not happen if disconnect cleans up properly
            print(f"Cannot forward to {shell_type} shell: No active shell for client {client_id}")


    async def cleanup_client_resources_if_idle(self, client_id: str):
        has_chat = client_id in self.active_chat_connections
        has_shells = client_id in self.active_shells and bool(self.active_shells[client_id])
        
        if not has_chat and not has_shells:
            if client_id in self.agent_instances:
                agent, computer = self.agent_instances[client_id]
                print(f"Cleaning up all resources for idle client {client_id}.")
                
                # Close computer's interactive SSH shell if it's open
                if computer.ssh_interactive_shell and computer.ssh_interactive_shell.process.isalive():
                    print(f"Closing main interactive shell for computer of client {client_id}.")
                    await self.loop.run_in_executor(None, computer.ssh_interactive_shell.close)

                # Terminate SSH tunnel process if it's running
                if computer.ssh_tunnel_proc and computer.ssh_tunnel_proc.poll() is None:
                    print(f"Terminating SSH tunnel for computer of client {client_id}.")
                    computer.ssh_tunnel_proc.terminate()
                    try:
                        await self.loop.run_in_executor(None, computer.ssh_tunnel_proc.wait, 5)
                    except subprocess.TimeoutExpired:
                        computer.ssh_tunnel_proc.kill()
                
                # Add any other agent-specific cleanup if necessary
                # e.g., agent.cleanup()

                del self.agent_instances[client_id]
                print(f"All resources for client {client_id} cleaned up.")

manager = ConnectionManager()

# --- WebSocket Endpoints ---
@app.websocket("/ws/chat/{client_id}")
async def websocket_chat_endpoint(websocket: WebSocket, client_id: str):
    await manager.connect_chat(websocket, client_id)
    print(websocket.client_state)
    if not websocket.client_state == 'connected': return # Connection failed in connect_chat
    try:
        while True:
            data = await websocket.receive_text()
            print(data)
            await manager.process_chat_message(data, client_id)
    except WebSocketDisconnect:
        print(f"Chat WebSocket for {client_id} disconnected by client.")
    except Exception as e:
        print(f"Error in chat WebSocket for {client_id}: {e}")
    finally:
        await manager.disconnect_chat(client_id)

@app.websocket("/ws/terminal/{client_id}")
async def websocket_terminal_endpoint(websocket: WebSocket, client_id: str):
    await manager.connect_shell(websocket, client_id, "terminal")
    if not websocket.client_state == 'connected': return

    try:
        while True:
            data = await websocket.receive_text()
            await manager.forward_to_shell(data, client_id, "terminal")
    except WebSocketDisconnect:
        print(f"Terminal WebSocket for {client_id} disconnected by client.")
    except Exception as e:
        print(f"Error in terminal WebSocket for {client_id}: {e}")
    finally:
        await manager.disconnect_shell(client_id, "terminal")

@app.websocket("/ws/jupyter/{client_id}")
async def websocket_jupyter_endpoint(websocket: WebSocket, client_id: str):
    await manager.connect_shell(websocket, client_id, "jupyter")
    if not websocket.client_state == 'connected': return

    try:
        while True:
            data = await websocket.receive_text() # Input from xterm.js (Jupyter console)
            await manager.forward_to_shell(data, client_id, "jupyter")
    except WebSocketDisconnect:
        print(f"Jupyter WebSocket for {client_id} disconnected by client.")
    except Exception as e:
        print(f"Error in Jupyter WebSocket for {client_id}: {e}")
    finally:
        await manager.disconnect_shell(client_id, "jupyter")

# --- HTTP API Endpoints ---
@app.get("/api/planner/{client_id}")
async def get_planner_info(client_id: str):
    if client_id not in manager.agent_instances:
        # Try to initialize if not present, e.g. if planner is accessed before chat/shell
        # This might be desired if planner can be viewed independently.
        # For now, assume agent must be active from a WS connection first.
        raise HTTPException(status_code=404, detail="Agent not found for client_id. Establish a WebSocket connection first.")

    agent, _ = manager.agent_instances[client_id]
    if hasattr(agent, 'state') and hasattr(agent.state, 'task_state'):
        task_state = agent.state.task_state # This is an instance of infant.agent.state.task_state.TaskState
        
        # Serialize TaskState to a dictionary
        # This depends on the attributes of your TaskState class
        sub_tasks_data = []
        if hasattr(task_state, 'sub_tasks') and isinstance(task_state.sub_tasks, list):
            for sub_task in task_state.sub_tasks:
                # Assuming sub_task is an object with attributes like 'description', 'status', 'tool_input_preview', etc.
                # Or if it's a dictionary already.
                if isinstance(sub_task, dict):
                    sub_tasks_data.append(sub_task)
                elif hasattr(sub_task, '__dict__'): # Basic object to dict
                    sub_tasks_data.append(vars(sub_task))
                else:
                    sub_tasks_data.append(str(sub_task)) # Fallback

        planner_data = {
            "goal": getattr(task_state, 'goal', None),
            "main_task_assessment": getattr(task_state, 'main_task_assessment', None),
            "sub_tasks": sub_tasks_data,
            "current_sub_task_index": getattr(task_state, 'current_sub_task_index', None),
            "status": str(getattr(task_state, 'status', None)), # Enum to string
            "last_error": getattr(task_state, 'last_error', None),
        }
        return planner_data
    else:
        raise HTTPException(status_code=404, detail="Task state not found for agent.")

# To run this (save as main_api.py):
# pip install fastapi "uvicorn[standard]" pexpect python-dotenv # Add any other infantagent deps
# uvicorn infant.server:app --reload --ws-ping-interval 20 --ws-ping-timeout 20 --port 4000