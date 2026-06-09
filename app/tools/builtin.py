"""Built-in tools for the Enterprise AI Agent.

Tools:
1. echo_tool - Echo back input text
2. calculator_tool - Safe arithmetic expression evaluation
3. search_documents_tool - Search documents using RAG Retriever
4. get_system_status_tool - Return system status info
5. list_documents_tool - List non-deleted documents
"""

import ast
import operator
import time
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models import Document
from app.rag.retriever import Retriever
from app.tools.base import BaseTool
from app.tools.schemas import ToolResult


class EchoTool(BaseTool):
    """Echo tool that returns input text unchanged."""

    @property
    def name(self) -> str:
        return "echo_tool"

    @property
    def description(self) -> str:
        return "Echo back the input text. Useful for testing tool invocation."

    @property
    def input_schema(self) -> dict[str, object]:
        return {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "Text to echo back",
                },
            },
            "required": ["text"],
        }

    async def invoke(self, input_data: dict[str, object]) -> ToolResult:
        start = time.monotonic()
        text = input_data.get("text", "")
        latency_ms = (time.monotonic() - start) * 1000
        return ToolResult(
            tool_name=self.name,
            status="success",
            output={"text": str(text)},
            latency_ms=latency_ms,
            trace_id=str(uuid4()),
        )


# AST node whitelist for safe arithmetic evaluation
_SAFE_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}

_MAX_EXPRESSION_LENGTH = 200


class CalculatorTool(BaseTool):
    """Safe arithmetic calculator using AST whitelist.

    Security:
    - No eval() or exec()
    - No function calls
    - No name/variable access
    - No attribute access
    - No string operations
    - Expression length limited to 200 characters
    - Only numeric literals and basic arithmetic operators allowed
    """

    @property
    def name(self) -> str:
        return "calculator_tool"

    @property
    def description(self) -> str:
        return "Evaluate a safe arithmetic expression. Supports +, -, *, /, **, %. No variables or function calls."

    @property
    def input_schema(self) -> dict[str, object]:
        return {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "Arithmetic expression to evaluate (e.g., '1+2*3')",
                    "maxLength": _MAX_EXPRESSION_LENGTH,
                },
            },
            "required": ["expression"],
        }

    async def invoke(self, input_data: dict[str, object]) -> ToolResult:
        start = time.monotonic()
        trace_id = str(uuid4())
        expression = input_data.get("expression", "")

        try:
            result = self._safe_eval(str(expression))
            latency_ms = (time.monotonic() - start) * 1000
            return ToolResult(
                tool_name=self.name,
                status="success",
                output={"result": result, "expression": str(expression)},
                latency_ms=latency_ms,
                trace_id=trace_id,
            )
        except (ValueError, ZeroDivisionError, SyntaxError) as e:
            latency_ms = (time.monotonic() - start) * 1000
            return ToolResult(
                tool_name=self.name,
                status="error",
                error=str(e),
                latency_ms=latency_ms,
                trace_id=trace_id,
            )

    def _safe_eval(self, expression: str) -> int | float:
        """Safely evaluate an arithmetic expression using AST whitelist.

        Args:
            expression: Arithmetic expression string.

        Returns:
            Numeric result.

        Raises:
            ValueError: For invalid or unsafe expressions.
            ZeroDivisionError: For division by zero.
            SyntaxError: For malformed expressions.
        """
        if not expression or not expression.strip():
            raise ValueError("Expression cannot be empty")

        if len(expression) > _MAX_EXPRESSION_LENGTH:
            raise ValueError(f"Expression too long (max {_MAX_EXPRESSION_LENGTH} characters)")

        try:
            tree = ast.parse(expression, mode="eval")
        except SyntaxError as e:
            raise SyntaxError(f"Invalid expression syntax: {e}") from e

        result = self._eval_node(tree.body)
        return result

    def _eval_node(self, node: ast.AST) -> int | float:
        """Recursively evaluate an AST node with whitelist enforcement.

        Args:
            node: AST node to evaluate.

        Returns:
            Numeric result.

        Raises:
            ValueError: For disallowed AST nodes.
        """
        if isinstance(node, ast.Constant):
            # Only allow numeric constants (int, float)
            if isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
                return node.value
            raise ValueError(f"Unsupported constant type: {type(node.value).__name__}")

        if isinstance(node, ast.UnaryOp):
            op_type = type(node.op)
            if op_type not in _SAFE_OPERATORS:
                raise ValueError(f"Unsupported unary operator: {op_type.__name__}")
            operand = self._eval_node(node.operand)
            return _SAFE_OPERATORS[op_type](operand)

        if isinstance(node, ast.BinOp):
            op_type = type(node.op)
            if op_type not in _SAFE_OPERATORS:
                raise ValueError(f"Unsupported binary operator: {op_type.__name__}")
            left = self._eval_node(node.left)
            right = self._eval_node(node.right)
            try:
                return _SAFE_OPERATORS[op_type](left, right)
            except ZeroDivisionError:
                raise ZeroDivisionError("Division by zero") from None

        # Reject all other node types
        raise ValueError(
            f"Unsupported expression element: {type(node).__name__}. "
            f"Only numeric literals and basic arithmetic operators (+, -, *, /, **, %) are allowed."
        )


class SearchDocumentsTool(BaseTool):
    """Search documents using the RAG Retriever."""

    def __init__(self, db_session: AsyncSession) -> None:
        self._db_session = db_session

    @property
    def name(self) -> str:
        return "search_documents_tool"

    @property
    def description(self) -> str:
        return "Search documents in the knowledge base. Returns relevant document chunks with similarity scores."

    @property
    def input_schema(self) -> dict[str, object]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query text",
                },
                "top_k": {
                    "type": "integer",
                    "description": "Maximum number of results (default: from config)",
                },
            },
            "required": ["query"],
        }

    async def invoke(self, input_data: dict[str, object]) -> ToolResult:
        start = time.monotonic()
        trace_id = str(uuid4())
        query = input_data.get("query", "")
        top_k = input_data.get("top_k")

        try:
            retriever = Retriever(
                session=self._db_session,
                top_k=int(top_k) if top_k is not None else None,
            )
            results = await retriever.similarity_search(str(query))

            search_results = [
                {
                    "document_id": r.document_id,
                    "document_title": r.document_title,
                    "chunk_id": r.chunk_id,
                    "chunk_index": r.chunk_index,
                    "score": r.score,
                    "snippet": r.content,
                }
                for r in results
            ]

            latency_ms = (time.monotonic() - start) * 1000
            return ToolResult(
                tool_name=self.name,
                status="success",
                output={"results": search_results, "count": len(search_results)},
                latency_ms=latency_ms,
                trace_id=trace_id,
            )
        except Exception as e:
            latency_ms = (time.monotonic() - start) * 1000
            return ToolResult(
                tool_name=self.name,
                status="error",
                error=str(e),
                latency_ms=latency_ms,
                trace_id=trace_id,
            )


class GetSystemStatusTool(BaseTool):
    """Return system status information."""

    @property
    def name(self) -> str:
        return "get_system_status_tool"

    @property
    def description(self) -> str:
        return "Get the current system status including service name, version, and environment."

    @property
    def input_schema(self) -> dict[str, object]:
        return {
            "type": "object",
            "properties": {},
        }

    async def invoke(self, input_data: dict[str, object]) -> ToolResult:  # noqa: ARG002
        start = time.monotonic()
        settings = get_settings()
        latency_ms = (time.monotonic() - start) * 1000
        return ToolResult(
            tool_name=self.name,
            status="success",
            output={
                "service": settings.app_name,
                "version": settings.app_version,
                "environment": settings.app_env,
                "status": "ok",
            },
            latency_ms=latency_ms,
            trace_id=str(uuid4()),
        )


class ListDocumentsTool(BaseTool):
    """List non-deleted documents."""

    def __init__(self, db_session: AsyncSession) -> None:
        self._db_session = db_session

    @property
    def name(self) -> str:
        return "list_documents_tool"

    @property
    def description(self) -> str:
        return "List all non-deleted documents in the knowledge base."

    @property
    def input_schema(self) -> dict[str, object]:
        return {
            "type": "object",
            "properties": {},
        }

    async def invoke(self, input_data: dict[str, object]) -> ToolResult:  # noqa: ARG002
        start = time.monotonic()
        trace_id = str(uuid4())

        try:
            stmt = (
                select(Document)
                .where(Document.status != "deleted")
                .order_by(Document.created_at.desc())
                .limit(100)
            )
            result = await self._db_session.execute(stmt)
            documents = list(result.scalars().all())

            doc_list = [
                {
                    "id": str(doc.id),
                    "title": doc.title,
                    "filename": doc.filename,
                    "status": doc.status,
                    "file_size": doc.file_size,
                    "created_at": str(doc.created_at),
                }
                for doc in documents
            ]

            latency_ms = (time.monotonic() - start) * 1000
            return ToolResult(
                tool_name=self.name,
                status="success",
                output={"documents": doc_list, "count": len(doc_list)},
                latency_ms=latency_ms,
                trace_id=trace_id,
            )
        except Exception as e:
            latency_ms = (time.monotonic() - start) * 1000
            return ToolResult(
                tool_name=self.name,
                status="error",
                error=str(e),
                latency_ms=latency_ms,
                trace_id=trace_id,
            )


def create_builtin_tools(db_session: AsyncSession) -> list[BaseTool]:
    """Create instances of all built-in tools.

    Args:
        db_session: Async database session for tools that need DB access.

    Returns:
        List of built-in tool instances.
    """
    return [
        EchoTool(),
        CalculatorTool(),
        SearchDocumentsTool(db_session),
        GetSystemStatusTool(),
        ListDocumentsTool(db_session),
    ]
