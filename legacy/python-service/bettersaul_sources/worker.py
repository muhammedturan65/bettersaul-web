"""
BetterSaul Source Connector — Import Worker

Async worker that pulls from a source, chunks, embeds, and writes to DB.
Designed for 9M+ documents: concurrent pipeline, batching, checkpointing.
"""
from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable

from .connectors import BaseConnector, LegalDocument, SearchResponse, get_connector
from .db_writer import DatabaseWriter
from .embeddings import EmbeddingBackend, chunk_text, get_embedding_backend

logger = logging.getLogger(__name__)


@dataclass
class ImportProgress:
    job_id: str
    source: str
    status: str = "queued"
    total: int = 0
    processed: int = 0
    failed: int = 0
    started_at: datetime | None = None
    completed_at: datetime | None = None
    current_step: str = ""
    log: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "job_id": self.job_id, "source": self.source, "status": self.status,
            "total": self.total, "processed": self.processed, "failed": self.failed,
            "progress": round(self.processed / self.total * 100) if self.total else 0,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "current_step": self.current_step,
            "log": self.log[-50:],  # last 50 entries
        }


class ImportWorker:
    """
    Production import worker for 9M+ documents.

    Pipeline:
        Source → Fetch page → For each doc:
            → get_document (fetch full text)
            → chunk_text (800 char, 200 overlap)
            → embed_batch (sentence-transformers)
            → DB upsert (decision + chunks + embeddings)
        → Update progress

    Concurrency:
        - Page fetch: sequential (respect rate limit)
        - Document fetch + embed: parallel (configurable concurrency)
        - DB writes: batch transaction
    """

    def __init__(
        self,
        connector: BaseConnector,
        db: DatabaseWriter,
        embedder: EmbeddingBackend,
        *,
        source_id: int,
        concurrency: int = 5,
        batch_size: int = 20,
        max_documents: int | None = None,
        on_progress: Callable[[ImportProgress], None] | None = None,
    ):
        self.connector = connector
        self.db = db
        self.embedder = embedder
        self.source_id = source_id
        self.concurrency = concurrency
        self.batch_size = batch_size
        self.max_documents = max_documents
        self.on_progress = on_progress
        self._cancelled = False
        self._paused = False
        self.progress: ImportProgress | None = None

    async def run(self, query: str = "*", job_id: str | None = None) -> ImportProgress:
        """Run full import. Returns final progress."""
        job_id = job_id or f"job_{int(time.time())}_{uuid.uuid4().hex[:8]}"
        self.progress = ImportProgress(
            job_id=job_id, source=self.connector.SOURCE_NAME,
            started_at=datetime.utcnow(),
        )
        self._log("info", f"Import started: source={self.connector.SOURCE_NAME}, query={query!r}")
        await self._notify()

        try:
            page = 1
            total_processed = 0
            total_failed = 0
            has_more = True

            # Semaphore for concurrent doc fetching
            sem = asyncio.Semaphore(self.concurrency)

            async def process_document(doc: LegalDocument) -> bool:
                async with sem:
                    if self._cancelled:
                        return False
                    while self._paused:
                        await asyncio.sleep(1)
                    try:
                        # Fetch full text if not already fetched
                        if not doc.full_text:
                            full_doc = await self.connector.get_document(doc.source_doc_id)
                            if full_doc:
                                doc.full_text = full_doc.full_text
                                if not doc.title:
                                    doc.title = full_doc.title

                        if not doc.full_text:
                            self._log("warn", f"Empty doc: {doc.source_doc_id}")
                            return False

                        # Chunk
                        chunks = chunk_text(doc.full_text)
                        doc.metadata["chunk_count"] = len(chunks)

                        # Embed document (title + summary + first chunk)
                        text_for_emb = f"{doc.title}\n{doc.summary}\n{chunks[0] if chunks else ''}"
                        doc_emb = (await self.embedder.embed_batch([text_for_emb]))[0]

                        # Embed chunks
                        chunk_embs = []
                        if chunks:
                            chunk_embs = await self.embedder.embed_batch(chunks)

                        # Write to DB
                        inserted, updated = await self.db.upsert_decisions(
                            [doc], embeddings=[doc_emb], source_id=self.source_id
                        )
                        # Get decision id
                        async with self.db._pool.acquire() as conn:
                            row = await conn.fetchrow(
                                "SELECT id FROM legal_decisions WHERE source_id=$1 AND source_doc_id=$2",
                                self.source_id, doc.source_doc_id,
                            )
                            if row:
                                await self.db.upsert_chunks(
                                    row["id"], chunks, chunk_embs if chunk_embs else None
                                )

                        return True
                    except Exception as e:
                        self._log("error", f"Doc {doc.source_doc_id} failed: {e}")
                        return False

            # Main loop: paginate through source
            while has_more and not self._cancelled:
                self.progress.current_step = f"Fetching page {page}..."
                await self._notify()

                resp: SearchResponse = await self.connector.search(query, page=page)

                if resp.rate_limited:
                    self._log("warn", f"Rate limited, pausing 60s")
                    await asyncio.sleep(60)
                    continue

                if resp.error:
                    self._log("error", f"Search error: {resp.error}")
                    break

                if not resp.documents:
                    self._log("info", f"No more documents on page {page}")
                    break

                self.progress.total = max(self.progress.total, resp.total or len(resp.documents))

                # Process batch concurrently
                tasks = [process_document(doc) for doc in resp.documents[:self.batch_size]]
                results = await asyncio.gather(*tasks, return_exceptions=True)

                batch_success = sum(1 for r in results if r is True)
                batch_failed = sum(1 for r in results if r is False or isinstance(r, Exception))

                total_processed += batch_success
                total_failed += batch_failed

                self.progress.processed = total_processed
                self.progress.failed = total_failed
                self.progress.current_step = f"Page {page}: {batch_success} ok, {batch_failed} fail"
                self._log(
                    "info",
                    f"Page {page}: {batch_success}/{len(resp.documents)} processed, "
                    f"total {total_processed} (failed {total_failed})",
                )
                await self._notify()

                # Sync to DB
                await self.db.update_import_job(
                    job_id=self.progress.job_id,
                    source_name=self.connector.SOURCE_NAME,
                    status="running",
                    total=self.progress.total,
                    processed=total_processed,
                    failed=total_failed,
                    started_at=self.progress.started_at,
                )

                # Stop if max reached
                if self.max_documents and total_processed >= self.max_documents:
                    self._log("info", f"Reached max_documents={self.max_documents}")
                    break

                if not resp.has_more:
                    has_more = False
                else:
                    page = resp.next_page or page + 1

            # Done
            self.progress.status = "completed" if not self._cancelled else "cancelled"
            self.progress.completed_at = datetime.utcnow()
            self._log("info", f"Import {self.progress.status}: {total_processed} processed, {total_failed} failed")
            await self._notify()

            await self.db.update_import_job(
                job_id=self.progress.job_id,
                source_name=self.connector.SOURCE_NAME,
                status=self.progress.status,
                total=self.progress.total,
                processed=total_processed,
                failed=total_failed,
                started_at=self.progress.started_at,
                completed_at=self.progress.completed_at,
            )

        except Exception as e:
            self.progress.status = "failed"
            self.progress.completed_at = datetime.utcnow()
            self._log("error", f"Import failed: {e}")
            await self.db.update_import_job(
                job_id=self.progress.job_id,
                source_name=self.connector.SOURCE_NAME,
                status="failed",
                total=self.progress.total,
                processed=self.progress.processed,
                failed=self.progress.failed,
                started_at=self.progress.started_at,
                completed_at=self.progress.completed_at,
                error_message=str(e),
            )

        return self.progress

    def cancel(self):
        self._cancelled = True
        self._log("warn", "Cancellation requested")

    def pause(self):
        self._paused = True
        self._log("warn", "Paused")

    def resume(self):
        self._paused = False
        self._log("info", "Resumed")

    def _log(self, level: str, msg: str):
        if self.progress:
            self.progress.log.append({
                "ts": datetime.utcnow().isoformat(),
                "level": level,
                "msg": msg,
            })
            logger.log(
                {"info": logging.INFO, "warn": logging.WARNING, "error": logging.ERROR}[level],
                f"[{self.progress.job_id}] {msg}",
            )

    async def _notify(self):
        if self.on_progress and self.progress:
            self.on_progress(self.progress)


# ─── Job Manager ─────────────────────────────────────────────────────────────


class JobManager:
    """Manages running import jobs (in-memory for single-instance)."""

    def __init__(self):
        self._jobs: dict[str, ImportWorker] = {}
        self._progress: dict[str, ImportProgress] = {}

    def list_jobs(self) -> list[dict]:
        return [p.to_dict() for p in self._progress.values()]

    def get_job(self, job_id: str) -> dict | None:
        p = self._progress.get(job_id)
        return p.to_dict() if p else None

    async def start_job(
        self,
        source: str,
        *,
        query: str = "*",
        max_documents: int | None = None,
        concurrency: int = 5,
        db_dsn: str,
        embedding_backend: str = "auto",
        redis_url: str | None = None,
    ) -> dict:
        """Start a new import job. Returns job info."""
        from .connectors import RateLimiter
        import httpx

        connector_cls = get_connector(source)
        rate_limiter = RateLimiter(redis_url)
        await rate_limiter.connect()

        client = httpx.AsyncClient(http2=True, follow_redirects=True)
        connector = connector_cls(client=client, rate_limiter=rate_limiter)

        db = DatabaseWriter(db_dsn)
        await db.connect()
        await db.ensure_schema()

        source_label = connector_cls.SOURCE_NAME.title()
        source_id = await db.get_or_create_source(source, source_label, connector_cls.BASE_URL)

        embedder = get_embedding_backend(embedding_backend)

        worker = ImportWorker(
            connector=connector, db=db, embedder=embedder,
            source_id=source_id, concurrency=concurrency,
            max_documents=max_documents,
        )
        job_id = f"job_{int(time.time())}_{uuid.uuid4().hex[:8]}"

        self._jobs[job_id] = worker
        self._progress[job_id] = worker.progress or ImportProgress(
            job_id=job_id, source=source
        )

        # Run in background
        asyncio.create_task(self._run_job(job_id, worker, query))

        return {"job_id": job_id, "source": source, "status": "queued"}

    async def _run_job(self, job_id: str, worker: ImportWorker, query: str):
        try:
            progress = await worker.run(query=query, job_id=job_id)
            self._progress[job_id] = progress
        finally:
            # Cleanup
            self._jobs.pop(job_id, None)

    def pause_job(self, job_id: str) -> bool:
        w = self._jobs.get(job_id)
        if w:
            w.pause()
            return True
        return False

    def resume_job(self, job_id: str) -> bool:
        w = self._jobs.get(job_id)
        if w:
            w.resume()
            return True
        return False

    def cancel_job(self, job_id: str) -> bool:
        w = self._jobs.get(job_id)
        if w:
            w.cancel()
            return True
        return False
