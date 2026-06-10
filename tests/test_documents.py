"""Tests for Document API endpoints."""

import io
from uuid import uuid4

from fastapi.testclient import TestClient

from app.rag.chunking import TextChunker
from app.rag.embeddings import FakeEmbeddingProvider


class TestUploadDocument:
    """Tests for document upload."""

    def test_upload_txt_success(self, client: TestClient) -> None:
        """Test uploading a .txt file successfully."""
        content = b"This is a test document content."
        file = io.BytesIO(content)

        response = client.post(
            "/api/documents/upload",
            files={"file": ("test.txt", file, "text/plain")},
        )

        assert response.status_code == 201
        data = response.json()
        assert "document" in data
        assert data["document"]["filename"] == "test.txt"
        assert data["document"]["file_type"] == "txt"
        assert data["document"]["status"] == "ready"
        assert data["chunks_count"] >= 1

    def test_upload_md_success(self, client: TestClient) -> None:
        """Test uploading a .md file successfully."""
        content = b"# Test Markdown\n\nThis is markdown content."
        file = io.BytesIO(content)

        response = client.post(
            "/api/documents/upload",
            files={"file": ("test.md", file, "text/markdown")},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["document"]["filename"] == "test.md"
        assert data["document"]["file_type"] == "md"
        assert data["document"]["status"] == "ready"

    def test_upload_unsupported_type_returns_400(self, client: TestClient) -> None:
        """Test uploading unsupported file type returns 400."""
        content = b"Unsupported content"
        file = io.BytesIO(content)

        response = client.post(
            "/api/documents/upload",
            files={"file": ("test.xyz", file, "application/octet-stream")},
        )

        assert response.status_code == 400
        assert "Unsupported file type" in response.json()["detail"]

    def test_upload_empty_file_returns_400(self, client: TestClient) -> None:
        """Test uploading empty file returns 400."""
        file = io.BytesIO(b"")

        response = client.post(
            "/api/documents/upload",
            files={"file": ("empty.txt", file, "text/plain")},
        )

        assert response.status_code == 400

    def test_upload_creates_document_record(self, client: TestClient) -> None:
        """Test that upload creates a Document record."""
        content = b"Test content for document creation."
        file = io.BytesIO(content)

        response = client.post(
            "/api/documents/upload",
            files={"file": ("create.txt", file, "text/plain")},
        )

        assert response.status_code == 201
        data = response.json()
        assert "id" in data["document"]
        assert data["document"]["id"] is not None

    def test_upload_creates_chunks(self, client: TestClient) -> None:
        """Test that upload creates DocumentChunk records."""
        content = b"Test content that will be chunked."
        file = io.BytesIO(content)

        response = client.post(
            "/api/documents/upload",
            files={"file": ("chunks.txt", file, "text/plain")},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["chunks_count"] >= 1

    def test_upload_document_status_ready(self, client: TestClient) -> None:
        """Test that successful upload sets status to 'ready'."""
        content = b"Content for status test."
        file = io.BytesIO(content)

        response = client.post(
            "/api/documents/upload",
            files={"file": ("status.txt", file, "text/plain")},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["document"]["status"] == "ready"

    def test_upload_with_custom_title(self, client: TestClient) -> None:
        """Test uploading with custom title."""
        content = b"Content with custom title."
        file = io.BytesIO(content)

        response = client.post(
            "/api/documents/upload",
            files={"file": ("file.txt", file, "text/plain")},
            data={"title": "Custom Title"},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["document"]["title"] == "Custom Title"


class TestListDocuments:
    """Tests for listing documents."""

    def test_list_documents_success(self, client: TestClient) -> None:
        """Test listing documents successfully."""
        # Upload a document first
        content = b"Document for listing test."
        file = io.BytesIO(content)
        client.post(
            "/api/documents/upload",
            files={"file": ("list.txt", file, "text/plain")},
        )

        response = client.get("/api/documents")

        assert response.status_code == 200
        data = response.json()
        assert "documents" in data
        assert "total" in data
        assert data["total"] >= 1

    def test_list_documents_empty(self, client: TestClient) -> None:
        """Test listing documents structure when empty."""
        response = client.get("/api/documents")

        assert response.status_code == 200
        data = response.json()
        assert "documents" in data
        assert "total" in data


class TestGetDocument:
    """Tests for getting a single document."""

    def test_get_document_success(self, client: TestClient) -> None:
        """Test getting a document by ID."""
        # Upload first
        content = b"Document to get."
        file = io.BytesIO(content)
        upload_response = client.post(
            "/api/documents/upload",
            files={"file": ("get.txt", file, "text/plain")},
        )
        document_id = upload_response.json()["document"]["id"]

        # Get document
        response = client.get(f"/api/documents/{document_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == document_id

    def test_get_document_not_found(self, client: TestClient) -> None:
        """Test getting non-existent document returns 404."""
        fake_id = str(uuid4())
        response = client.get(f"/api/documents/{fake_id}")

        assert response.status_code == 404


class TestGetDocumentChunks:
    """Tests for getting document chunks."""

    def test_get_chunks_success(self, client: TestClient) -> None:
        """Test getting chunks for a document."""
        # Upload first
        content = b"Document with chunks to retrieve."
        file = io.BytesIO(content)
        upload_response = client.post(
            "/api/documents/upload",
            files={"file": ("chunks.txt", file, "text/plain")},
        )
        document_id = upload_response.json()["document"]["id"]

        # Get chunks
        response = client.get(f"/api/documents/{document_id}/chunks")

        assert response.status_code == 200
        data = response.json()
        assert "chunks" in data
        assert "total" in data
        assert data["total"] >= 1

    def test_get_chunks_not_found(self, client: TestClient) -> None:
        """Test getting chunks for non-existent document returns 404."""
        fake_id = str(uuid4())
        response = client.get(f"/api/documents/{fake_id}/chunks")

        assert response.status_code == 404


class TestDeleteDocument:
    """Tests for deleting documents."""

    def test_delete_document_success(self, client: TestClient) -> None:
        """Test deleting a document successfully."""
        # Upload first
        content = b"Document to delete."
        file = io.BytesIO(content)
        upload_response = client.post(
            "/api/documents/upload",
            files={"file": ("delete.txt", file, "text/plain")},
        )
        document_id = upload_response.json()["document"]["id"]

        # Delete
        response = client.delete(f"/api/documents/{document_id}")

        assert response.status_code == 204

    def test_delete_document_not_found(self, client: TestClient) -> None:
        """Test deleting non-existent document returns 404."""
        fake_id = str(uuid4())
        response = client.delete(f"/api/documents/{fake_id}")

        assert response.status_code == 404

    def test_deleted_document_not_in_list(self, client: TestClient) -> None:
        """Test that deleted documents are not returned in list."""
        # Upload
        content = b"Document to delete and verify."
        file = io.BytesIO(content)
        upload_response = client.post(
            "/api/documents/upload",
            files={"file": ("delete_verify.txt", file, "text/plain")},
        )
        document_id = upload_response.json()["document"]["id"]

        # Get initial count
        list_response = client.get("/api/documents")
        initial_count = list_response.json()["total"]

        # Delete
        client.delete(f"/api/documents/{document_id}")

        # Get new count
        new_response = client.get("/api/documents")
        new_count = new_response.json()["total"]

        assert new_count < initial_count

    def test_get_deleted_document_returns_404(self, client: TestClient) -> None:
        """Test that getting deleted document returns 404."""
        # Upload
        content = b"Document for 404 test."
        file = io.BytesIO(content)
        upload_response = client.post(
            "/api/documents/upload",
            files={"file": ("404_test.txt", file, "text/plain")},
        )
        document_id = upload_response.json()["document"]["id"]

        # Delete
        client.delete(f"/api/documents/{document_id}")

        # Try to get
        response = client.get(f"/api/documents/{document_id}")

        assert response.status_code == 404


class TestChunking:
    """Tests for text chunking."""

    def test_short_text_one_chunk(self) -> None:
        """Test that short text produces at least 1 chunk."""
        chunker = TextChunker(chunk_size=800, chunk_overlap=100)
        text = "This is a short text."

        chunks = chunker.chunk(text)

        assert len(chunks) >= 1
        assert chunks[0] == text

    def test_long_text_multiple_chunks(self) -> None:
        """Test that long text produces multiple chunks."""
        chunker = TextChunker(chunk_size=100, chunk_overlap=20)
        text = "This is a longer text that should be split into multiple chunks. " * 10

        chunks = chunker.chunk(text)

        assert len(chunks) >= 2

    def test_chunk_index_starts_at_zero(self, client: TestClient) -> None:
        """Test that chunk_index starts at 0."""
        content = b"Content for chunk index test."
        file = io.BytesIO(content)

        upload_response = client.post(
            "/api/documents/upload",
            files={"file": ("index.txt", file, "text/plain")},
        )
        document_id = upload_response.json()["document"]["id"]

        chunks_response = client.get(f"/api/documents/{document_id}/chunks")
        chunks = chunks_response.json()["chunks"]

        assert chunks[0]["chunk_index"] == 0

    def test_empty_text_returns_empty_list(self) -> None:
        """Test that empty text returns empty list."""
        chunker = TextChunker()

        chunks = chunker.chunk("")

        assert len(chunks) == 0


class TestFakeEmbeddingProvider:
    """Tests for FakeEmbeddingProvider."""

    def test_embedding_deterministic(self) -> None:
        """Test that same text produces same embedding."""
        provider = FakeEmbeddingProvider(dimension=1536)
        text = "Test text for embedding"

        embedding1 = provider.embed(text)
        embedding2 = provider.embed(text)

        assert embedding1 == embedding2

    def test_embedding_dimension_correct(self) -> None:
        """Test that embedding dimension is correct."""
        provider = FakeEmbeddingProvider(dimension=1536)
        text = "Test text"

        embedding = provider.embed(text)

        assert len(embedding) == 1536

    def test_different_text_different_embedding(self) -> None:
        """Test that different texts produce different embeddings."""
        provider = FakeEmbeddingProvider(dimension=1536)

        embedding1 = provider.embed("First text")
        embedding2 = provider.embed("Second text")

        assert embedding1 != embedding2

    def test_embedding_values_in_range(self) -> None:
        """Test that embedding values are in valid range."""
        provider = FakeEmbeddingProvider(dimension=100)
        text = "Test text"

        embedding = provider.embed(text)

        for value in embedding:
            assert -1.0 <= value <= 1.0

    def test_custom_dimension(self) -> None:
        """Test that custom dimension works."""
        provider = FakeEmbeddingProvider(dimension=384)
        text = "Test text"

        embedding = provider.embed(text)

        assert len(embedding) == 384


class TestIntegration:
    """Integration tests combining multiple operations."""

    def test_full_document_workflow(self, client: TestClient) -> None:
        """Test full document workflow: upload, get, chunks, delete."""
        # Upload
        content = b"Full workflow test document content."
        file = io.BytesIO(content)
        upload_response = client.post(
            "/api/documents/upload",
            files={"file": ("workflow.txt", file, "text/plain")},
        )

        assert upload_response.status_code == 201
        document_id = upload_response.json()["document"]["id"]

        # Get document
        get_response = client.get(f"/api/documents/{document_id}")
        assert get_response.status_code == 200

        # Get chunks
        chunks_response = client.get(f"/api/documents/{document_id}/chunks")
        assert chunks_response.status_code == 200

        # Delete
        delete_response = client.delete(f"/api/documents/{document_id}")
        assert delete_response.status_code == 204

        # Verify deleted
        verify_response = client.get(f"/api/documents/{document_id}")
        assert verify_response.status_code == 404
