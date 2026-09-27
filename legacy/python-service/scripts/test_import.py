#!/usr/bin/env python3
"""
BetterSaul Import Pipeline — Manual Test Script

Test the Python source connector end-to-end:
1. Connect to PostgreSQL + Redis
2. Search a single source (Yargıtay)
3. Start an import job (max 10 documents)
4. Monitor progress
5. Verify embeddings in DB

Usage:
    python scripts/test_import.py --source yargitay --max 10
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys

# Add package to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bettersaul_sources.worker import JobManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default="yargitay",
                        choices=["yargitay", "danistay", "emsal", "aym", "resmi_gazete", "mevzuat"])
    parser.add_argument("--max", type=int, default=10, help="Max documents to import")
    parser.add_argument("--query", default="*", help="Search query")
    parser.add_argument("--concurrency", type=int, default=3)
    parser.add_argument("--embedding", default="auto",
                        choices=["auto", "e5", "openai", "tfidf"])
    parser.add_argument("--db-url", default=os.getenv(
        "DATABASE_URL", "postgresql://bettersaul:bettersaul@localhost:5432/bettersaul"))
    parser.add_argument("--redis-url", default=os.getenv("REDIS_URL", "redis://localhost:6379"))
    args = parser.parse_args()

    logger.info(f"Starting test import: source={args.source}, max={args.max}, query={args.query}")

    manager = JobManager()
    result = await manager.start_job(
        source=args.source,
        query=args.query,
        max_documents=args.max,
        concurrency=args.concurrency,
        db_dsn=args.db_url,
        embedding_backend=args.embedding,
        redis_url=args.redis_url,
    )
    job_id = result["job_id"]
    logger.info(f"Job started: {job_id}")

    # Poll progress
    while True:
        await asyncio.sleep(2)
        job = manager.get_job(job_id)
        if not job:
            logger.error("Job not found")
            break

        logger.info(
            f"Status: {job['status']} | "
            f"Progress: {job['processed']}/{job.get('total', '?')} "
            f"({job.get('progress', 0)}%) | "
            f"Failed: {job.get('failed', 0)} | "
            f"Step: {job.get('current_step', '')}"
        )

        if job["status"] in ("completed", "failed", "cancelled"):
            break

    # Print final log
    final = manager.get_job(job_id)
    if final:
        logger.info(f"\nFinal status: {final['status']}")
        logger.info(f"Total processed: {final['processed']}")
        logger.info(f"Total failed: {final['failed']}")
        logger.info("\nLast 10 log entries:")
        for entry in final.get("log", [])[-10:]:
            logger.info(f"  [{entry['level']}] {entry['ts']}: {entry['msg']}")


if __name__ == "__main__":
    asyncio.run(main())
