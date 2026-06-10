"""ReAct Agent with deterministic planner for tool selection.

This agent uses a rule-based (deterministic) planner instead of a real LLM
to decide which tools to call. It is designed for testing and development.

NOT production-grade: a real LLM planner would use chain-of-thought reasoning
to dynamically select and sequence tools. This implementation uses simple
pattern matching rules.
"""

import re
import time
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.rag_agent import RAGAgent
from app.agents.react_schemas import ReActResult, ReActStep
from app.db.models import User
from app.db.repositories import AuditLogRepository
from app.tools.service import ToolService

# Maximum steps allowed in ReAct execution
DEFAULT_MAX_STEPS = 5

# Pattern for extracting arithmetic expressions from questions with explicit keywords
_ARITH_EXPLICIT_PATTERN = re.compile(
    "(?:\u8ba1\u7b97|calculate|\u7b97|compute)\\s*(.*)",
    re.IGNORECASE,
)

# Pattern for "what is" followed by arithmetic (requires digits to disambiguate)
_ARITH_WHATIS_PATTERN = re.compile(
    r"(?:what is)\s*([\d+\-*/().%\s]+)",
    re.IGNORECASE,
)


class DeterministicPlanner:
    "Deterministic rule-based planner for ReAct tool selection.\n\n    Rules (evaluated in order):\n    1. Arithmetic expressions -> calculator_tool\n    2. Echo/\u56de\u663e prefix -> echo_tool\n    3. System status/health -> get_system_status_tool\n    4. Search documents/\u77e5\u8bc6\u5e93\u641c\u7d22 -> search_documents_tool\n    5. No match -> fallback to RAG\n\n    This is NOT a production-grade LLM planner. It uses simple pattern\n    matching for deterministic, testable behavior.\n"

    @staticmethod
    def plan(question: str) -> tuple[str | None, dict[str, object], str]:
        """Determine which tool to call based on the question.

        Args:
            question: User question text.

        Returns:
            Tuple of (tool_name, action_input, thought).
            tool_name is None if no tool matches (fallback to RAG).
        """
        q = question.strip().lower()

        # Rule 1: Arithmetic expressions
        # 1a: Explicit keywords (\u8ba1\u7b97/calculate/\u7b97/compute) -> always select calculator
        arith_explicit_match = _ARITH_EXPLICIT_PATTERN.search(question)
        if arith_explicit_match:
            expr = arith_explicit_match.group(1).strip()
            if not expr:
                expr = question  # fallback to full question if no expression after keyword
            expr = expr.replace("^", "**")
            return (
                "calculator_tool",
                {"expression": expr},
                f"Detected arithmetic expression: {expr}",
            )

            # 1b: "what is" + digits -> calculator (requires digits to disambiguate from general questions)
        arith_whatis_match = _ARITH_WHATIS_PATTERN.search(question)
        if arith_whatis_match:
            expr = arith_whatis_match.group(1).strip()
            if expr and re.search(r"\d", expr):
                expr = expr.replace("^", "**")
                return (
                    "calculator_tool",
                    {"expression": expr},
                    f"Detected arithmetic expression: {expr}",
                )

                # Also check for pure arithmetic patterns without keyword prefix
        if re.match(r"^[\d+\-*/().%\s]+$", question.strip()) and any(
            c in question for c in "+-*/%"
        ):
            expr = question.strip().replace("^", "**")
            return (
                "calculator_tool",
                {"expression": expr},
                f"Detected pure arithmetic expression: {expr}",
            )

            # Rule 2: Echo
        if q.startswith("echo ") or q.startswith("\u56de\u663e "):
            text = question.strip()
            # Remove prefix
            for prefix in ("echo ", "\u56de\u663e "):
                if text.lower().startswith(prefix):
                    text = text[len(prefix) :].strip()
                    break
            return (
                "echo_tool",
                {"text": text},
                f"Detected echo request: {text}",
            )

            # Rule 3: System status
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
            return (
                "get_system_status_tool",
                {},
                "Detected system status query",
            )

            # Rule 4: Search documents
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
            # Extract query after keyword
            query = question.strip()
            return (
                "search_documents_tool",
                {"query": query},
                "Detected document search request",
            )

            # Rule 5: MCP business metric
        mcp_metric_keywords = [
            "business metric",
            "\u4e1a\u52a1\u6307\u6807",
            "revenue",
            "active users",
            "tickets",
            "\u67e5\u8be2\u6307\u6807",
            "\u6307\u6807\u67e5\u8be2",
        ]
        if any(kw in q for kw in mcp_metric_keywords):
            # Try to extract specific metric
            metric = "revenue"  # default
            if "active_users" in q or "active users" in q or "\u7528\u6237" in q:
                metric = "active_users"
            elif "tickets" in q or "\u5de5\u5355\u6570" in q or "ticket" in q:
                metric = "tickets"
            elif "revenue" in q or "\u6536\u5165" in q or "\u8425\u6536" in q:
                metric = "revenue"
            return (
                "mcp_get_business_metric",
                {"metric": metric},
                f"Detected business metric query: {metric}",
            )

            # Rule 6: MCP create ticket
        mcp_ticket_keywords = [
            "create ticket",
            "\u521b\u5efa\u5de5\u5355",
            "\u63d0\u4ea4\u5de5\u5355",
            "\u65b0\u5efa\u5de5\u5355",
            "\u5f00\u5de5\u5355",
        ]
        if any(kw in q for kw in mcp_ticket_keywords):
            title = question.strip()
            return (
                "mcp_create_ticket",
                {"title": title, "description": title},
                "Detected ticket creation request",
            )

            # Rule 7: MCP echo
        if q.startswith("mcp echo ") or q.startswith("mcp_echo "):
            text = question.strip()
            for prefix in ("mcp echo ", "mcp_echo "):
                if text.lower().startswith(prefix):
                    text = text[len(prefix) :].strip()
                    break
            return (
                "mcp_echo",
                {"text": text},
                f"Detected MCP echo request: {text}",
            )

            # Rule 8: No match -> fallback to RAG
        return (None, {}, "No matching tool found, falling back to RAG")


class ReActAgent:
    """ReAct Agent that uses deterministic planning for tool selection.

    Flow:
    1. Receive user question
    2. Generate deterministic thought about which tool to use
    3. If tool selected: call tool via ToolService, record observation
    4. If no tool: fallback to RAGAgent
    5. Return answer with steps trace

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
        self.tool_service = ToolService(session, current_user=current_user)
        self.planner = DeterministicPlanner()
        self.audit_repo = AuditLogRepository(session)

    async def query(
        self,
        question: str,
        session_id: UUID | None = None,
    ) -> ReActResult:
        """Process a question through the ReAct pipeline.

        Args:
            question: User question text.
            session_id: Optional chat session ID for audit log.

        Returns:
            ReActResult with answer, steps, tool_calls, and metadata.
        """
        trace_id = str(__import__("uuid").uuid4())
        steps: list[ReActStep] = []
        tool_calls: list[dict[str, object]] = []

        # Step 1: Plan - determine which tool to use
        tool_name, action_input, thought = self.planner.plan(question)

        if tool_name is None:
            # Fallback to RAG
            step = ReActStep(
                step_index=0,
                thought=thought,
                action="fallback_to_rag",
                action_input={},
                observation="Using RAG Agent for answer",
                status="skipped",
            )
            steps.append(step)

            rag_agent = RAGAgent(
                session=self.session,
                user_id=self.current_user.id if self.current_user is not None else None,
            )
            rag_result = await rag_agent.query(question)

            result = ReActResult(
                answer=rag_result.answer,
                steps=steps,
                tool_calls=[],
                citations=[
                    {
                        "document_id": c.document_id,
                        "document_title": c.document_title,
                        "chunk_id": c.chunk_id,
                        "chunk_index": c.chunk_index,
                        "score": c.score,
                        "snippet": c.snippet,
                    }
                    for c in rag_result.citations
                ],
                trace_id=trace_id,
                used_fallback=True,
                mode="react",
            )

            await self._write_audit_log(result, session_id, question)
            return result

            # Step 2: Execute tool
        step_index = 0
        step = ReActStep(
            step_index=step_index,
            thought=thought,
            action=f"call_tool:{tool_name}",
            action_input=action_input,
            tool_name=tool_name,
        )
        steps.append(step)

        start = time.monotonic()
        try:
            tool_result = await self.tool_service.invoke_tool(
                tool_name=tool_name,
                input_data=action_input,
                actor="react_agent",
                session_id=session_id,
            )
            latency_ms = (time.monotonic() - start) * 1000

            if tool_result.status == "success":
                step.observation = str(tool_result.output)
                step.status = "success"
                step.latency_ms = latency_ms

                # Build answer from tool result
                answer = self._format_tool_answer(tool_name, tool_result.output)
            else:
                step.observation = f"Error: {tool_result.error}"
                step.status = "error"
                step.latency_ms = latency_ms
                answer = (
                    f"\u5de5\u5177 {tool_name} \u6267\u884c\u5931\u8d25\uff1a{tool_result.error}"
                )

            tool_calls.append(
                {
                    "tool_name": tool_name,
                    "status": tool_result.status,
                    "trace_id": tool_result.trace_id,
                    "latency_ms": latency_ms,
                }
            )

        except Exception as e:
            latency_ms = (time.monotonic() - start) * 1000
            step.observation = f"Exception: {e}"
            step.status = "error"
            step.latency_ms = latency_ms
            answer = f"\u5de5\u5177 {tool_name} \u6267\u884c\u5f02\u5e38"

            # Check max_steps: only truncate if we've exceeded the limit
            # (single tool call = 1 step; max_steps=1 allows 1 step, max_steps=0 means no steps allowed)
        if self.max_steps <= 0:
            answer = "ReAct execution stopped because max_steps was reached."

        result = ReActResult(
            answer=answer,
            steps=steps,
            tool_calls=tool_calls,
            citations=[],
            trace_id=trace_id,
            used_fallback=False,
            mode="react",
        )

        await self._write_audit_log(result, session_id, question)
        return result

    def _format_tool_answer(self, tool_name: str, output: dict[str, object] | None) -> str:
        """Format a tool result into a human-readable answer.

        Args:
            tool_name: Name of the tool.
            output: Tool output dictionary.

        Returns:
            Formatted answer string.
        """
        if output is None:
            return f"\u5de5\u5177 {tool_name} \u8fd4\u56de\u7a7a\u7ed3\u679c"

        if tool_name == "calculator_tool":
            result_val = output.get("result", "")
            expression = output.get("expression", "")
            return f"\u8ba1\u7b97\u7ed3\u679c\uff1a{expression} = {result_val}"

        if tool_name == "echo_tool":
            text = output.get("text", "")
            return f"\u56de\u663e\uff1a{text}"

        if tool_name == "get_system_status_tool":
            service = output.get("service", "")
            version = output.get("version", "")
            env = output.get("environment", "")
            status_val = output.get("status", "")
            return f"\u7cfb\u7edf\u72b6\u6001\uff1a{service} v{version} ({env}) - {status_val}"

        if tool_name == "search_documents_tool":
            count = output.get("count", 0)
            return f"\u641c\u7d22\u5230 {count} \u6761\u76f8\u5173\u6587\u6863"

        if tool_name == "list_documents_tool":
            count = output.get("count", 0)
            return f"\u5171\u6709 {count} \u4e2a\u6587\u6863"

            # Generic fallback
        import json

        return f"[{tool_name}] {json.dumps(output, ensure_ascii=False, default=str)}"

    async def _write_audit_log(
        self,
        result: ReActResult,
        session_id: UUID | None,
        question: str,
    ) -> None:
        """Write audit log for ReAct execution."""
        metadata: dict[str, object] = {
            "trace_id": result.trace_id,
            "question": question,
            "mode": "react",
            "steps_count": len(result.steps),
            "tool_calls_count": len(result.tool_calls),
            "used_fallback": result.used_fallback,
            "final_status": result.steps[-1].status if result.steps else "unknown",
        }
        if session_id:
            metadata["session_id"] = str(session_id)

        await self.audit_repo.create(
            action="react.run",
            actor="react_agent",
            resource_type="react_session",
            resource_id=session_id,
            metadata=metadata,
            user_id=self.current_user.id if self.current_user is not None else None,
        )
