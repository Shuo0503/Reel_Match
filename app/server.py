import asyncio
import json
import logging
from pathlib import Path
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.types import Scope

from agents import Runner, OpenAIConversationsSession

from agent import get_starting_agent


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AgentsWebSocketManager:
    def __init__(self):
        self.active_sessions: dict[str, OpenAIConversationsSession] = {}
        self.agents: dict[str, Any] = {}
        self.websockets: dict[str, WebSocket] = {}
        self.session_states: dict[str, dict] = {}

    async def connect(self, websocket: WebSocket, session_id: str):
        await websocket.accept()
        self.websockets[session_id] = websocket

        agent = get_starting_agent()
        session = OpenAIConversationsSession()

        self.active_sessions[session_id] = session
        self.agents[session_id] = agent

        self.session_states[session_id] = {
            "user1_genre": None,
            "user1_location": None,
            "user2_genre": None,
            "user2_location": None,
            "current_step": 0,  
        }
        logger.info(f"✅ Session {session_id} connected with agent: {agent.name}")

        # Send initial greeting
        asyncio.create_task(self._send_initial_greeting(session_id))
    
    async def disconnect(self, session_id: str):
        if session_id in self.active_sessions:
            del self.active_sessions[session_id]
        if session_id in self.agents:
            del self.agents[session_id]
        if session_id in self.websockets:
            del self.websockets[session_id]
        if session_id in self.session_states:
            del self.session_states[session_id]
        logger.info(f"Session {session_id} disconnected")

    async def send_user_message(self, session_id: str, message_text: str):
        """Send a user message and stream the response."""
        session = self.active_sessions.get(session_id)
        websocket = self.websockets.get(session_id)
        
        if not session or not websocket:
            logger.warning("No active session for sending message")
            return
        
        logger.info(f"Sending user message: {message_text}")
        asyncio.create_task(self._run_agent_and_stream(session_id, message_text))

    async def _send_initial_greeting(self, session_id: str):
        """Send initial greeting from the agent."""
        session = self.active_sessions.get(session_id)
        websocket = self.websockets.get(session_id)
        
        if not session or not websocket:
            return
        
        #  Trigger initial greeting with empty input
        await self._run_agent_and_stream(session_id, "")

    async def _run_agent_and_stream(self, session_id: str, user_input: str):
        """Run the agent and stream the response."""
        session = self.active_sessions.get(session_id)
        agent = self.agents.get(session_id)
        websocket = self.websockets.get(session_id)
        
        if not session or not agent or not websocket:
            return
        
        try:
            # Use Runner.run_streamed as a class method
            result = Runner.run_streamed(agent, input=user_input, session=session)
            async for event in result.stream_events():
                event_type = getattr(event, "type", None)
                logger.info(f"📨 MODEL EVENT: {event_type}")
                
                # Handle raw_response_event with ResponseTextDeltaEvent
                if event_type == "raw_response_event":
                    data = getattr(event, "data", None)
                    if data and hasattr(data, "delta"):
                        await websocket.send_text(
                            json.dumps({
                                "type": "assistant_response_delta",
                                "text": data.delta,
                            })
                        )
                # Handle run_item_event for completion
                elif event_type == "run_item_event":
                    item = getattr(event, "item", None)
                    if item and hasattr(item, "type"):
                        if item.type == "message" and hasattr(item, "content"):
                            # Extract text from message content
                            text_parts = []
                            if isinstance(item.content, list):
                                for content_item in item.content:
                                    if hasattr(content_item, "text"):
                                        text_parts.append(content_item.text)
                            text = "".join(text_parts)
                            if text:
                                await websocket.send_text(
                                    json.dumps({
                                        "type": "assistant_response",
                                        "text": text,
                                    })
                                )
                # Handle run completion
                elif event_type == "run_complete":
                    await websocket.send_text(
                        json.dumps({"type": "response_complete"})
                    )
        except Exception as e:
            logger.error(f"Error streaming response for session {session_id}: {e}", exc_info=True)



manager = AgentsWebSocketManager()


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(lifespan=lifespan)


@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await manager.connect(websocket, session_id)
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)

            if message["type"] == "text":
                user_text = message["text"]
                logger.info(f"💬 Received from user: {user_text}")

                await manager.send_user_message(session_id, user_text)

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for session {session_id}")
        await manager.disconnect(session_id)
    except Exception as e:
        logger.error(f"WebSocket error: {e}", exc_info=True)
        await manager.disconnect(session_id)


class CustomStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope: Scope) -> FileResponse:
        response = await super().get_response(path, scope)
        print(f"path: ${path}")
        if path.endswith(".js"):
            response.headers["Content-Type"] = "application/javascript"
        return response


@app.get("/")
async def read_index():
    return FileResponse("static/index.html")


@app.get("/api/health")
async def health_check():
    return {"status": "ok"}


@app.get("/api/recommendation")
async def api_recommendation():
    file = Path("../recommendation.json")
    if not file.exists():
        return {"error": "file_not_found"}
    try:
        return json.loads(file.read_text())
    except Exception as e:
        return {"error": "json_malformed", "details": str(e)}


app.mount("/", CustomStaticFiles(directory="static"), name="static")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=3000,
        # Increased WebSocket frame size to comfortably handle image data URLs.
        ws_max_size=16 * 1024 * 1024,
    )
