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

from agents.realtime import RealtimeRunner, RealtimeSession, RealtimeSessionEvent
from agents.realtime.config import RealtimeUserInputMessage
from agents.realtime.items import RealtimeItem
from agents.realtime.model import RealtimeModelConfig
from agents.realtime.model_inputs import RealtimeModelSendRawMessage

from agent import get_starting_agent


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RealtimeWebSocketManager:
    def __init__(self):
        self.active_sessions: dict[str, RealtimeSession] = {}
        self.session_contexts: dict[str, Any] = {}
        self.websockets: dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, session_id: str):
        await websocket.accept()
        self.websockets[session_id] = websocket

        agent = get_starting_agent()
        runner = RealtimeRunner(agent)
        # If you want to customize the runner behavior, you can pass options:
        # runner_config = RealtimeRunConfig(async_tool_calls=False)
        # runner = RealtimeRunner(agent, config=runner_config)
        session_context = await runner.run(
            model_config={
                "initial_model_settings": {
                    "voice_enabled": False,
                    "modalities": ["text"],
                },
                "instructions": agent.instructions,
                "output_modalities": ["text"],
            }
        )
        session = await session_context.__aenter__()
        if hasattr(session, "model"):
            try:
                await session.model.update_session(
                    {
                        "modalities": ["text"],
                        "output_modalities": ["text"],
                    }
                )
                print("✅ Session patched to text-only!")
            except Exception as e:
                print("⚠️ session.model.update_session failed:", e)

        self.active_sessions[session_id] = session
        self.session_contexts[session_id] = session_context

        # Start event processing task
        asyncio.create_task(self._process_events(session_id))

    async def disconnect(self, session_id: str):
        if session_id in self.session_contexts:
            await self.session_contexts[session_id].__aexit__(None, None, None)
            del self.session_contexts[session_id]
        if session_id in self.active_sessions:
            del self.active_sessions[session_id]
        if session_id in self.websockets:
            del self.websockets[session_id]

    async def send_client_event(self, session_id: str, event: dict[str, Any]):
        session = self.active_sessions.get(session_id)
        if not session:
            print("No active realtime session!")
            return

        logger.info(f"Sending client event: {event['type']}")
        if event["type"] == "response.create":
            print("Requesting model response...")
            await session.model.send_event(
                RealtimeModelSendRawMessage(
                    message={
                        "type": "response.create",
                        "response": {
                            "modalities": ["text"],
                        },
                    }
                )
            )

    async def send_user_message(
        self, session_id: str, message: RealtimeUserInputMessage
    ):
        """Send a structured user message via the higher-level API."""
        session = self.active_sessions.get(session_id)
        if not session:
            return
        await session.send_message(
            message
        )  # delegates to RealtimeModelSendUserInput path

    async def interrupt(self, session_id: str) -> None:
        """Interrupt current model playback/response for a session."""
        session = self.active_sessions.get(session_id)
        if not session:
            return
        await session.interrupt()

    async def _process_events(self, session_id: str):
        try:
            session = self.active_sessions[session_id]
            websocket = self.websockets[session_id]

            async for event in session:
                print("MODEL SENT EVENT:", event, event.type)

                if "audio" in event.type.lower():
                    continue

                if event.type == "response.text.delta":
                    # Incremental text from the model
                    if hasattr(event, "delta"):
                        await websocket.send_text(
                            json.dumps(
                                {
                                    "type": "assistant_response_delta",
                                    "text": event.delta,
                                }
                            )
                        )

                elif event.type == "response.text.done":
                    # Complete text response
                    if hasattr(event, "text"):
                        await websocket.send_text(
                            json.dumps(
                                {"type": "assistant_response", "text": event.text}
                            )
                        )

                elif event.type == "response.done":
                    # Response complete
                    await websocket.send_text(json.dumps({"type": "response_complete"}))

                elif hasattr(event, "data"):
                    # Try to extract text from event data
                    data = event.data
                    text = None

                    if hasattr(data, "output_text"):
                        text = data.output_text
                    elif hasattr(data, "text"):
                        text = data.text
                    elif isinstance(data, dict):
                        text = data.get("output_text") or data.get("text")

                    if text:
                        await websocket.send_text(
                            json.dumps({"type": "assistant_response", "text": text})
                        )

        except Exception as e:
            print(e)
            logger.error(f"Error processing events for session {session_id}: {e}")

    # def _sanitize_history_item(self, item: RealtimeItem) -> dict[str, Any]:
    #     """Remove large binary payloads from history items while keeping transcripts."""
    #     item_dict = item.model_dump()
    #     content = item_dict.get("content")
    #     if isinstance(content, list):
    #         sanitized_content: list[Any] = []
    #         for part in content:
    #             if isinstance(part, dict):
    #                 sanitized_part = part.copy()
    #                 sanitized_content.append(sanitized_part)
    #             else:
    #                 sanitized_content.append(part)
    #         item_dict["content"] = sanitized_content
    #     return item_dict

    # async def _serialize_event(self, event: RealtimeSessionEvent) -> dict[str, Any]:
    #     print("Incoming Realtime event type:", event.type)

    #     base_event: dict[str, Any] = {
    #         "type": event.type,
    #     }

    #     # if event.type == "agent_start":
    #     #     base_event["agent"] = event.agent.name
    #     # elif event.type == "agent_end":
    #     #     base_event["agent"] = event.agent.name
    #     # elif event.type == "handoff":
    #     #     base_event["from"] = event.from_agent.name
    #     #     base_event["to"] = event.to_agent.name
    #     # elif event.type == "tool_start":
    #     #     base_event["tool"] = event.tool.name
    #     # elif event.type == "tool_end":
    #     #     base_event["tool"] = event.tool.name
    #     #     base_event["output"] = str(event.output)
    #     # elif event.type == "audio_interrupted":
    #     #     pass
    #     # elif event.type == "history_updated":
    #     #     base_event["history"] = [
    #     #         self._sanitize_history_item(item) for item in event.history
    #     #     ]
    #     # elif event.type == "history_added":
    #     #     # Provide the added item so the UI can render incrementally.
    #     #     try:
    #     #         base_event["item"] = self._sanitize_history_item(event.item)
    #     #     except Exception:
    #     #         base_event["item"] = None
    #     # elif event.type == "guardrail_tripped":
    #     #     base_event["guardrail_results"] = [
    #     #         {"name": result.guardrail.name} for result in event.guardrail_results
    #     #     ]

    #     text = ""
    #     if event.type == "raw_model_event" and not text:
    #         return None

    #     elif event.type == "raw_model_event":

    #         if hasattr(event, "data") and hasattr(event.data, "data"):
    #             payload = event.data.data

    #             if isinstance(payload, dict):
    #                 if "delta" in payload:
    #                     text = payload["delta"]
    #                 elif "output_text" in payload:
    #                     text = payload["output_text"]
    #                 elif "text" in payload:
    #                     text = payload["text"]

    #         base_event["raw_model_event"] = {"type": "assistant_response", "text": text}

    #     elif event.type == "error":
    #         base_event["error"] = (
    #             str(event.error) if hasattr(event, "error") else "Unknown error"
    #         )
    #     elif event.type == "input_audio_timeout_triggered":
    #         pass
    #     else:
    #         logger.warning(f"Skipping unsupported realtime event: {event.type}")

    #     return base_event


manager = RealtimeWebSocketManager()


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
                # agent = get_starting_agent()

                await manager.send_user_message(
                    session_id,
                    RealtimeUserInputMessage(
                        role="user",
                        type="message",
                        content=[{"type": "input_text", "text": message["text"]}],
                    ),
                )

                await manager.send_client_event(
                    session_id,
                    {
                        "type": "response.create",
                    },
                )

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for session {session_id}")
        await manager.disconnect(session_id)
    except Exception as e:
        logger.error(f"WebSocket error: {e}", exc_info=True)
        await manager.disconnect(session_id)


class CustomStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope: Scope) -> FileResponse:
        response = await super().get_response(path, scope)
        # Check if the file is a JavaScript file since the wrong mime-type is
        # sometimes returned depending on the host OS
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
