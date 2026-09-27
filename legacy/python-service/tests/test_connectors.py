"""Tests for BetterSaul source connectors."""
import asyncio
import pytest
from bettersaul_sources.connectors import (
    YargitayConnector, DanistayConnector, EmsalConnector,
    AnayasaConnector, ResmiGazeteConnector, MevzuatConnector,
    CONNECTORS, get_connector, LegalDocument, SearchResponse,
)
from bettersaul_sources.embeddings import chunk_text, TfidfHashBackend


def test_chunk_text_basic():
    """Test text chunking with sentence boundary detection."""
    text = "Bu bir cümle. Bu ikinci cümle. Bu üçüncü cümle ve daha uzun bir metin parçası."
    chunks = chunk_text(text, chunk_size=50, overlap=10)
    assert len(chunks) >= 1
    assert all(isinstance(c, str) for c in chunks)


def test_chunk_text_empty():
    """Test chunking empty text."""
    assert chunk_text("") == []
    assert chunk_text(None) == []


def test_chunk_text_short():
    """Test chunking text shorter than chunk_size."""
    text = "Kısa metin."
    chunks = chunk_text(text, chunk_size=800)
    assert chunks == [text]


def test_legal_document_dataclass():
    """Test LegalDocument dataclass creation."""
    doc = LegalDocument(
        source="yargitay", source_doc_id="test-123",
        court="Yargıtay", court_chamber="9. HD",
        decision_number="E. 2024/123, K. 2024/456",
        case_number="", decision_date=None,
        document_type="decision", title="Test", full_text="Test text",
        summary="Test summary",
    )
    assert doc.source == "yargitay"
    assert doc.court_chamber == "9. HD"
    assert doc.keywords == []
    assert doc.topics == []


def test_connectors_registry():
    """Test connector registry."""
    assert "yargitay" in CONNECTORS
    assert "danistay" in CONNECTORS
    assert "emsal" in CONNECTORS
    assert "aym" in CONNECTORS
    assert "resmi_gazete" in CONNECTORS
    assert "mevzuat" in CONNECTORS

    assert get_connector("yargitay") is YargitayConnector
    assert get_connector("danistay") is DanistayConnector

    with pytest.raises(ValueError):
        get_connector("unknown")


def test_connector_rate_limits():
    """Test each connector has rate limit config."""
    for name, cls in CONNECTORS.items():
        assert cls.RATE_LIMIT_RPM > 0, f"{name} missing RATE_LIMIT_RPM"
        assert cls.RATE_LIMIT_COOLDOWN > 0, f"{name} missing RATE_LIMIT_COOLDOWN"
        assert cls.BASE_URL.startswith("https://"), f"{name} BASE_URL not HTTPS"
        assert cls.SOURCE_NAME == name, f"{name} SOURCE_NAME mismatch"


def test_tfidf_backend():
    """Test TF-IDF fallback backend."""
    backend = TfidfHashBackend()
    assert backend.DIM == 256
    assert backend.MODEL_NAME == "tfidf-hash-256-tr-v1"

    # Embed single text
    emb = backend._embed_one("işe iade davası")
    assert len(emb) == 256
    # L2 normalized
    norm = sum(v * v for v in emb) ** 0.5
    assert abs(norm - 1.0) < 0.01


@pytest.mark.asyncio
async def test_tfidf_embed_batch():
    """Test async batch embedding."""
    backend = TfidfHashBackend()
    texts = ["işe iade", "boşanma davası", "tüketici kredisi"]
    embeddings = await backend.embed_batch(texts)
    assert len(embeddings) == 3
    assert all(len(e) == 256 for e in embeddings)
