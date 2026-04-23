import os
import re
import sys
import asyncio
import httpx
from multidict import CIMultiDict
import aiohttp
from http.cookies import SimpleCookie
import logging
from aiohttp import ClientSession, TCPConnector, WSMsgType
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, UploadFile, Response, File
from fastapi.responses import RedirectResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.cors import CORSMiddleware
from infant.agent.memory.memory import CmdRun, IPythonRun, Task, TaskFinish
import infant.util.constant as constant
from infant.config import Config 

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from infant.main import initialize_agent, run_single_step, cleanup


agent = None
computer = None
config = Config()

app = FastAPI()

upstream_http = httpx.AsyncClient(verify=False, follow_redirects=True)
upstream_aiohttp = None

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    global upstream_aiohttp
    upstream_aiohttp = ClientSession(connector=TCPConnector(ssl=False))
    logger.info("[WS] connecting to {url}")


@app.on_event("shutdown")
async def shutdown_event():
    try:
        # Close HTTP clients
        try:
            await upstream_http.aclose()
        except Exception as e:
            logger.error(f"Error closing HTTP client: {str(e)}")
            
        try:
            if 'upstream_aiohttp' in globals() and upstream_aiohttp and not upstream_aiohttp.closed:
                await upstream_aiohttp.close()
        except Exception as e:
            logger.error(f"Error closing aiohttp session: {str(e)}")
            
    except Exception as e:
        logger.error(f"Unexpected error during shutdown: {str(e)}")
    finally:
        # Ensure cleanup is called
        try:
            if cleanup:
                if agent and computer:
                    await cleanup(agent=agent, computer=computer)
                else:
                    await cleanup()
        except Exception as e:
            logger.error(f"Error during cleanup: {str(e)}")

# Redirect to frontend
@app.get("/", name="root_frontend")
async def root_frontend():
    return RedirectResponse(url="/frontend/index.html")

# Static files
app.mount("/frontend", StaticFiles(directory="frontend"), name="frontend")

# Status API
@app.get("/api/guacamole-token")
async def guacamole_token():
    """Get a fresh Guacamole auth token for the iframe."""
    try:
        resp = await upstream_http.post(
            "http://infant-computer:8080/guacamole/api/tokens",
            data={"username": "web", "password": "web"},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        if resp.status_code == 200:
            data = resp.json()
            return {"success": True, "token": data["authToken"]}
        return {"success": False, "error": f"Guacamole returned {resp.status_code}"}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.get("/api/status")
async def status():
    if agent:
        return {
            "success": True,
            "status": "ready",
            "currentTask": "none",
            "model": agent.planning_llm.model_name,
            "sessionActive": True,
        }
    return {"success": True, "status": "ready", "currentTask": "none", "model": "demo", "sessionActive": False}

# Chat API
@app.post("/api/chat")
async def chat(data: dict):
    user_message = data.get('message', '')
    if not user_message:
        return {"success": False, "error": "No message provided"}
    if agent and run_single_step:
        try:
            response = await run_single_step(agent, user_message)
            return {"success": True, "response": response, "status": "completed"}
        except Exception as e:
            logger.error(f"Error in chat: {e}")
            return {"success": False, "error": str(e)}
    await asyncio.sleep(1)
    return {"success": True, "response": f"Demo mode: Received '{user_message}'", "status": "completed"}

# Reset API
@app.post("/api/reset")
async def reset():
    if agent:
        agent.state.reset()
        for llm in agent._active_llms():
            llm.metrics.accumulated_cost = 0
        computer.execute(f'cd {computer.computer_workspace_dir} && rm -rf *')
        return {"success": True, "message": "Conversation reset successfully"}
    await asyncio.sleep(0.5)
    return {"success": True, "message": "Demo mode reset"}

# Settings API
@app.post("/api/settings")
async def settings(data: dict):
    global config, agent, computer
    # Load base config from config.toml first
    try:
        user_config = config._load()
        config.__dict__.update(user_config)
    except FileNotFoundError:
        logger.warning("config.toml not found, using defaults")
    # Apply frontend settings
    if data.get('model'):
        config.model = data.get('model')
    if data.get('apiKey'):
        config.api_key = data.get('apiKey')
    if data.get('temperature') is not None:
        config.temperature = float(data.get('temperature'))
    if data.get('maxTokens') is not None:
        config.max_output_tokens = int(data.get('maxTokens'))
    # Finalize config (resolves paths, SSH settings, etc.)
    config.finalize_config()
    if agent:
        await agent.update_agent_config(config)
        return {"success": True, "message": "Agent updated", "appliedSettings": data}
    return {"success": True, "message": "Agent initialized", "appliedSettings": data}

@app.get("/api/initialize")
async def initialize():
    global agent, computer
    agent, computer = await initialize_agent(config)
    return {"success": True, "message": "Agent initialized successfully"}


@app.get("/api/memory")
async def memory():
    if not agent:
        return {"success": False, "error": "Agent not initialized"}

    tasks, commands, codes, memories = [], [], [], []
    task_counter = 0
    for idx, mem in enumerate(agent.state.memory_list):
        # 1) 旧的三种类型
        if isinstance(mem, Task):
            # 1) 计算该 Task 在所有 Task 中的 ID（从 0 开始）
            task_id = task_counter
            task_counter += 1

            status = 'pending'
            for later in agent.state.memory_list[idx:]:
                if isinstance(later, TaskFinish):
                    status = 'completed'
                    break

            # 3) 把 id、name、status 一起放到 tasks 里
            tasks.append({
                'id':     task_id,
                'name':   mem.task,
                'status': status
            })
        elif isinstance(mem, CmdRun):
            commands.append({"command": mem.command})
            if mem.result:
                commands[-1]["result"] = mem.result
        elif isinstance(mem, IPythonRun):
            codes.append({"code": mem.code})
            if mem.result:
                codes[-1]["result"] = mem.result
        # 2) 其它所有 memory
        mem_dict = {
            "id":       idx,
            "category": type(mem).__name__,
            "content":  getattr(mem, "content", repr(mem))
        }
        mem_dict.update(mem.__dict__)
        if hasattr(mem, "result"):
            mem_dict["result"] = getattr(mem, "result")
        memories.append(mem_dict)

    output = {
        "success":  True,
        "tasks":    tasks,
        "commands": commands,
        "codes":    codes,
        "memories": memories,
    }
    return output


# File Upload API
@app.post("/api/upload")
async def upload(files: list[UploadFile] = File(...)):
    global computer
    uploaded_files = []
    try:
        os.makedirs(computer.workspace_mount_path, exist_ok=True)
        for file in files:
            file_location = os.path.join(computer.workspace_mount_path, file.filename)
            os.makedirs(os.path.dirname(file_location), exist_ok=True)  
            with open(file_location, "wb") as buffer:
                buffer.write(await file.read())
            uploaded_files.append(f"Uploaded file: {file.filename}")
        return {"success": True, "uploaded_files": uploaded_files}
    except Exception as e:
        return {"success": False, "error": str(e)}

# 在你的backend.py中添加以下API

# Tasks监控API - 获取所有Task类型的memory
@app.get("/api/tasks")
async def get_tasks():
    """获取所有Task类型的memory项目"""
    if not agent:
        return {"success": True, "tasks": [], "debug": "Agent not initialized"}
    
    tasks = []
    debug_info = []
    
    # 导入Task类 (根据你的实际导入路径调整)
    try:
        from infant.agent.memory.memory import Task
        task_class_available = True
    except ImportError:
        # 如果导入失败，尝试其他可能的路径
        try:
            task_class_available = True
        except ImportError:
            Task = None
            task_class_available = False
    
    # 先获取所有memory信息用于调试
    for i, mem in enumerate(agent.state.memory_list):
        mem_info = {
            'index': i,
            'class': mem.__class__.__name__,
            'module': mem.__class__.__module__,
            'attributes': [attr for attr in dir(mem) if not attr.startswith('_')],
        }
        
        # 添加常见属性的值
        for attr in ['name', 'status', 'description', 'type']:
            if hasattr(mem, attr):
                mem_info[f'has_{attr}'] = True
                mem_info[attr] = str(getattr(mem, attr))
            else:
                mem_info[f'has_{attr}'] = False
                
        debug_info.append(mem_info)
        
        # 判断是否为Task类型
        is_task = False
        
        if task_class_available and Task and isinstance(mem, Task):
            # 方法1: 直接isinstance检查
            is_task = True
        elif mem.__class__.__name__ == 'Task':
            # 方法2: 类名精确匹配
            is_task = True
        elif 'task' in mem.__class__.__name__.lower():
            # 方法3: 类名包含task
            is_task = True
        
        if is_task:
            task_data = {
                'id': getattr(mem, 'id', i),
                'name': getattr(mem, 'name', f'Task {i}'),
                'task': getattr(mem, 'task', 'unknown')
            }
            
            # 添加时间相关字段
            for time_attr in ['created_at', 'completed_at', 'updated_at']:
                if hasattr(mem, time_attr):
                    task_data[time_attr] = str(getattr(mem, time_attr))
                else:
                    task_data[time_attr] = None
                    
            tasks.append(task_data)
    
    return {
        "success": True, 
        "tasks": tasks,
        "debug": {
            "memory_count": len(agent.state.memory_list),
            "task_count": len(tasks),
            "task_class_available": task_class_available,
            "memory_details": debug_info[:5]  # 只返回前5个用于调试
        }
    }

# Tasks监控API - SSE版本（用于实时更新）
@app.get("/api/tasks/stream")
async def stream_tasks(request: Request):
    """实时流式传输Task更新"""
    
    # 尝试导入Task类
    try:
        from infant.agent.memory.memory import Task
        task_class_available = True
    except ImportError:
        try:
            task_class_available = True
        except ImportError:
            Task = None
            task_class_available = False
    
    async def generate_tasks():
        last_task_count = 0
        last_tasks = []
        
        while True:
            try:
                if agent and agent.state.memory_list:
                    current_tasks = []
                    for i, mem in enumerate(agent.state.memory_list):
                        # 判断是否为Task类型
                        is_task = False
                        
                        if task_class_available and Task and isinstance(mem, Task):
                            is_task = True
                        elif mem.__class__.__name__ == 'Task':
                            is_task = True
                        elif 'task' in mem.__class__.__name__.lower():
                            is_task = True
                        
                        if is_task:
                            task_data = {
                                'id': getattr(mem, 'id', i),
                                'name': getattr(mem, 'name', f'Task {i}'),
                                'task': getattr(mem, 'task', 'unknown')
                            }
                            
                            # 添加时间相关字段
                            for time_attr in ['created_at', 'completed_at', 'updated_at']:
                                if hasattr(mem, time_attr):
                                    task_data[time_attr] = str(getattr(mem, time_attr))
                                else:
                                    task_data[time_attr] = None
                                    
                            current_tasks.append(task_data)
                    
                    # 检查是否有变化
                    if len(current_tasks) != last_task_count or current_tasks != last_tasks:
                        import json
                        data = json.dumps({"tasks": current_tasks})
                        yield f"data: {data}\n\n"
                        last_task_count = len(current_tasks)
                        last_tasks = current_tasks.copy()
                
                await asyncio.sleep(1)  # 每秒检查一次
                
            except Exception as e:
                logger.error(f"Error in task stream: {e}")
                import json
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
                await asyncio.sleep(5)
    
    return StreamingResponse(
        generate_tasks(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )

# 添加Task操作API
@app.post("/api/tasks/{task_id}/complete")
async def complete_task(task_id: int):
    """标记Task为完成状态"""
    if not agent:
        return {"success": False, "error": "Agent not initialized"}
    
    # 查找对应的task memory并更新状态
    for mem in agent.state.memory_list:
        if hasattr(mem, 'id') and mem.id == task_id:
            if hasattr(mem, 'status'):
                mem.status = 'completed'
                if hasattr(mem, 'completed_at'):
                    from datetime import datetime
                    mem.completed_at = datetime.now().isoformat()
                return {"success": True, "message": f"Task {task_id} marked as completed"}
    
    return {"success": False, "error": f"Task {task_id} not found"}

@app.delete("/api/tasks/{task_id}")
async def delete_task(task_id: int):
    """删除指定的Task"""
    if not agent:
        return {"success": False, "error": "Agent not initialized"}
    
    # 查找并删除对应的task memory
    for i, mem in enumerate(agent.state.memory_list):
        if hasattr(mem, 'id') and mem.id == task_id:
            agent.state.memory_list.pop(i)
            return {"success": True, "message": f"Task {task_id} deleted"}
    
    return {"success": False, "error": f"Task {task_id} not found"}


logger = logging.getLogger("proxydbg")
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
logger.addHandler(handler)

# ——————————————
# global upstream sessions
# ——————————————
# upstream_http = httpx.AsyncClient(verify=False, follow_redirects=True)
# upstream_aiohttp = ClientSession(connector=TCPConnector(ssl=False))

# @app.on_event("shutdown")
# async def shutdown_sessions():
#     logger.debug("Shutting down upstream sessions")
#     await upstream_http.aclose()
#     await upstream_aiohttp.close()

# ——————————————
# helper to collect sid
# ——————————————
def get_forward_params(request: Request):
    params = dict(request.query_params)
    if "sid" not in params and "sid" in request.cookies:
        params["sid"] = request.cookies["sid"]
    return params

# ——————————————
# root: handled by root_frontend above
# ——————————————

# ——————————————
# SSE proxy
# ——————————————
@app.get("/gui/event")
async def sse(request: Request):
    params = get_forward_params(request)
    logger.debug(f"[SSE] path={request.url.path} params={params} cookies={dict(request.cookies)}")
    upstream = await upstream_aiohttp.get(
        f"https://infant-computer:8080{request.url.path}",
        params=params,
        ssl=False
    )
    logger.debug(f"[SSE upstream] status={upstream.status} headers={dict(upstream.headers)}")

    async def gen():
        async for chunk in upstream.content.iter_chunked(1024):
            yield chunk

    return StreamingResponse(gen(), media_type="text/event-stream")

# ——————————————
# WebSocket proxy
# ——————————————
@app.websocket("/gui/event")
async def ws_proxy(ws: WebSocket):
    await ws.accept()
    sid = ws.query_params.get("sid") or ws.cookies.get("sid")
    url = f"wss://infant-computer:8080{ws.url.path}" + (f"?sid={sid}" if sid else "")
    logger.debug(f"[WS] connecting to {url}")
    upstream = await upstream_aiohttp.ws_connect(url, ssl=False)
    logger.debug("[WS upstream] connected")

    async def to_up():
        async for msg in upstream:
            logger.debug(f"[WS ← upstream] type={msg.type} len={len(msg.data)}")
            if msg.type == WSMsgType.TEXT:
                await ws.send_text(msg.data)
            else:
                await ws.send_bytes(msg.data)

    async def to_client():
        while True:
            m = await ws.receive()
            logger.debug(f"[WS → upstream] {m}")
            if m["type"] == "websocket.receive":
                if "text" in m:
                    await upstream.send_str(m["text"])
                else:
                    await upstream.send_bytes(m["bytes"])
            else:
                break

    await asyncio.gather(to_up(), to_client())
    await upstream.close()

# ——————————————
# HTTP proxy for /gui/*
# ——————————————
@app.api_route("/gui/{full_path:path}", methods=["GET","POST","HEAD","OPTIONS"])
async def gui_proxy(request: Request, full_path: str):
    params = get_forward_params(request)
    upstream_url = f"https://infant-computer:8080/gui/{full_path}"
    logger.debug(f"[HTTP] {request.method} {upstream_url} params={params} headers={dict(request.headers)}")

    resp_up = await upstream_http.request(
        method=request.method,
        url=upstream_url,
        params=params,
        content=await request.body(),
        headers={k:v for k,v in request.headers.items() if k.lower()!="host"},
    )
    logger.debug(f"[HTTP upstream] status={resp_up.status_code} headers={dict(resp_up.headers)}")

    # strip X-Frame-Options
    headers = {
        k: v for k, v in resp_up.headers.multi_items()
        if k.lower() not in ("x-frame-options",)
    }

    # rewrite Set-Cookie to proxy domain
    cookies = resp_up.headers.get_list("set-cookie")
    if cookies:
        logger.debug(f"[HTTP upstream] set-cookie={cookies}")
    for raw in cookies:
        c = SimpleCookie()
        c.load(raw)
        for morsel in c.values():
            cookie_str = (
                f"{morsel.key}={morsel.value}; "
                f"Path={morsel['path'] or '/'}; HttpOnly; Domain=127.0.0.1"
            )
            logger.debug(f"[HTTP] rewriting cookie: {cookie_str}")
            headers.setdefault("set-cookie", cookie_str)

    return Response(
        content=resp_up.content,
        status_code=resp_up.status_code,
        headers=headers,
        media_type=resp_up.headers.get("content-type"),
    )

# ——————————————
# Guacamole HTTP proxy
# ——————————————
@app.api_route("/guacamole/{full_path:path}", methods=["GET","POST","PUT","DELETE","HEAD","OPTIONS"])
async def guacamole_proxy(request: Request, full_path: str):
    params = get_forward_params(request)
    upstream_url = f"http://infant-computer:8080/guacamole/{full_path}"
    logger.debug(f"[guacamole] {request.method} {upstream_url} params={params}")

    body = await request.body()
    fwd_headers = {
        k: v for k, v in request.headers.items()
        if k.lower() not in ("host", "content-length", "transfer-encoding")
    }
    resp_up = await upstream_http.request(
        method=request.method,
        url=upstream_url,
        params=params,
        content=body,
        headers=fwd_headers,
    )
    logger.debug(f"[guacamole upstream] status={resp_up.status_code}")

    headers = {
        k: v for k, v in resp_up.headers.multi_items()
        if k.lower() not in ("x-frame-options", "content-security-policy", "set-cookie")
    }

    # Rewrite Set-Cookie: drop the upstream Domain (so the cookie attaches to our
    # proxy host), but preserve SameSite/Secure/HttpOnly/Path as set by Guacamole.
    cookies = resp_up.headers.get_list("set-cookie")
    rewritten = []
    for raw in cookies:
        c = SimpleCookie()
        try:
            c.load(raw)
        except Exception:
            rewritten.append(raw)
            continue
        for morsel in c.values():
            parts = [f"{morsel.key}={morsel.value}"]
            parts.append(f"Path={morsel['path'] or '/'}")
            if morsel["expires"]:
                parts.append(f"Expires={morsel['expires']}")
            if morsel["max-age"]:
                parts.append(f"Max-Age={morsel['max-age']}")
            if morsel["samesite"]:
                parts.append(f"SameSite={morsel['samesite']}")
            if morsel["secure"]:
                parts.append("Secure")
            if morsel["httponly"]:
                parts.append("HttpOnly")
            rewritten.append("; ".join(parts))
    if rewritten:
        # Starlette's Response needs a MutableHeaders to send multiple Set-Cookie lines.
        resp = Response(
            content=resp_up.content,
            status_code=resp_up.status_code,
            headers=headers,
            media_type=resp_up.headers.get("content-type"),
        )
        for ck in rewritten:
            resp.raw_headers.append((b"set-cookie", ck.encode("latin-1")))
        return resp

    return Response(
        content=resp_up.content,
        status_code=resp_up.status_code,
        headers=headers,
        media_type=resp_up.headers.get("content-type"),
    )

# ——————————————
# Guacamole WebSocket proxy
# ——————————————
@app.websocket("/guacamole/websocket-tunnel")
async def guacamole_ws_proxy(ws: WebSocket):
    # Guacamole's guacamole-common-js WebSocketTunnel connects with subprotocol
    # "guacamole". The server MUST echo it back or the browser fails the handshake.
    requested_protocols = ws.headers.get("sec-websocket-protocol", "")
    client_protocols = [p.strip() for p in requested_protocols.split(",") if p.strip()]
    selected = "guacamole" if "guacamole" in client_protocols else (client_protocols[0] if client_protocols else None)

    params = dict(ws.query_params)
    qs = "&".join(f"{k}={v}" for k, v in params.items())
    url = f"ws://infant-computer:8080/guacamole/websocket-tunnel" + (f"?{qs}" if qs else "")
    logger.debug(f"[guacamole WS] connecting to {url} protocols={client_protocols}")

    # Forward the browser's Cookie header so upstream session state stays consistent.
    upstream_headers = {}
    cookie = ws.headers.get("cookie")
    if cookie:
        upstream_headers["Cookie"] = cookie

    upstream = await upstream_aiohttp.ws_connect(
        url,
        ssl=False,
        protocols=client_protocols or (),
        headers=upstream_headers or None,
    )
    logger.debug(f"[guacamole WS] connected upstream protocol={upstream.protocol}")

    # Prefer the subprotocol the upstream actually selected; fall back to our guess.
    accept_protocol = upstream.protocol or selected
    await ws.accept(subprotocol=accept_protocol)

    closed = asyncio.Event()

    async def up_to_client():
        try:
            async for msg in upstream:
                if closed.is_set():
                    break
                if msg.type == WSMsgType.TEXT:
                    await ws.send_text(msg.data)
                elif msg.type == WSMsgType.BINARY:
                    await ws.send_bytes(msg.data)
                elif msg.type in (WSMsgType.CLOSE, WSMsgType.CLOSING, WSMsgType.CLOSED):
                    break
        except Exception:
            pass
        finally:
            closed.set()

    async def client_to_up():
        try:
            while not closed.is_set():
                m = await ws.receive()
                if m["type"] == "websocket.receive":
                    if "text" in m:
                        await upstream.send_str(m["text"])
                    else:
                        await upstream.send_bytes(m["bytes"])
                else:
                    break
        except (WebSocketDisconnect, Exception):
            pass
        finally:
            closed.set()

    try:
        await asyncio.gather(up_to_client(), client_to_up())
    except Exception:
        pass
    finally:
        if not upstream.closed:
            await upstream.close()

# ——————————————
# proxy for /nxplayer/* (Web Player assets)
# ——————————————
@app.api_route("/nxplayer/{full_path:path}", methods=["GET","HEAD","OPTIONS"])
async def nxplayer_proxy(request: Request, full_path: str):
    upstream_url = f"https://infant-computer:8080/nxplayer/{full_path}"
    logger.debug(f"[nxplayer] {request.method} {upstream_url}")
    resp_up = await upstream_http.request(
        method=request.method,
        url=upstream_url,
        params=request.query_params,
        content=await request.body(),
        headers={k:v for k,v in request.headers.items() if k.lower()!="host"},
    )
    logger.debug(f"[nxplayer upstream] status={resp_up.status_code}")
    headers = {
        k: v for k, v in resp_up.headers.items()
        if k.lower() not in ("x-frame-options",)
    }
    return Response(
        content=resp_up.content,
        status_code=resp_up.status_code,
        headers=headers,
        media_type=resp_up.headers.get("content-type"),
    )
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("BACKEND_PORT", "8008"))
    print(f"Starting server on http://localhost:{port}")
    uvicorn.run("backend:app", host="0.0.0.0", port=port, reload=True)
