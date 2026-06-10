"""LLM-backed planners for ReAct and Plan-and-Execute agents."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from app.agents.plan_execute_schemas import PlanStep
from app.llm.base import BaseLLMProvider
from app.tools.schemas import ToolInfo


class LLMPlannerError(ValueError):
    """Raised when an LLM planner response cannot be used safely."""


@dataclass
class ReActPlanDecision:
    """Validated ReAct planner decision."""

    tool_name: str | None
    action_input: dict[str, object]
    thought: str


class LLMPlanner:
    """Use an LLM provider to create tool decisions and execution plans."""

    def __init__(self, llm_provider: BaseLLMProvider) -> None:
        self.llm_provider = llm_provider

    def plan_react(self, question: str, tools: list[ToolInfo]) -> ReActPlanDecision:
        """Plan a single ReAct action from available tools."""
        tool_names = {tool.name for tool in tools}
        context = json.dumps(
            {
                "task": "Select at most one tool for a ReAct agent.",
                "allowed_response_schema": {
                    "tool_name": "string tool name or null",
                    "action_input": "object",
                    "thought": "brief explanation string",
                },
                "tools": [_tool_to_prompt_dict(tool) for tool in tools],
                "rules": [
                    "Return only JSON.",
                    "Use null tool_name when no tool is appropriate and RAG should answer.",
                    "Do not invent tool names or input fields.",
                ],
            },
            ensure_ascii=False,
        )
        raw = self.llm_provider.generate(question, context)
        data = _parse_json_object(raw)

        tool_name_raw = data.get("tool_name")
        if tool_name_raw is None:
            tool_name = None
        elif isinstance(tool_name_raw, str) and tool_name_raw in tool_names:
            tool_name = tool_name_raw
        else:
            raise LLMPlannerError(f"LLM selected unknown tool: {tool_name_raw!r}")

        action_input = data.get("action_input", {})
        if not isinstance(action_input, dict):
            raise LLMPlannerError("LLM action_input must be an object")

        thought = data.get("thought", "")
        if not isinstance(thought, str) or not thought.strip():
            thought = "LLM planner selected an action"

        return ReActPlanDecision(
            tool_name=tool_name,
            action_input=dict(action_input),
            thought=thought,
        )

    def plan_execute(
        self,
        question: str,
        tools: list[ToolInfo],
        max_steps: int,
    ) -> list[PlanStep]:
        """Plan a bounded Plan-and-Execute sequence from available tools."""
        tool_names = {tool.name for tool in tools}
        context = json.dumps(
            {
                "task": "Create a concise execution plan.",
                "allowed_step_schema": {
                    "description": "string",
                    "action_type": "tool, rag, or final",
                    "tool_name": "required only when action_type is tool",
                    "tool_input": "object, required only when action_type is tool",
                },
                "max_steps": max_steps,
                "tools": [_tool_to_prompt_dict(tool) for tool in tools],
                "rules": [
                    "Return only JSON with a top-level steps array.",
                    "Allowed action_type values are tool, rag, final.",
                    "Do not invent tool names or input fields.",
                    "Include a final step as the last step.",
                ],
            },
            ensure_ascii=False,
        )
        raw = self.llm_provider.generate(question, context)
        data = _parse_json_object(raw)
        raw_steps = data.get("steps")
        if not isinstance(raw_steps, list) or not raw_steps:
            raise LLMPlannerError("LLM plan must include a non-empty steps array")

        steps: list[PlanStep] = []
        for raw_step in raw_steps[:max_steps]:
            if not isinstance(raw_step, dict):
                raise LLMPlannerError("Each LLM plan step must be an object")
            step = _parse_step(raw_step, len(steps), tool_names)
            steps.append(step)

        if not steps:
            raise LLMPlannerError("LLM plan produced no usable steps")

        if steps[-1].action_type != "final":
            if len(steps) >= max_steps:
                steps[-1] = PlanStep(
                    step_index=steps[-1].step_index,
                    description="Generate final answer",
                    action_type="final",
                )
            else:
                steps.append(
                    PlanStep(
                        step_index=len(steps),
                        description="Generate final answer",
                        action_type="final",
                    )
                )

        return steps


def _parse_step(raw_step: dict[str, Any], index: int, tool_names: set[str]) -> PlanStep:
    action_type = raw_step.get("action_type")
    if action_type not in {"tool", "rag", "final"}:
        raise LLMPlannerError(f"Invalid action_type: {action_type!r}")

    description = raw_step.get("description")
    if not isinstance(description, str) or not description.strip():
        description = f"Step {index + 1}"

    if action_type == "tool":
        tool_name = raw_step.get("tool_name")
        if not isinstance(tool_name, str) or tool_name not in tool_names:
            raise LLMPlannerError(f"LLM selected unknown tool: {tool_name!r}")
        tool_input = raw_step.get("tool_input", {})
        if not isinstance(tool_input, dict):
            raise LLMPlannerError("LLM tool_input must be an object")
        return PlanStep(
            step_index=index,
            description=description,
            action_type="tool",
            tool_name=tool_name,
            tool_input=dict(tool_input),
        )

    return PlanStep(
        step_index=index,
        description=description,
        action_type=action_type,
    )


def _parse_json_object(raw: str) -> dict[str, Any]:
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:].strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise LLMPlannerError("LLM response was not valid JSON")
        try:
            data = json.loads(text[start : end + 1])
        except json.JSONDecodeError as e:
            raise LLMPlannerError("LLM response was not valid JSON") from e

    if not isinstance(data, dict):
        raise LLMPlannerError("LLM response must be a JSON object")
    return data


def _tool_to_prompt_dict(tool: ToolInfo) -> dict[str, object]:
    return {
        "name": tool.name,
        "description": tool.description,
        "input_schema": tool.input_schema,
        "required_role": tool.required_role,
        "allowed_modes": tool.allowed_modes,
    }
