"""Reranker implementations."""

from __future__ import annotations

import json
from typing import Any

from app.llm.base import BaseLLMProvider
from app.rag.retriever import RetrievalResult


class BaseReranker:
    """Base class for rerankers."""

    def rerank(self, query: str, results: list[RetrievalResult]) -> list[RetrievalResult]:
        raise NotImplementedError


class NoopReranker(BaseReranker):
    """No-op reranker that returns results unchanged."""

    def rerank(self, query: str, results: list[RetrievalResult]) -> list[RetrievalResult]:  # noqa: ARG002
        return results


class LLMReranker(BaseReranker):
    """Rerank retrieval results using an OpenAI-compatible LLM provider."""

    def __init__(self, llm_provider: BaseLLMProvider) -> None:
        self.llm_provider = llm_provider

    def rerank(self, query: str, results: list[RetrievalResult]) -> list[RetrievalResult]:
        if len(results) <= 1:
            return results

        candidate_map = {result.chunk_id: result for result in results}
        context = json.dumps(
            {
                "task": "Rerank document chunks by relevance to the query.",
                "allowed_response_schema": {
                    "results": [
                        {
                            "chunk_id": "one of the provided chunk_id values",
                            "score": "number between 0 and 1",
                        }
                    ]
                },
                "rules": [
                    "Return only JSON.",
                    "Do not invent chunk_id values.",
                    "Higher score means more relevant.",
                ],
                "candidates": [
                    {
                        "chunk_id": result.chunk_id,
                        "document_title": result.document_title,
                        "chunk_index": result.chunk_index,
                        "current_score": result.score,
                        "content": result.content,
                    }
                    for result in results
                ],
            },
            ensure_ascii=False,
        )
        raw = self.llm_provider.generate(query, context)
        data = _parse_json_object(raw)
        raw_ranked = data.get("results")
        if not isinstance(raw_ranked, list):
            raise ValueError("LLM reranker response must include a results array")

        ranked: list[RetrievalResult] = []
        seen: set[str] = set()
        for item in raw_ranked:
            if not isinstance(item, dict):
                continue
            chunk_id = item.get("chunk_id")
            if not isinstance(chunk_id, str) or chunk_id not in candidate_map or chunk_id in seen:
                continue
            result = candidate_map[chunk_id]
            score = item.get("score")
            if isinstance(score, int | float):
                result.score = float(score)
            ranked.append(result)
            seen.add(chunk_id)

        if not ranked:
            raise ValueError("LLM reranker returned no valid chunk ids")

        ranked.extend(result for result in results if result.chunk_id not in seen)
        return ranked


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
            raise ValueError("LLM reranker response was not valid JSON")
        data = json.loads(text[start : end + 1])

    if not isinstance(data, dict):
        raise ValueError("LLM reranker response must be a JSON object")
    return data
