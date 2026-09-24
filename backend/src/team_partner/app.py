import asyncio
import contextlib
import logging
import uuid
from collections.abc import AsyncIterator, Iterable
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from hyperforge.harness_sdk import HarnessConversation, HarnessEvent, HarnessTool, ModelClient
from pydantic import BaseModel

from team_partner.agents.runtime import open_agent
from team_partner.agents.storage import SQLiteHarnessStorage
from team_partner.agents.tools import TeamsAlertResult, create_team_tools, post_teams_webhook
from team_partner.db import create_database
from team_partner.jira_client import build_live_providers
from team_partner.settings import EnvSettings, env_settings
from team_partner.stories import StoryProvider, placeholder_story_provider
from team_partner.stories import router as stories_router
from team_partner.teams import TeamProvider, placeholder_team_provider
from team_partner.teams import router as teams_router

FRONTEND_ORIGINS = ["http://localhost:4200", "http://localhost:4201"]

logger = logging.getLogger(__name__)


class CreateSessionRequest(BaseModel):
    title: str = "New conversation"


class NotifyRequest(BaseModel):
    message: str | None = None
    title: str = "Execution Partner Alert"
    webhook_url: str | None = None


router = APIRouter(prefix="/api/v1/agents", tags=["agent"])
alerts_router = APIRouter(prefix="/api/v1/alerts", tags=["alerts"])


def storage_for(app: FastAPI) -> SQLiteHarnessStorage:
    return SQLiteHarnessStorage(app.state.session_factory)


DEFAULT_NOTIFY_MESSAGE = (
    "High priority execution risks detected. Please review open PRs and stalled items, "
    "and help unblock owners today."
)


@alerts_router.post("/notify", response_model=TeamsAlertResult)
async def notify_team(body: NotifyRequest, request: Request) -> TeamsAlertResult:
    settings: EnvSettings = request.app.state.settings
    webhook_url = body.webhook_url or settings.teams_webhook_url
    if not webhook_url:
        raise HTTPException(400, "No Teams webhook configured. Set TEAMS_WEBHOOK_URL or provide webhook_url.")
    message = body.message or DEFAULT_NOTIFY_MESSAGE
    result = await post_teams_webhook(
        webhook_url,
        message,
        body.title,
        bearer_token=settings.teams_webhook_bearer_token,
    )
    if not result.delivered:
        raise HTTPException(502, result.message)
    return result


@router.post("/sessions", response_model=HarnessConversation, status_code=201)
async def create_session(body: CreateSessionRequest, request: Request) -> HarnessConversation:
    conversation = HarnessConversation(
        id=uuid.uuid4().hex,
        metadata={"root_agent_id": uuid.uuid4().hex},
        title=body.title,
    )
    await storage_for(request.app).create_conversation(conversation)
    return conversation


@router.get("/sessions", response_model=list[HarnessConversation])
async def list_sessions(request: Request, limit: int = Query(50, ge=1, le=100)):
    return storage_for(request.app).list_conversations(limit=limit)


@router.get("/sessions/{session_id}", response_model=HarnessConversation)
async def get_session(session_id: str, request: Request):
    session = await storage_for(request.app).get_conversation(session_id)
    if session is None:
        raise HTTPException(404, "Conversation not found")
    return session


@router.get("/sessions/{session_id}/events", response_model=list[HarnessEvent])
async def get_events(session_id: str, request: Request):
    storage = storage_for(request.app)
    if await storage.get_conversation(session_id) is None:
        raise HTTPException(404, "Conversation not found")
    return [event async for event in storage.iter_events(session_id)]


@router.delete("/sessions/{session_id}", status_code=204)
async def delete_session(session_id: str, request: Request) -> None:
    if session_id in request.app.state.active_sessions:
        raise HTTPException(409, "Conversation is active")
    if not storage_for(request.app).delete_conversation(session_id):
        raise HTTPException(404, "Conversation not found")


@router.websocket("/sessions/{session_id}/ws")
async def agent_ws(websocket: WebSocket, session_id: str) -> None:
    """Replay history, then accept prompt/steer/interrupt/feedback_response commands."""
    storage = storage_for(websocket.app)
    if await storage.get_conversation(session_id) is None:
        await websocket.close(code=4004, reason="Conversation not found")
        return
    active = websocket.app.state.active_sessions
    if session_id in active:
        await websocket.close(code=4009, reason="Conversation is active")
        return
    active.add(session_id)
    agent = None
    owns_client = False
    turn: asyncio.Task[None] | None = None
    send_lock = asyncio.Lock()

    async def send(frame: dict) -> None:
        async with send_lock:
            await websocket.send_json(frame, mode="text")

    async def run_prompt(prompt: str) -> None:
        assert agent is not None
        try:
            async for event in agent.run(prompt):
                await send({"object": "agent.event", "event": event.model_dump(mode="json")})
        except Exception:
            logger.exception("Agent turn failed")
            with contextlib.suppress(WebSocketDisconnect, RuntimeError):
                await send({"object": "agent.error", "reason": "Agent turn failed"})

    try:
        await websocket.accept()
        await send({"object": "session", "session_id": session_id})
        await send({"object": "history.start"})
        async for event in storage.iter_events(session_id):
            await send({"object": "agent.event", "replay": True, "event": event.model_dump(mode="json")})
        await send({"object": "history.end"})
        await send({"object": "session.ready"})

        while True:
            payload = await websocket.receive_json()
            if not isinstance(payload, dict):
                await send({"object": "command.rejected", "reason": "Command must be an object"})
                continue
            command = payload.get("command")
            if command == "prompt":
                prompt = payload.get("prompt")
                if not isinstance(prompt, str) or not prompt.strip():
                    await send({"object": "command.rejected", "reason": "Prompt is required"})
                    continue
                if turn is not None and not turn.done():
                    await send({"object": "command.rejected", "reason": "A turn is already running"})
                    continue
                if agent is None:
                    try:
                        agent, owns_client = await open_agent(
                            factory=websocket.app.state.session_factory,
                            settings=websocket.app.state.settings,
                            conversation_id=session_id,
                            model_client=websocket.app.state.model_client,
                            tools=websocket.app.state.tools,
                        )
                    except RuntimeError as exc:
                        await send({"object": "command.rejected", "reason": str(exc)})
                        continue
                turn = asyncio.create_task(run_prompt(prompt))
            elif command == "steer" and agent is not None and turn is not None and not turn.done():
                content = payload.get("content")
                if not isinstance(content, str) or not content.strip():
                    await send({"object": "command.rejected", "reason": "Content is required"})
                    continue
                message_id = await agent.steer(content)
                await send({"object": "command.accepted", "command": "steer", "message_id": message_id})
            elif command == "interrupt" and agent is not None and turn is not None and not turn.done():
                agent.interrupt()
            elif command == "feedback_response" and agent is not None:
                await agent.respond_feedback(str(payload.get("request_id", "")), str(payload.get("response", "")))
            else:
                await send({"object": "command.rejected", "reason": "Unknown or inactive command"})
    except WebSocketDisconnect:
        pass
    finally:
        if agent is not None:
            agent.interrupt()
        if turn is not None:
            if not turn.done():
                with contextlib.suppress(Exception):
                    await asyncio.wait_for(turn, timeout=5)
            if not turn.done():
                turn.cancel()
            await asyncio.gather(turn, return_exceptions=True)
        if owns_client and agent is not None:
            await agent.model_client.aclose()
        active.discard(session_id)


def create_app(
    settings: EnvSettings | None = None,
    model_client: ModelClient | None = None,
    tools: Iterable[HarnessTool] = (),
    team_provider: TeamProvider = placeholder_team_provider,
    story_provider: StoryProvider = placeholder_story_provider,
) -> FastAPI:
    settings = settings or env_settings

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        engine, factory = create_database(settings.database_url)
        app.state.session_factory = factory
        app.state.tools = (*create_team_tools(factory, settings), *tools)
        app.state.active_sessions = set()
        try:
            yield
        finally:
            engine.dispose()

    app = FastAPI(title="AI Team Partner API", lifespan=lifespan)
    app.state.settings = settings
    app.state.model_client = model_client
    app.state.team_provider = team_provider
    app.state.story_provider = story_provider
    app.add_middleware(
        CORSMiddleware,
        allow_origins=FRONTEND_ORIGINS,
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["*"],
    )
    app.include_router(router)
    app.include_router(teams_router)
    app.include_router(stories_router)
    app.include_router(alerts_router)

    @app.get("/health", include_in_schema=False)
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


_live_providers = build_live_providers(env_settings)
app = create_app(
    team_provider=_live_providers[0] if _live_providers else placeholder_team_provider,
    story_provider=_live_providers[1] if _live_providers else placeholder_story_provider,
)
