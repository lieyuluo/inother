"""Tests for user-facing API error responses."""

import io

from fastapi.testclient import TestClient

from app.core.config import clear_settings_cache
from app.core.provider_errors import ProviderResponseError
from app.services.document_service import DocumentService


def test_unauthenticated_error_has_clear_message(
    client: TestClient,
    monkeypatch,
) -> None:
    monkeypatch.setenv("AUTH_REQUIRED", "true")
    clear_settings_cache()
    try:
        response = client.get("/api/documents")
    finally:
        monkeypatch.delenv("AUTH_REQUIRED", raising=False)
        clear_settings_cache()

    assert response.status_code == 401
    data = response.json()
    assert data["code"] == "unauthenticated"
    assert data["message"] == "请先登录或重新登录后再试。"
    assert data["detail"] == "Could not validate credentials"


def test_validation_error_lists_fields(client: TestClient) -> None:
    response = client.post(
        "/api/auth/register",
        json={"email": "bad", "username": "ab", "password": "short"},
    )

    assert response.status_code == 422
    data = response.json()
    assert data["code"] == "validation_error"
    assert "请求参数不正确" in data["message"]
    assert "username" in data["message"]
    assert "password" in data["message"]
    assert data["details"]["fields"]
    assert isinstance(data["detail"], list)


def test_business_error_keeps_detail_and_message(client: TestClient) -> None:
    response = client.post(
        "/api/documents/upload",
        files={"file": ("bad.xyz", io.BytesIO(b"bad"), "application/octet-stream")},
    )

    assert response.status_code == 400
    data = response.json()
    assert data["code"] == "bad_request"
    assert "Unsupported file type" in data["message"]
    assert data["detail"] == data["error"]


def test_provider_error_has_actionable_message(
    client: TestClient,
    monkeypatch,
) -> None:
    async def fail_upload(*args, **kwargs):
        raise ProviderResponseError("Server error: HTTP 500", provider="openai_embedding")

    monkeypatch.setattr(DocumentService, "upload_document", fail_upload)
    response = client.post(
        "/api/documents/upload",
        files={"file": ("doc.txt", io.BytesIO(b"hello"), "text/plain")},
    )

    assert response.status_code == 502
    data = response.json()
    assert data["code"] == "provider_response_error"
    assert data["message"] == "AI 服务返回异常，请检查模型、额度、Base URL，或稍后重试。"
    assert data["details"]["provider"] == "openai_embedding"
