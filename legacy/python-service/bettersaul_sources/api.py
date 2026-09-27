"""
BetterSaul Python Service — FastAPI Wrapper

Exposes source connectors + import worker + embedding pipeline as REST API.
Next.js admin panel calls these endpoints for real-source imports.

Run:
    uvicorn bettersaul_sources.api:app --host 0.0.0.0 --port 8001

Or via the worker script:
    python -m bettersaul_sources.api
"""
from __future__ import annotations

import logging
import os
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .worker import JobManager

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(
    title="BetterSaul Source Connector Service",
    description="Async legal source scraping + embedding pipeline for 9M+ Turkish decisions",
    version="1.0.0",
)

# CORS — allow Next.js
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:3000").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Singleton job manager
jobs = JobManager()


# ─── Models ──────────────────────────────────────────────────────────────────


class ImportRequest(BaseModel):
    source: str  # yargitay | danistay | emsal | aym | resmi_gazete | mevzuat
    query: str = "*"
    max_documents: Optional[int] = None
    concurrency: int = 5
    embedding_backend: str = "auto"  # auto | e5 | openai | tfidf


class SearchRequest(BaseModel):
    source: str
    query: str
    page: int = 1


# ─── Health & Info ───────────────────────────────────────────────────────────


@app.get("/health")
async def health():
    return {"status": "ok", "service": "bettersaul-sources", "version": "1.0.0"}


@app.get("/sources")
async def list_sources():
    from .connectors import CONNECTORS
    return {
        "sources": [
            {
                "name": name,
                "label": cls.SOURCE_NAME.title(),
                "base_url": cls.BASE_URL,
                "rate_limit_rpm": cls.RATE_LIMIT_RPM,
            }
            for name, cls in CONNECTORS.items()
        ]
    }


# ─── Search (single source) ──────────────────────────────────────────────────


@app.post("/search")
async def search(req: SearchRequest):
    """Search a single source (without writing to DB)."""
    import httpx
    from .connectors import get_connector, RateLimiter

    connector_cls = get_connector(req.source)
    client = httpx.AsyncClient(http2=True, follow_redirects=True)
    connector = connector_cls(client=client)

    try:
        resp = await connector.search(req.query, page=req.page)
        return {
            "source": req.source,
            "query": req.query,
            "page": req.page,
            "total": resp.total,
            "has_more": resp.has_more,
            "rate_limited": resp.rate_limited,
            "error": resp.error,
            "documents": [
                {
                    "source_doc_id": d.source_doc_id,
                    "court": d.court,
                    "court_chamber": d.court_chamber,
                    "decision_number": d.decision_number,
                    "title": d.title,
                    "summary": d.summary,
                    "decision_date": d.decision_date.isoformat() if d.decision_date else None,
                }
                for d in resp.documents
            ],
        }
    finally:
        await client.aclose()


# ─── Import Jobs ─────────────────────────────────────────────────────────────


@app.post("/import")
async def start_import(req: ImportRequest):
    """Start a new import job."""
    db_dsn = os.getenv(
        "DATABASE_URL",
        "postgresql://bettersaul:bettersaul@localhost:5432/bettersaul",
    )
    redis_url = os.getenv("REDIS_URL")
    embedding_backend = req.embedding_backend or os.getenv("EMBEDDING_BACKEND", "auto")

    try:
        result = await jobs.start_job(
            source=req.source,
            query=req.query,
            max_documents=req.max_documents,
            concurrency=req.concurrency,
            db_dsn=db_dsn,
            embedding_backend=embedding_backend,
            redis_url=redis_url,
        )
        return result
    except Exception as e:
        logger.error(f"Failed to start import: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/import")
async def list_imports():
    """List all import jobs."""
    return {"jobs": jobs.list_jobs()}


@app.get("/import/{job_id}")
async def get_import(job_id: str):
    """Get a specific import job progress."""
    job = jobs.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@app.post("/import/{job_id}/pause")
async def pause_import(job_id: str):
    if not jobs.pause_job(job_id):
        raise HTTPException(status_code=404, detail="Job not found or not running")
    return {"ok": True}


@app.post("/import/{job_id}/resume")
async def resume_import(job_id: str):
    if not jobs.resume_job(job_id):
        raise HTTPException(status_code=404, detail="Job not found or not paused")
    return {"ok": True}


@app.post("/import/{job_id}/cancel")
async def cancel_import(job_id: str):
    if not jobs.cancel_job(job_id):
        raise HTTPException(status_code=404, detail="Job not found")
    return {"ok": True}


# ─── Embedding endpoints ─────────────────────────────────────────────────────


class EmbedRequest(BaseModel):
    texts: list[str]
    backend: str = "auto"


@app.post("/embed")
async def embed(req: EmbedRequest):
    """Embed texts using configured backend."""
    from .embeddings import get_embedding_backend
    backend = get_embedding_backend(req.backend)
    embeddings = await backend.embed_batch(req.texts)
    return {
        "embeddings": embeddings,
        "model": backend.MODEL_NAME,
        "dim": backend.DIM,
    }


# ─── Semantic search (PostgreSQL + pgvector) ─────────────────────────────────


class SemanticSearchRequest(BaseModel):
    query: str
    top_k: int = 20
    court: Optional[str] = None
    backend: str = "auto"


@app.post("/search/semantic")
async def semantic_search(req: SemanticSearchRequest):
    """Semantic search via pgvector cosine similarity."""
    import os
    from .embeddings import get_embedding_backend
    from .db_writer import DatabaseWriter

    backend = get_embedding_backend(req.backend)
    query_emb = (await backend.embed_batch([f"query: {req.query}"]))[0]

    db = DatabaseWriter(os.getenv("DATABASE_URL"))
    await db.connect()
    try:
        results = await db.search_semantic(query_emb, top_k=req.top_k, court=req.court)
        return {
            "query": req.query,
            "total": len(results),
            "embedding_model": backend.MODEL_NAME,
            "results": results,
        }
    finally:
        await db.close()


# ─── Main ────────────────────────────────────────────────────────────────────


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "bettersaul_sources.api:app",
        host="0.0.0.0", port=8001,
        reload=os.getenv("DEBUG") == "1",
        workers=int(os.getenv("WORKERS", "1")),
    )
