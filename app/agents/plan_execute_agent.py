"""Plan-and-Execute Agent with deterministic planner.

This agent decomposes a user question into a multi-step plan, then executes
each step sequentially. It uses a rule-based (deterministic) planner instead
of a real LLM.

NOT production-grade: a real LLM planner would use chain-of-thought reasoning
to dynamically decompose tasks. This implementation uses simple pattern matching.
"""

import re
import time
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.plan_execute_schemas import (
    PlanExecuteResult,
    PlanStep,
    StepResult,
)
from app.agents.rag_agent import RAGAgent
from app.db.models import User
from app.db.repositories import AuditLogRepository
from app.tools.service import ToolService

DEFAULT_MAX_STEPS = 5

# -- Deterministic Planner ----------------------------------------------


class DeterministicPlanPlanner:
    "Deterministic rule-based planner for Plan-and-Execute.\n\n    Rules (evaluated in order):\n    1. Report + documents -> search_documents + final\n    2. Multi-step (\u5148...\u518d... / first...then...) -> multi-tool + final\n    3. System status + documents -> get_system_status + search_documents + final\n    4. Single tool task -> tool + final\n    5. No match -> rag + final\n\n    This is NOT a production-grade LLM planner.\n"

    @staticmethod
    def plan(question: str, max_steps: int = DEFAULT_MAX_STEPS) -> list[PlanStep]:
        """Generate a deterministic execution plan for the question.

        Args:
            question: User question text.
            max_steps: Maximum number of steps allowed.

        Returns:
            List of PlanStep objects.
        """
        q = question.strip().lower()

        # Rule 1: Report/\u603b\u7ed3 + documents -> search_documents + final
        report_keywords = [
            "\u751f\u6210\u62a5\u544a",
            "\u62a5\u544a",
            "\u603b\u7ed3",
            "report",
            "summarize",
            "summary",
        ]
        doc_keywords = [
            "\u6587\u6863",
            "\u77e5\u8bc6\u5e93",
            "document",
            "search documents",
            "\u641c\u7d22\u6587\u6863",
            "\u77e5\u8bc6\u5e93\u641c\u7d22",
        ]
        if any(kw in q for kw in report_keywords) and any(kw in q for kw in doc_keywords):
            steps = [
                PlanStep(
                    step_index=0,
                    description="Search documents for report content",
                    action_type="tool",
                    tool_name="search_documents_tool",
                    tool_input={"query": question},
                ),
                PlanStep(
                    step_index=1,
                    description="Generate final answer from search results",
                    action_type="final",
                ),
            ]
            return _trim_plan(steps, max_steps)

            # Rule 2: Multi-step patterns (\u5148...\u518d... / first...then...)
        multi_step_patterns = [
            "\u5148.+\u518d",
            "\u5148.+\u7136\u540e",
            "\u5148.+\u63a5\u7740",
            r"first.+then",
            r"first.+after",
        ]
        if any(re.search(p, q) for p in multi_step_patterns):
            steps = _build_multi_step_plan(question, q, max_steps)
            return _trim_plan(steps, max_steps)

            # Rule 3: System status + documents -> get_system_status + search_documents + final
        status_keywords = [
            "\u7cfb\u7edf\u72b6\u6001",
            "system status",
            "\u7cfb\u7edf\u4fe1\u606f",
            "system info",
            "health",
            "\u5065\u5eb7",
            "\u670d\u52a1\u72b6\u6001",
            "service status",
        ]
        if any(kw in q for kw in status_keywords) and any(kw in q for kw in doc_keywords):
            steps = [
                PlanStep(
                    step_index=0,
                    description="Check system status",
                    action_type="tool",
                    tool_name="get_system_status_tool",
                    tool_input={},
                ),
                PlanStep(
                    step_index=1,
                    description="Search documents",
                    action_type="tool",
                    tool_name="search_documents_tool",
                    tool_input={"query": question},
                ),
                PlanStep(
                    step_index=2,
                    description="Generate final answer",
                    action_type="final",
                ),
            ]
            return _trim_plan(steps, max_steps)

            # Rule 3.5: MCP - \u5148\u67e5\u770b\u4e1a\u52a1\u6307\u6807\uff0c\u518d\u521b\u5efa\u5de5\u5355
        mcp_metric_keywords = [
            "\u4e1a\u52a1\u6307\u6807",
            "business metric",
            "revenue",
            "active_users",
            "active users",
        ]
        mcp_ticket_keywords = [
            "\u521b\u5efa\u5de5\u5355",
            "create ticket",
            "\u63d0\u4ea4\u5de5\u5355",
            "\u65b0\u5efa\u5de5\u5355",
        ]
        if any(kw in q for kw in mcp_metric_keywords) and any(
            kw in q for kw in mcp_ticket_keywords
        ):
            metric_tool = (
                "mcp.demo.get_business_metric"
                if "namespaced" in q or "mcp.demo" in q
                else "mcp_get_business_metric"
            )
            ticket_tool = (
                "mcp.demo.create_ticket"
                if "namespaced" in q or "mcp.demo" in q
                else "mcp_create_ticket"
            )
            steps = [
                PlanStep(
                    step_index=0,
                    description="Get business metric",
                    action_type="tool",
                    tool_name=metric_tool,
                    tool_input={"metric": "revenue"},
                ),
                PlanStep(
                    step_index=1,
                    description="Create ticket",
                    action_type="tool",
                    tool_name=ticket_tool,
                    tool_input={"title": question, "description": question},
                ),
                PlanStep(
                    step_index=2,
                    description="Generate final answer",
                    action_type="final",
                ),
            ]
            return _trim_plan(steps, max_steps)

            # Rule 3.6: MCP - \u751f\u6210\u4e1a\u52a1\u6307\u6807\u62a5\u544a
        mcp_report_keywords = [
            "\u751f\u6210\u4e1a\u52a1\u6307\u6807\u62a5\u544a",
            "\u4e1a\u52a1\u6307\u6807\u62a5\u544a",
            "business metric report",
            "\u751f\u6210\u6307\u6807\u62a5\u544a",
        ]
        if any(kw in q for kw in mcp_report_keywords):
            metric_tool = (
                "mcp.demo.get_business_metric"
                if "namespaced" in q or "mcp.demo" in q
                else "mcp_get_business_metric"
            )
            steps = [
                PlanStep(
                    step_index=0,
                    description="Get business metric",
                    action_type="tool",
                    tool_name=metric_tool,
                    tool_input={"metric": "revenue"},
                ),
                PlanStep(
                    step_index=1,
                    description="Generate final answer",
                    action_type="final",
                ),
            ]
            return _trim_plan(steps, max_steps)

            # Rule 4: Single tool task -> tool + final
        single_tool = _detect_single_tool(question, q)
        if single_tool is not None:
            tool_name, tool_input = single_tool
            steps = [
                PlanStep(
                    step_index=0,
                    description=f"Call {tool_name}",
                    action_type="tool",
                    tool_name=tool_name,
                    tool_input=tool_input,
                ),
                PlanStep(
                    step_index=1,
                    description="Generate final answer",
                    action_type="final",
                ),
            ]
            return _trim_plan(steps, max_steps)

            # Rule 5: No match -> rag + final
        steps = [
            PlanStep(
                step_index=0,
                description="Query knowledge base via RAG",
                action_type="rag",
            ),
            PlanStep(
                step_index=1,
                description="Generate final answer",
                action_type="final",
            ),
        ]
        return _trim_plan(steps, max_steps)


def _trim_plan(steps: list[PlanStep], max_steps: int) -> list[PlanStep]:
    """Trim plan to max_steps, ensuring a final step exists."""
    if len(steps) <= max_steps:
        return steps

    trimmed = steps[:max_steps]
    # Ensure last step is final
    if trimmed and trimmed[-1].action_type != "final":
        trimmed[-1] = PlanStep(
            step_index=trimmed[-1].step_index,
            description="Generate final answer (truncated)",
            action_type="final",
        )
    return trimmed


def _detect_single_tool(question: str, q: str) -> tuple[str, dict[str, object]] | None:
    """Detect a single tool match from the question.

    Returns (tool_name, tool_input) or None.
    """
    # Calculator
    arith_explicit = re.search(
        "(?:\u8ba1\u7b97|calculate|\u7b97|compute)\\s*(.*)", question, re.IGNORECASE
    )
    if arith_explicit:
        expr = arith_explicit.group(1).strip()
        if not expr:
            expr = question
        expr = expr.replace("^", "**")
        return ("calculator_tool", {"expression": expr})

    arith_whatis = re.search(r"(?:what is)\s*([\d+\-*/().%\s]+)", question, re.IGNORECASE)
    if arith_whatis:
        expr = arith_whatis.group(1).strip()
        if expr and re.search(r"\d", expr):
            expr = expr.replace("^", "**")
            return ("calculator_tool", {"expression": expr})

    if re.match(r"^[\d+\-*/().%\s]+$", question.strip()) and any(c in question for c in "+-*/%"):
        expr = question.strip().replace("^", "**")
        return ("calculator_tool", {"expression": expr})

        # Echo
    if q.startswith("echo ") or q.startswith("\u56de\u663e "):
        text = question.strip()
        for prefix in ("echo ", "\u56de\u663e "):
            if text.lower().startswith(prefix):
                text = text[len(prefix) :].strip()
                break
        return ("echo_tool", {"text": text})

        # System status
    status_keywords = [
        "\u7cfb\u7edf\u72b6\u6001",
        "system status",
        "\u7cfb\u7edf\u4fe1\u606f",
        "system info",
        "health",
        "\u5065\u5eb7",
        "\u670d\u52a1\u72b6\u6001",
        "service status",
    ]
    if any(kw in q for kw in status_keywords):
        return ("get_system_status_tool", {})

        # Search documents
    search_keywords = [
        "\u641c\u7d22\u6587\u6863",
        "search documents",
        "\u77e5\u8bc6\u5e93\u641c\u7d22",
        "search knowledge",
        "\u641c\u7d22\u77e5\u8bc6",
        "\u6587\u6863\u641c\u7d22",
        "document search",
    ]
    if any(kw in q for kw in search_keywords):
        return ("search_documents_tool", {"query": question})

        # MCP business metric
    mcp_metric_keywords = [
        "business metric",
        "\u4e1a\u52a1\u6307\u6807",
        "\u67e5\u8be2\u6307\u6807",
        "\u6307\u6807\u67e5\u8be2",
    ]
    if any(kw in q for kw in mcp_metric_keywords):
        metric = "revenue"
        if "active_users" in q or "active users" in q or "\u7528\u6237" in q:
            metric = "active_users"
        elif "tickets" in q or "\u5de5\u5355\u6570" in q:
            metric = "tickets"
        tool_name = (
            "mcp.demo.get_business_metric"
            if "namespaced" in q or "mcp.demo" in q
            else "mcp_get_business_metric"
        )
        return (tool_name, {"metric": metric})

        # MCP create ticket
    mcp_ticket_kws = [
        "create ticket",
        "\u521b\u5efa\u5de5\u5355",
        "\u63d0\u4ea4\u5de5\u5355",
        "\u65b0\u5efa\u5de5\u5355",
    ]
    if any(kw in q for kw in mcp_ticket_kws):
        tool_name = (
            "mcp.demo.create_ticket"
            if "namespaced" in q or "mcp.demo" in q
            else "mcp_create_ticket"
        )
        return (tool_name, {"title": question, "description": question})

        # MCP echo
    if q.startswith("mcp echo ") or q.startswith("mcp_echo "):
        text = question.strip()
        for prefix in ("mcp echo ", "mcp_echo "):
            if text.lower().startswith(prefix):
                text = text[len(prefix) :].strip()
                break
        return ("mcp_echo", {"text": text})

    return None


def _build_multi_step_plan(question: str, q: str, max_steps: int) -> list[PlanStep]:
    "Build a multi-step plan for \u5148...\u518d... / first...then... patterns."
    steps: list[PlanStep] = []
    idx = 0

    # Split on \u5148/\u518d/\u7136\u540e/\u63a5\u7740 or first/then/after
    # Chinese pattern
    cn_parts = re.split("[\u5148\u518d\u7136\u540e\u63a5\u7740]", question)
    cn_parts = [p.strip() for p in cn_parts if p.strip()]

    # English pattern
    en_parts = re.split(
        r"\b(?:first|then|after\s+that|afterwards)\b", question, flags=re.IGNORECASE
    )
    en_parts = [p.strip() for p in en_parts if p.strip()]

    # Use whichever gives more parts
    parts = cn_parts if len(cn_parts) >= len(en_parts) else en_parts

    if len(parts) < 2:
        # Fallback: treat whole question as single tool or rag
        single_tool = _detect_single_tool(question, q)
        if single_tool:
            tool_name, tool_input = single_tool
            steps.append(
                PlanStep(
                    step_index=idx,
                    description=f"Call {tool_name}",
                    action_type="tool",
                    tool_name=tool_name,
                    tool_input=tool_input,
                )
            )
            idx += 1
        else:
            steps.append(
                PlanStep(
                    step_index=idx,
                    description="Query knowledge base via RAG",
                    action_type="rag",
                )
            )
            idx += 1
    else:
        for part in parts:
            if idx >= max_steps - 1:
                break
            part_lower = part.lower()
            single_tool = _detect_single_tool(part, part_lower)
            if single_tool:
                tool_name, tool_input = single_tool
                steps.append(
                    PlanStep(
                        step_index=idx,
                        description=f"Call {tool_name}: {part[:50]}",
                        action_type="tool",
                        tool_name=tool_name,
                        tool_input=tool_input,
                    )
                )
            else:
                steps.append(
                    PlanStep(
                        step_index=idx,
                        description=f"Query RAG: {part[:50]}",
                        action_type="rag",
                    )
                )
            idx += 1

            # Always add final step
    steps.append(
        PlanStep(
            step_index=idx,
            description="Generate final answer",
            action_type="final",
        )
    )

    return steps

    # -- Executor -----------------------------------------------------------


class Executor:
    """Execute plan steps sequentially."""

    def __init__(self, session: AsyncSession, current_user: User | None = None) -> None:
        self.session = session
        self.current_user = current_user
        self.tool_service = ToolService(session, current_user=current_user)

    async def execute_step(
        self,
        step: PlanStep,
        question: str,
        session_id: UUID | None = None,
    ) -> StepResult:
        """Execute a single plan step.

        Args:
            step: The plan step to execute.
            question: Original user question (for RAG fallback).
            session_id: Optional session ID.

        Returns:
            StepResult with execution outcome.
        """
        step.status = "running"
        start = time.monotonic()

        if step.action_type == "final":
            latency_ms = (time.monotonic() - start) * 1000
            step.status = "success"
            return StepResult(
                step_index=step.step_index,
                status="success",
                output="Final answer generated",
                latency_ms=latency_ms,
            )

        if step.action_type == "rag":
            return await self._execute_rag_step(step, question, start, session_id)

        if step.action_type == "tool":
            return await self._execute_tool_step(step, start, session_id)

            # Unknown action type
        latency_ms = (time.monotonic() - start) * 1000
        step.status = "error"
        return StepResult(
            step_index=step.step_index,
            status="error",
            error=f"Unknown action_type: {step.action_type}",
            latency_ms=latency_ms,
        )

    async def _execute_tool_step(
        self,
        step: PlanStep,
        start: float,
        session_id: UUID | None,
    ) -> StepResult:
        """Execute a tool step."""
        tool_name = step.tool_name or "unknown"
        try:
            tool_result = await self.tool_service.invoke_tool(
                tool_name=tool_name,
                input_data=step.tool_input,
                actor="plan_execute_agent",
                session_id=session_id,
                mode="plan_execute",
            )
            latency_ms = (time.monotonic() - start) * 1000

            if tool_result.status == "success":
                step.status = "success"
                return StepResult(
                    step_index=step.step_index,
                    status="success",
                    output=str(tool_result.output),
                    latency_ms=latency_ms,
                    tool_name=tool_name,
                )
            else:
                step.status = "error"
                return StepResult(
                    step_index=step.step_index,
                    status="error",
                    output=str(tool_result.output) if tool_result.output else "",
                    error=tool_result.error or "Tool returned error",
                    latency_ms=latency_ms,
                    tool_name=tool_name,
                )
        except Exception as e:
            latency_ms = (time.monotonic() - start) * 1000
            step.status = "error"
            return StepResult(
                step_index=step.step_index,
                status="error",
                error=str(e),
                latency_ms=latency_ms,
                tool_name=tool_name,
            )

    async def _execute_rag_step(
        self,
        step: PlanStep,
        question: str,
        start: float,
        session_id: UUID | None,  # noqa: ARG002
    ) -> StepResult:
        """Execute a RAG step."""
        try:
            rag_agent = RAGAgent(
                session=self.session,
                user_id=self.current_user.id if self.current_user is not None else None,
            )
            rag_result = await rag_agent.query(question)
            latency_ms = (time.monotonic() - start) * 1000
            step.status = "success"

            citations = [
                {
                    "document_id": c.document_id,
                    "document_title": c.document_title,
                    "chunk_id": c.chunk_id,
                    "chunk_index": c.chunk_index,
                    "score": c.score,
                    "snippet": c.snippet,
                }
                for c in rag_result.citations
            ]

            return StepResult(
                step_index=step.step_index,
                status="success",
                output=rag_result.answer,
                latency_ms=latency_ms,
                citations=citations,
            )
        except Exception as e:
            latency_ms = (time.monotonic() - start) * 1000
            step.status = "error"
            return StepResult(
                step_index=step.step_index,
                status="error",
                error=str(e),
                latency_ms=latency_ms,
            )

            # -- Verifier -----------------------------------------------------------


class Verifier:
    """Verify plan execution results."""

    @staticmethod
    def verify(
        step_results: list[StepResult],
        plan: list[PlanStep],
        max_steps: int,
    ) -> str:
        """Check execution results and return final_status.

        Returns:
            One of: "success", "partial_error", "max_steps_reached"
        """
        # Check if any steps were skipped (due to max_steps)
        skipped_steps = [sr for sr in step_results if sr.status == "skipped"]
        if skipped_steps:
            return "max_steps_reached"

            # Check if plan has pending steps that weren't executed
        pending_steps = [s for s in plan if s.status == "pending"]
        executed_count = len(step_results)
        if pending_steps and (executed_count < len(plan) or executed_count >= max_steps):
            return "max_steps_reached"

            # Check for errors
        error_count = sum(1 for s in step_results if s.status == "error")
        if error_count > 0:
            return "partial_error"

        return "success"

        # -- Writer / Finalizer -------------------------------------------------


class Finalizer:
    """Generate final answer from step results."""

    @staticmethod
    def finalize(
        step_results: list[StepResult],
        final_status: str,
        used_fallback: bool,
    ) -> str:
        """Generate a final answer based on step results.

        Args:
            step_results: Results from each executed step.
            final_status: Overall execution status.
            used_fallback: Whether RAG fallback was used.

        Returns:
            Final answer string.
        """
        if final_status == "max_steps_reached":
            return "Plan execution stopped because max_steps was reached. Partial results may be available."

        if used_fallback:
            # Use RAG answer directly
            for sr in step_results:
                if sr.citations or sr.output:
                    return sr.output
            return "No results from RAG fallback."

        if final_status == "partial_error":
            success_steps = [
                sr
                for sr in step_results
                if sr.status == "success" and sr.output != "Final answer generated"
            ]
            error_steps = [sr for sr in step_results if sr.status == "error"]
            parts = []
            if success_steps:
                parts.append(
                    "Completed steps: "
                    + "; ".join(f"Step {s.step_index}: {s.output[:80]}" for s in success_steps)
                )
            if error_steps:
                parts.append(
                    "Failed steps: "
                    + "; ".join(f"Step {s.step_index}: {s.error}" for s in error_steps)
                )
            return "Plan executed with errors. " + " ".join(parts)

            # All success
        success_outputs = [
            f"Step {sr.step_index}: {sr.output[:100]}"
            for sr in step_results
            if sr.status == "success" and sr.output and sr.output != "Final answer generated"
        ]
        if success_outputs:
            return "Plan executed successfully. " + "; ".join(success_outputs)
        return "Plan executed successfully."

        # -- PlanExecuteAgent ---------------------------------------------------


class PlanExecuteAgent:
    """Plan-and-Execute Agent.

    Flow:
    1. Planner generates a deterministic plan
    2. Executor runs each step
    3. Verifier checks results
    4. Finalizer generates answer
    5. AuditLog is written

    Does NOT depend on FastAPI request/response.
    """

    def __init__(
        self,
        session: AsyncSession,
        max_steps: int = DEFAULT_MAX_STEPS,
        current_user: User | None = None,
    ) -> None:
        self.session = session
        self.max_steps = max_steps
        self.current_user = current_user
        self.planner = DeterministicPlanPlanner()
        self.executor = Executor(session, current_user=current_user)
        self.verifier = Verifier()
        self.finalizer = Finalizer()
        self.audit_repo = AuditLogRepository(session)

    async def query(
        self,
        question: str,
        session_id: UUID | None = None,
    ) -> PlanExecuteResult:
        """Process a question through the Plan-and-Execute pipeline.

        Args:
            question: User question text.
            session_id: Optional chat session ID.

        Returns:
            PlanExecuteResult with answer, plan, step_results, etc.
        """
        trace_id = str(__import__("uuid").uuid4())

        # Step 1: Plan
        plan = self.planner.plan(question, max_steps=self.max_steps)

        # Step 2: Execute
        step_results: list[StepResult] = []
        tool_calls: list[dict[str, object]] = []
        all_citations: list[dict[str, object]] = []
        used_fallback = False

        for step in plan:
            if step.action_type == "final" and len(step_results) > 0:
                # Final step: just mark success
                step.status = "success"
                step_results.append(
                    StepResult(
                        step_index=step.step_index,
                        status="success",
                        output="Final answer generated",
                    )
                )
                continue

                # Check max_steps: skip remaining if we've hit the limit
            if step.step_index >= self.max_steps:
                step.status = "skipped"
                step_results.append(
                    StepResult(
                        step_index=step.step_index,
                        status="skipped",
                        error="Skipped due to max_steps limit",
                    )
                )
                continue

            step_result = await self.executor.execute_step(step, question, session_id)
            step_results.append(step_result)

            # Collect tool calls
            if step_result.tool_name and step_result.status == "success":
                tool_calls.append(
                    {
                        "tool_name": step_result.tool_name,
                        "status": step_result.status,
                        "latency_ms": step_result.latency_ms,
                    }
                )
            elif step_result.tool_name and step_result.status == "error":
                tool_calls.append(
                    {
                        "tool_name": step_result.tool_name,
                        "status": step_result.status,
                        "latency_ms": step_result.latency_ms,
                        "error": step_result.error,
                    }
                )

                # Collect citations
            if step_result.citations:
                all_citations.extend(step_result.citations)

                # Check if RAG was used (fallback)
            if step.action_type == "rag":
                used_fallback = True

                # Step 3: Verify
        final_status = self.verifier.verify(step_results, plan, self.max_steps)

        # Step 4: Finalize
        answer = self.finalizer.finalize(step_results, final_status, used_fallback)

        # If used_fallback and RAG step succeeded, use RAG answer directly
        if used_fallback:
            for sr in step_results:
                if sr.output and sr.status == "success" and sr.citations is not None:
                    # This was a RAG step
                    answer = sr.output
                    break

        result = PlanExecuteResult(
            answer=answer,
            plan=plan,
            step_results=step_results,
            citations=all_citations,
            tool_calls=tool_calls,
            trace_id=trace_id,
            used_fallback=used_fallback,
            mode="plan_execute",
            final_status=final_status,
        )

        # Step 5: AuditLog
        await self._write_audit_log(result, session_id, question)

        return result

    async def _write_audit_log(
        self,
        result: PlanExecuteResult,
        session_id: UUID | None,
        question: str,
    ) -> None:
        """Write audit log for Plan-and-Execute execution."""
        metadata: dict[str, object] = {
            "trace_id": result.trace_id,
            "question": question,
            "mode": "plan_execute",
            "plan_steps_count": len(result.plan),
            "step_results_count": len(result.step_results),
            "tool_calls_count": len(result.tool_calls),
            "citations_count": len(result.citations),
            "used_fallback": result.used_fallback,
            "final_status": result.final_status,
        }
        if session_id:
            metadata["session_id"] = str(session_id)

        await self.audit_repo.create(
            action="plan_execute.run",
            actor="plan_execute_agent",
            resource_type="plan_execute_session",
            resource_id=session_id,
            metadata=metadata,
            user_id=self.current_user.id if self.current_user is not None else None,
        )
