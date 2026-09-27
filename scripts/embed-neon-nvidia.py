"""Re-embed all legal decisions using NVIDIA nemotron-3-embed-1b (2048-dim)."""
import psycopg2
import json
import os
import requests
import time
import sys

NEON_URL = "postgresql://neondb_owner:npg_Nct1aqdKL9hp@ep-delicate-frost-b29rat94-pooler.c-6.eu-central-1.aws.neon.tech/neondb?sslmode=require"
NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY") or open("/home/z/my-project/.nvidia.env").read().split("=", 1)[1].strip()
NVIDIA_URL = "https://integrate.api.nvidia.com/v1/embeddings"
NVIDIA_MODEL = "nvidia/nemotron-3-embed-1b"

def embed_nvidia(text):
    """Embed text via NVIDIA API."""
    res = requests.post(
        NVIDIA_URL,
        headers={
            "Authorization": f"Bearer {NVIDIA_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": NVIDIA_MODEL,
            "input": [text[:8000],],  # NVIDIA limit
            "encoding_format": "float",
        },
        timeout=30,
    )
    res.raise_for_status()
    return res.json()["data"][0]["embedding"]

def chunk_text(text, chunk_size=800, overlap=200):
    if not text or len(text) <= chunk_size:
        return [text] if text else []
    chunks = []
    i = 0
    while i < len(text):
        end = min(i + chunk_size, len(text))
        chunk = text[i:end]
        if end < len(text):
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

def main():
    print("=== Connecting to Neon ===")
    conn = psycopg2.connect(NEON_URL)
    conn.autocommit = False
    cur = conn.cursor()

    # Fetch all decisions
    cur.execute('SELECT id, title, summary, "fullText" FROM "LegalDecision" ORDER BY id')
    decisions = cur.fetchall()
    print(f"Found {len(decisions)} decisions")

    updated = 0
    for d_id, title, summary, full_text in decisions:
        try:
            # Embed document (title + summary + first chunk)
            text_for_emb = f"{title or ''}\n{summary or ''}\n{(full_text or '')[:1000]}"
            embedding = embed_nvidia(text_for_emb)
            print(f"  Embedding dim: {len(embedding)}")

            chunks = chunk_text(full_text or "", 800, 200)

            # Update decision
            cur.execute(
                'UPDATE "LegalDecision" SET embedding = %s, "embeddingModel" = %s, "chunkCount" = %s WHERE id = %s',
                (json.dumps(embedding), NVIDIA_MODEL, len(chunks), d_id)
            )

            # Delete old chunks
            cur.execute('DELETE FROM "LegalDecisionChunk" WHERE "decisionId" = %s', (d_id,))

            # Embed each chunk
            for i, chunk in enumerate(chunks):
                chunk_emb = embed_nvidia(chunk)
                cur.execute(
                    'INSERT INTO "LegalDecisionChunk" (id, "decisionId", "chunkIndex", "chunkText", embedding, metadata) VALUES (gen_random_uuid(), %s, %s, %s, %s, %s)',
                    (d_id, i, chunk, json.dumps(chunk_emb), json.dumps({"chunk_size": len(chunk), "model": NVIDIA_MODEL}))
                )

            conn.commit()
            updated += 1
            print(f"  ✓ {str(d_id)[:8]}... emb={len(embedding)}dim chunks={len(chunks)}")
            time.sleep(0.5)  # Rate limit

        except Exception as e:
            print(f"  ✗ {str(d_id)[:8]}... ERROR: {e}")
            conn.rollback()
            cur = conn.cursor()

    cur.close()
    conn.close()
    print(f"\n✓ Done: {updated}/{len(decisions)} decisions re-embedded with NVIDIA {NVIDIA_MODEL}")

if __name__ == "__main__":
    main()
