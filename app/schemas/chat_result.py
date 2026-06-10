"""Shared chat result dataclass for non-streaming and streaming responses."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from app.schemas.chat import (
    CitationResponse,
    MessageResponse,
    PlanStepResponse,
    ReActStepResponse,
    StepResultResponse,
)


@dataclass
class ChatResult:
    """Unified result from chat processing.

    Used by both non-streaming and streaming endpoints to avoid
    duplicating logic.
    """

    user_message: MessageResponse
    answer: str
    citations: list[CitationResponse] = field(default_factory=list)
    trace_id: str = ""
    steps: list[ReActStepResponse] | None = None
    tool_calls: list[dict[str, object]] | None = None
    mode: str = "rag"
    plan: list[PlanStepResponse] | None = None
    step_results: list[StepResultResponse] | None = None
    assistant_metadata: dict[str, Any] = field(default_factory=dict)
    session_id: UUID | None = None
