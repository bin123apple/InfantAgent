import asyncio
import websockets

async def test_ws_chat():
    uri = "ws://localhost:4000/ws/chat/testuser"
    async with websockets.connect(uri) as websocket:
        print("Connected to chat WebSocket.")
        await websocket.send("Hello from test client!")
        print("Sent: Hello from test client!")
        try:
            while True:
                response = await websocket.recv()
                print(f"Received: {response}")
        except websockets.exceptions.ConnectionClosed:
            print("WebSocket closed.")

if __name__ == "__main__":
    asyncio.run(test_ws_chat())
