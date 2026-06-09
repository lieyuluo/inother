"""Schemas for Plan-and-Execute Agent."""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import uuid4


@dataclass
class PlanStep:
    """A single step in the execution plan."""

    step_index: int
    description: str
    action_type: str  # tool / rag / final
    tool_name: str | None = None
    tool_input: dict[str, object] = field(default_factory=dict)
    status: str = "pending"  # pending / running / success / error / skipped


@dataclass
class StepResult:
    """Result from executing a single plan step."""

    step_index: int
    status: str  # success / error / skipped
    output: str = ""
    error: str | None = None
    latency_ms: float | None = None
    tool_name: str | None = None
    citations: list[dict[str, object]] = field(default_factory=list)


@dataclass
class PlanExecuteResult:
    """Result from the Plan-and-Execute Agent."""

    answer: str
    plan: list[PlanStep] = field(default_factory=list)
    step_results: list[StepResult] = field(default_factory=list)
    citations: list[dict[str, object]] = field(default_factory=list)
    tool_calls: list[dict[str, object]] = field(default_factory=list)
    trace_id: str = field(default_factory=lambda: str(uuid4()))
    used_fallback: bool = False
    mode: str = "plan_execute"
    final_status: str = "success"  # success / partial_error / max_steps_reached
