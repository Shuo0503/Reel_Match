import asyncio
import json
import logging
from contextlib import asynccontextmanager
from typing import Any

from agent import MovieRecommendations, get_starting_agent
from agents import OpenAIConversationsSession, Runner
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AgentsWebSocketManager:
    def __init__(self):
        self.active_sessions: dict[str, OpenAIConversationsSession] = {}
        self.agents: dict[str, Any] = {}
        self.websockets: dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, session_id: str):
        await websocket.accept()
        self.websockets[session_id] = websocket

        agent = get_starting_agent()
        session = OpenAIConversationsSession()

        self.active_sessions[session_id] = session
        self.agents[session_id] = agent
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
            result = Runner.run_streamed(agent, input=user_input, session=session)
            current_agent = agent
            async for event in result.stream_events():
                if event.type == "agent_updated_stream_event":
                    if event.new_agent is not current_agent:
                        await websocket.send_text(
                            json.dumps({
                                "type": "handoff",
                                "from": current_agent.name,
                                "to": event.new_agent.name,
                            })
                        )
                    current_agent = event.new_agent

                # Only stream plain-text agents; structured output arrives as one JSON payload below
                elif event.type == "raw_response_event":
                    if (
                        event.data.type == "response.output_text.delta"
                        and current_agent.output_type is None
                    ):
                        await websocket.send_text(
                            json.dumps({
                                "type": "assistant_response_delta",
                                "text": event.data.delta,
                            })
                        )

                # Handoffs also surface as tool calls; only report the hosted web search
                elif (
                    event.type == "run_item_stream_event"
                    and event.name == "tool_called"
                    and getattr(event.item.raw_item, "type", None) == "web_search_call"
                ):
                    action = event.item.raw_item.action
                    detail = getattr(action, "query", None) or getattr(action, "url", None)
                    logger.info(f"🔎 Web search ({action.type}): {detail}")
                    await websocket.send_text(
                        json.dumps({"type": "tool_start", "tool": "web_search"})
                    )

            if isinstance(result.final_output, MovieRecommendations):
                await websocket.send_text(
                    json.dumps({
                        "type": "recommendations",
                        "data": result.final_output.model_dump(),
                    })
                )
            await websocket.send_text(json.dumps({"type": "response_complete"}))
        except Exception as e:
            logger.error(f"Error streaming response for session {session_id}: {e}", exc_info=True)
            await websocket.send_text(
                json.dumps({
                    "type": "assistant_response_delta",
                    "text": "Sorry, something went wrong finding your movies. Please try again.",
                })
            )
            await websocket.send_text(json.dumps({"type": "response_complete"}))



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


@app.get("/")
async def read_index():
    return FileResponse("static/index.html")


@app.get("/api/health")
async def health_check():
    return {"status": "ok"}


app.mount("/", StaticFiles(directory="static"), name="static")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=3000,
    )
