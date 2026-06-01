"""API routes — REST + WebSocket endpoints."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse

from src.agent.loop import AgentLoop
from src.agent.memory import ConversationMemory
from src.agent.profile import get_profile, get_profile_path, init_profile, save_profile
from src.api.models import (
    AgentStepResponse,
    ChatRequest,
    ChatResponse,
    ConversationListResponse,
    HealthResponse,
    ModelInfo,
    ModelsResponse,
    SettingsRequest,
)
from src.config import config
from src.llm.client import llm_client

router = APIRouter(prefix="/api")


@router.get("/health")
async def health_check() -> HealthResponse:
    llm_ok = await llm_client.health_check()
    return HealthResponse(
        status="ok" if llm_ok else "llm_disconnected",
        llm_connected=llm_ok,
    )


@router.get("/models")
async def list_models() -> ModelsResponse:
    """List available GGUF models in the model directory."""
    model_dir = Path(config.llm.model_dir)
    models: list[ModelInfo] = []

    if model_dir.exists():
        for f in sorted(model_dir.glob("*.gguf")):
            size_mb = f.stat().st_size / (1024 * 1024)
            models.append(ModelInfo(
                filename=f.name,
                size_mb=round(size_mb, 1),
                path=str(f),
            ))

    return ModelsResponse(
        models=models,
        current_model=config.llm.default_model,
    )


@router.post("/settings")
async def update_settings(req: SettingsRequest) -> JSONResponse:
    """Update runtime settings (model, temperature, etc.)."""
    if req.model:
        config.llm.default_model = req.model
    if req.temperature is not None:
        config.agent.temperature = req.temperature
    if req.ctx_size is not None:
        config.llm.server.ctx_size = req.ctx_size
    if req.threads is not None:
        config.llm.server.threads = req.threads
    return JSONResponse({"status": "updated"})


@router.post("/chat")
async def chat(req: ChatRequest) -> ChatResponse:
    """Run agent loop (non-streaming, returns all steps at once)."""
    start = time.time()
    agent = AgentLoop(conversation_id=req.conversation_id)
    steps: list[AgentStepResponse] = []
    final_answer: str | None = None

    async for step in agent.run(req.message):
        if step.thought:
            steps.append(AgentStepResponse(
                type="thought",
                content=step.thought,
                duration=step.duration,
            ))
        if step.action:
            steps.append(AgentStepResponse(
                type="action",
                content=f"Running {step.action}",
                action_name=step.action,
                action_input=step.action_input,
                duration=step.duration,
            ))
        if step.observation is not None:
            steps.append(AgentStepResponse(
                type="observation",
                content=step.observation,
                duration=step.duration,
            ))
        if step.final_answer:
            final_answer = step.final_answer
            steps.append(AgentStepResponse(
                type="final_answer",
                content=step.final_answer,
                duration=step.duration,
            ))
        if step.error:
            steps.append(AgentStepResponse(
                type="error",
                content=step.error,
                duration=step.duration,
            ))

    return ChatResponse(
        conversation_id=agent.memory.conversation_id,
        steps=steps,
        final_answer=final_answer,
        total_duration=round(time.time() - start, 2),
    )


@router.websocket("/ws/chat")
async def websocket_chat(ws: WebSocket) -> None:
    """WebSocket endpoint for streaming agent events."""
    await ws.accept()

    try:
        while True:
            data = await ws.receive_text()
            msg = json.loads(data)
            user_input = msg.get("message", "")
            conv_id = msg.get("conversation_id")

            agent = AgentLoop(conversation_id=conv_id)

            # Send conversation ID back
            await ws.send_json({
                "type": "meta",
                "conversation_id": agent.memory.conversation_id,
            })

            # Stream granular events to the frontend
            async for event in agent.run_events(user_input):
                await ws.send_json(event.to_ws())

            await ws.send_json({"type": "done"})

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await ws.send_json({"type": "error", "content": str(e)})
        except Exception:
            pass


@router.get("/conversations")
async def list_conversations() -> ConversationListResponse:
    """List all saved conversations."""
    memory = ConversationMemory()
    return ConversationListResponse(conversations=memory.list_conversations())


@router.get("/conversations/{conv_id}")
async def get_conversation(conv_id: str) -> JSONResponse:
    """Get a specific conversation's messages."""
    memory = ConversationMemory(conversation_id=conv_id)
    data = memory.load()
    return JSONResponse(data)


@router.get("/profile")
async def get_user_profile() -> JSONResponse:
    """Get the user's personal profile."""
    content = get_profile()
    if not content:
        content = init_profile()
    return JSONResponse({"content": content, "path": get_profile_path()})


@router.post("/profile")
async def update_user_profile(body: dict[str, Any]) -> JSONResponse:
    """Update the user's personal profile. Expects {"content": "..."}."""
    content = body.get("content", "")
    save_profile(content)
    return JSONResponse({"status": "saved", "path": get_profile_path()})
