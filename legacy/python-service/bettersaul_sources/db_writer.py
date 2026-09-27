"""
BetterSaul Source Connector — Database Writer

Bulk insert legal decisions + chunks + embeddings to PostgreSQL + pgvector.
Uses COPY for maximum throughput (~10K rows/sec on single connection).
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Iterable

import asyncpg

from .connectors import LegalDocument
from .embeddings import chunk_text

logger = logging.getLogger(__name__)


class DatabaseWriter:
    """
    PostgreSQL + pgvector writer.

    Usage:
        writer = DatabaseWriter("postgresql://user:pass@localhost/bettersaul")
        await writer.connect()
        await writer.upsert_decisions(documents, embeddings=[...])
    """

    def __init__(self, dsn: str, pool_size: int = 10):
        self.dsn = dsn
        self.pool_size = pool_size
        self._pool: asyncpg.Pool | None = None

    async def connect(self):
        self._pool = await asyncpg.create_pool(
            dsn=self.dsn,
            min_size=2,
            max_size=self.pool_size,
            max_queries=100_000,
            command_timeout=120,
        )
        async with self._pool.acquire() as conn:
            # Ensure pgvector extension
            await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
            await conn.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")  # for keyword search
        logger.info(f"DatabaseWriter connected: {self.dsn} (pool={self.pool_size})")

    async def close(self):
        if self._pool:
            await self._pool.close()

    async def ensure_schema(self):
        """Create tables if not exist."""
        async with self._pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS legal_sources (
                    id SERIAL PRIMARY KEY,
                    name TEXT UNIQUE NOT NULL,
                    label TEXT NOT NULL,
                    base_url TEXT,
                    api_url TEXT,
                    last_synced_at TIMESTAMPTZ,
                    enabled BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                );
            """)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS legal_decisions (
                    id BIGSERIAL PRIMARY KEY,
                    source_id INT REFERENCES legal_sources(id),
                    source_doc_id TEXT,
                    court TEXT,
                    court_chamber TEXT,
                    decision_number TEXT,
                    case_number TEXT,
                    decision_date DATE,
                    document_type TEXT,
                    title TEXT,
                    full_text TEXT,
                    summary TEXT,
                    keywords JSONB,
                    topics JSONB,
                    citations JSONB,
                    metadata JSONB,
                    embedding vector(1024),
                    embedding_model TEXT,
                    chunk_count INT DEFAULT 0,
                    scraped_at TIMESTAMPTZ DEFAULT NOW(),
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    updated_at TIMESTAMPTZ DEFAULT NOW(),
                    UNIQUE (source_id, source_doc_id)
                );
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_legal_decisions_source
                ON legal_decisions (source_id, decision_date DESC);
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_legal_decisions_court
                ON legal_decisions (court, court_chamber);
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_legal_decisions_text_trgm
                ON legal_decisions USING gin (title gin_trgm_ops);
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_legal_decisions_emb_hnsw
                ON legal_decisions USING hnsw (embedding vector_cosine_ops)
                WITH (m = 16, ef_construction = 64);
            """)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS legal_decision_chunks (
                    id BIGSERIAL PRIMARY KEY,
                    decision_id BIGINT REFERENCES legal_decisions(id) ON DELETE CASCADE,
                    chunk_index INT NOT NULL,
                    chunk_text TEXT NOT NULL,
                    embedding vector(1024),
                    metadata JSONB,
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    UNIQUE (decision_id, chunk_index)
                );
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_legal_chunks_emb_hnsw
                ON legal_decision_chunks USING hnsw (embedding vector_cosine_ops)
                WITH (m = 16, ef_construction = 64);
            """)
            # ImportJob table (synced with Next.js)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS import_jobs (
                    id TEXT PRIMARY KEY,
                    source_name TEXT NOT NULL,
                    status TEXT DEFAULT 'queued',
                    total_items INT DEFAULT 0,
                    processed_items INT DEFAULT 0,
                    failed_items INT DEFAULT 0,
                    started_at TIMESTAMPTZ,
                    completed_at TIMESTAMPTZ,
                    error_message TEXT,
                    metadata JSONB,
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    updated_at TIMESTAMPTZ DEFAULT NOW()
                );
                CREATE INDEX IF NOT EXISTS idx_import_jobs_source_status
                ON import_jobs (source_name, status);
            """)

    async def get_or_create_source(self, name: str, label: str, base_url: str = "") -> int:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "INSERT INTO legal_sources (name, label, base_url) "
                "VALUES ($1, $2, $3) ON CONFLICT (name) DO UPDATE SET label=$2 "
                "RETURNING id",
                name, label, base_url,
            )
            return row["id"]

    async def upsert_decisions(
        self,
        decisions: list[LegalDocument],
        embeddings: list[list[float]] | None = None,
        source_id: int | None = None,
    ) -> tuple[int, int]:
        """
        Bulk upsert decisions with optional pre-computed embeddings.

        Returns (inserted, updated).
        """
        if not decisions:
            return 0, 0

        async with self._pool.acquire() as conn:
            async with conn.transaction():
                inserted = 0
                updated = 0

                for i, doc in enumerate(decisions):
                    emb = embeddings[i] if embeddings else None
                    # Upsert by (source_id, source_doc_id)
                    row = await conn.fetchrow(
                        """
                        INSERT INTO legal_decisions (
                            source_id, source_doc_id, court, court_chamber,
                            decision_number, case_number, decision_date,
                            document_type, title, full_text, summary,
                            keywords, topics, citations, metadata,
                            embedding, embedding_model, chunk_count, updated_at
                        ) VALUES (
                            $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11,
                            $12, $13, $14, $15, $16, $17, $18, NOW()
                        )
                        ON CONFLICT (source_id, source_doc_id) DO UPDATE SET
                            court = EXCLUDED.court,
                            court_chamber = EXCLUDED.court_chamber,
                            decision_number = EXCLUDED.decision_number,
                            decision_date = EXCLUDED.decision_date,
                            title = EXCLUDED.title,
                            full_text = EXCLUDED.full_text,
                            summary = EXCLUDED.summary,
                            keywords = EXCLUDED.keywords,
                            embedding = EXCLUDED.embedding,
                            embedding_model = EXCLUDED.embedding_model,
                            chunk_count = EXCLUDED.chunk_count,
                            updated_at = NOW()
                        RETURNING (xmax = 0) AS inserted, id
                        """,
                        source_id, doc.source_doc_id, doc.court, doc.court_chamber,
                        doc.decision_number, doc.case_number, doc.decision_date,
                        doc.document_type, doc.title, doc.full_text, doc.summary,
                        json.dumps(doc.keywords), json.dumps(doc.topics),
                        json.dumps(doc.citations), json.dumps(doc.metadata),
                        self._format_vector(emb) if emb else None,
                        "multilingual-e5-large" if emb else None,
                        0,  # chunk_count will be updated after chunks inserted
                    )
                    if row["inserted"]:
                        inserted += 1
                    else:
                        updated += 1

                return inserted, updated

    async def upsert_chunks(
        self,
        decision_id: int,
        chunks: list[str],
        embeddings: list[list[float]] | None = None,
    ) -> int:
        """Insert chunks for a decision. Returns count."""
        if not chunks:
            return 0

        async with self._pool.acquire() as conn:
            async with conn.transaction():
                # Delete old chunks
                await conn.execute(
                    "DELETE FROM legal_decision_chunks WHERE decision_id = $1",
                    decision_id,
                )

                rows = []
                for i, chunk in enumerate(chunks):
                    emb = embeddings[i] if embeddings else None
                    rows.append((
                        decision_id, i, chunk,
                        self._format_vector(emb) if emb else None,
                        json.dumps({"chunk_size": len(chunk)}),
                    ))

                await conn.executemany(
                    """
                    INSERT INTO legal_decision_chunks (
                        decision_id, chunk_index, chunk_text, embedding, metadata
                    ) VALUES ($1, $2, $3, $4, $5)
                    ON CONFLICT (decision_id, chunk_index) DO UPDATE SET
                        chunk_text = EXCLUDED.chunk_text,
                        embedding = EXCLUDED.embedding
                    """,
                    rows,
                )

                # Update chunk count on parent
                await conn.execute(
                    "UPDATE legal_decisions SET chunk_count = $1 WHERE id = $2",
                    len(chunks), decision_id,
                )

                return len(chunks)

    def _format_vector(self, vec: list[float]) -> str:
        """Format as PostgreSQL vector literal: '[0.1,0.2,...]'"""
        return "[" + ",".join(f"{v:.6f}" for v in vec) + "]"

    async def update_import_job(
        self, job_id: str, source_name: str, status: str,
        total: int, processed: int, failed: int,
        started_at=None, completed_at=None, error_message: str = None,
    ):
        """Sync import job state with Next.js (which reads this table)."""
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO import_jobs (
                    id, source_name, status, total_items, processed_items,
                    failed_items, started_at, completed_at, error_message, updated_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, NOW())
                ON CONFLICT (id) DO UPDATE SET
                    status = EXCLUDED.status,
                    total_items = EXCLUDED.total_items,
                    processed_items = EXCLUDED.processed_items,
                    failed_items = EXCLUDED.failed_items,
                    started_at = COALESCE(EXCLUDED.started_at, import_jobs.started_at),
                    completed_at = EXCLUDED.completed_at,
                    error_message = EXCLUDED.error_message,
                    updated_at = NOW()
                """,
                job_id, source_name, status, total, processed, failed,
                started_at, completed_at, error_message,
            )

    async def search_semantic(
        self, query_embedding: list[float], top_k: int = 20,
        court: str | None = None,
    ) -> list[dict]:
        """Semantic search via cosine similarity."""
        vec = self._format_vector(query_embedding)
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, court, court_chamber, decision_number, title, summary,
                       1 - (embedding <=> $1::vector) AS similarity
                FROM legal_decisions
                WHERE embedding IS NOT NULL
                  AND ($2::text IS NULL OR court ILIKE '%' || $2 || '%')
                ORDER BY embedding <=> $1::vector
                LIMIT $3
                """,
                vec, court, top_k,
            )
            return [dict(r) for r in rows]
