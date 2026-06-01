"""Pydantic models for API request/response schemas."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class ChatRequest(BaseModel):
    message: str
    conversation_id: str | None = None
    model: str | None = None  # override default model


class AgentStepResponse(BaseModel):
    type: str  # "thought", "action", "observation", "final_answer", "error"
    content: str
    action_name: str | None = None
    action_input: Any = None
    duration: float = 0.0


class ChatResponse(BaseModel):
    conversation_id: str
    steps: list[AgentStepResponse]
    final_answer: str | None = None
    total_duration: float = 0.0


class ModelInfo(BaseModel):
    filename: str
    size_mb: float
    path: str


class ModelsResponse(BaseModel):
    models: list[ModelInfo]
    current_model: str


class HealthResponse(BaseModel):
    status: str
    llm_connected: bool
    version: str = "0.1.0"


class SettingsRequest(BaseModel):
    model: str | None = None
    temperature: float | None = None
    ctx_size: int | None = None
    threads: int | None = None


class ConversationListResponse(BaseModel):
    conversations: list[dict[str, Any]]
