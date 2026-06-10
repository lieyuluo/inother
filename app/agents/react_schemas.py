"""Schemas for ReAct Agent."""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import uuid4


@dataclass
class ReActStep:
    """A single step in the ReAct execution trace."""

    step_index: int
    thought: str
    action: str
    action_input: dict[str, object]
    observation: str = ""
    status: str = "success"  # success / error / skipped
    tool_name: str | None = None
    latency_ms: float | None = None


@dataclass
class ReActResult:
    """Result from the ReAct Agent."""

    answer: str
    steps: list[ReActStep] = field(default_factory=list)
    tool_calls: list[dict[str, object]] = field(default_factory=list)
    citations: list[dict[str, object]] = field(default_factory=list)
    trace_id: str = field(default_factory=lambda: str(uuid4()))
    used_fallback: bool = False
    mode: str = "react"
    planner_provider: str = "deterministic"
    fallback_reason: str | None = None
