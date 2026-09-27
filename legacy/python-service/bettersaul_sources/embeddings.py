"""
BetterSaul Source Connector — Embedding & Chunking Pipeline

Production-grade embedding using sentence-transformers (multilingual-e5-large)
- 1024-dim vectors (instead of TF-IDF 256-dim mock)
- Semantic similarity for Turkish legal text
- Async batch processing for throughput

Falls back to TF-IDF hashing if sentence-transformers unavailable (dev mode).
"""
from __future__ import annotations

import asyncio
import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)

# ─── Turkish stop words (same as Next.js embeddings.ts) ──────────────────────
TURKISH_STOPWORDS = {
    "acaba", "ama", "ancak", "bir", "bu", "çok", "da", "de", "için", "ile",
    "ve", "ya", "ye", "ise", "ki", "kadar", "ne", "o", "olan", "olarak",
    "oldu", "olup", "olur", "ve", "veya", "yine", "bu", "şu", "her", "hiç",
    "çok", "az", "bir", "iki", "üç", "dört", "beş", "altı", "yedi", "sekiz",
    "dokuz", "on", "yirmi", "otuz", "kırk", "elli", "altmış", "yetmiş",
    "seksen", "doksan", "yüz", "bin", "milyon", "milyar",
}

# ─── Chunking ────────────────────────────────────────────────────────────────


def chunk_text(text: str, chunk_size: int = 800, overlap: int = 200) -> list[str]:
    """
    Chunk text into ~800-char chunks with 200-char overlap.
    Tries to break at sentence/paragraph boundary.
    """
    if not text or len(text) <= chunk_size:
        return [text] if text else []

    chunks: list[str] = []
    i = 0
    while i < len(text):
        end = min(i + chunk_size, len(text))
        chunk = text[i:end]
        if end < len(text):
            # Try to break at sentence/paragraph boundary
            last_break = max(chunk.rfind("."), chunk.rfind("\n"), chunk.rfind("!"), chunk.rfind("?"))
            if last_break > chunk_size * 0.5:
                chunk = chunk[: last_break + 1]
        chunk = chunk.strip()
        if chunk:
            chunks.append(chunk)
        i += len(chunk) - overlap
        if i >= end:
            break
    return chunks


def normalize_turkish(s: str) -> str:
    """Lowercase + deaccent Turkish characters."""
    return (
        s.lower()
        .replace("ı", "i").replace("ş", "s").replace("ğ", "g")
        .replace("ü", "u").replace("ö", "o").replace("ç", "c")
        .replace("İ", "i")
    )


def tokenize(s: str) -> list[str]:
    """Tokenize with Turkish-aware normalization + stopword removal + bigrams."""
    norm = normalize_turkish(s)
    tokens = re.findall(r"\w+", norm)
    tokens = [t for t in tokens if len(t) > 2 and t not in TURKISH_STOPWORDS]
    bigrams = [f"{tokens[i]}_{tokens[i+1]}" for i in range(len(tokens) - 1)]
    return tokens + bigrams


# ─── Embedding Backends ──────────────────────────────────────────────────────


class EmbeddingBackend:
    """Abstract embedding backend."""

    MODEL_NAME: str = ""
    DIM: int = 0

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError


class TfidfHashBackend(EmbeddingBackend):
    """Fallback: TF-IDF + hashing (same as Next.js embeddings.ts)."""

    MODEL_NAME = "tfidf-hash-256-tr-v1"
    DIM = 256

    def __hash_token(self, token: str) -> int:
        h = 2166136261
        for c in token:
            h ^= ord(c)
            h = (h * 16777619) & 0xFFFFFFFF
        # Convert to signed 32-bit
        return h - 0x100000000 if h >= 0x80000000 else h

    def _embed_one(self, text: str) -> list[float]:
        tokens = tokenize(text)
        vec = [0.0] * self.DIM
        for tok in tokens:
            h = self.__hash_token(tok)
            idx = abs(h) % self.DIM
            sign = -1 if (h >> 31) & 1 else 1
            vec[idx] += sign
        # L2 normalize
        norm = sum(v * v for v in vec) ** 0.5
        if norm > 0:
            vec = [v / norm for v in vec]
        return vec

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        # Run CPU-bound in thread pool
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, lambda: [self._embed_one(t) for t in texts]
        )


class SentenceTransformersBackend(EmbeddingBackend):
    """
    Production backend: sentence-transformers multilingual-e5-large.
    1024-dim, semantic similarity for Turkish.

    Install:
        pip install sentence-transformers torch
        # First run downloads ~2.5GB model
    """

    MODEL_NAME = "intfloat/multilingual-e5-large"
    DIM = 1024

    def __init__(self, model_name: str = None, device: str = "cpu"):
        try:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(
                model_name or self.MODEL_NAME, device=device
            )
            logger.info(f"SentenceTransformersBackend loaded: {self.MODEL_NAME} on {device}")
        except ImportError:
            raise RuntimeError(
                "sentence-transformers not installed. "
                "Install: pip install sentence-transformers torch"
            )

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        # e5 models require "query: " or "passage: " prefix
        prefixed = [f"passage: {t}" for t in texts]
        loop = asyncio.get_event_loop()

        def _encode():
            embeddings = self._model.encode(
                prefixed, batch_size=32, show_progress_bar=False,
                convert_to_numpy=True, normalize_embeddings=True,
            )
            return [emb.tolist() for emb in embeddings]

        return await loop.run_in_executor(None, _encode)


class OpenAIEmbeddingBackend(EmbeddingBackend):
    """
    Optional: OpenAI text-embedding-3-large (1536-dim).
    Requires OPENAI_API_KEY env var.

    Cost: ~$0.13 per 1M tokens. 9M decisions × 1000 tokens avg = ~$1,170 one-time.
    """

    MODEL_NAME = "text-embedding-3-large"
    DIM = 1536

    def __init__(self, api_key: str | None = None):
        import os
        self._api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self._api_key:
            raise RuntimeError("OPENAI_API_KEY not set")

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        import httpx
        async with httpx.AsyncClient(timeout=60) as client:
            # OpenAI batch limit: 2048 texts
            results: list[list[float]] = []
            for i in range(0, len(texts), 2048):
                batch = texts[i : i + 2048]
                resp = await client.post(
                    "https://api.openai.com/v1/embeddings",
                    headers={"Authorization": f"Bearer {self._api_key}"},
                    json={"input": batch, "model": self.MODEL_NAME},
                )
                resp.raise_for_status()
                data = resp.json()
                results.extend([d["embedding"] for d in data["data"]])
            return results


# ─── Backend Factory ─────────────────────────────────────────────────────────


def get_embedding_backend(preferred: str = "auto") -> EmbeddingBackend:
    """
    Get embedding backend by preference.
    - 'auto': try sentence-transformers, fallback to tfidf
    - 'e5': force multilingual-e5-large
    - 'openai': force OpenAI text-embedding-3-large
    - 'tfidf': force TF-IDF fallback
    """
    if preferred == "tfidf":
        return TfidfHashBackend()

    if preferred == "openai":
        return OpenAIEmbeddingBackend()

    if preferred in ("e5", "auto"):
        try:
            return SentenceTransformersBackend()
        except Exception as e:
            logger.warning(f"sentence-transformers unavailable ({e}), using TF-IDF")
            if preferred == "e5":
                raise
            return TfidfHashBackend()

    raise ValueError(f"Unknown backend: {preferred}")
