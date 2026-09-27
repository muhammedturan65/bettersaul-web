"""Re-embed ALL decisions in Neon with NVIDIA nemotron-3-embed-1b (2048-dim)."""
import psycopg2
import json
import requests
import time

NEON_URL = "postgresql://neondb_owner:npg_Nct1aqdKL9hp@ep-delicate-frost-b29rat94-pooler.c-6.eu-central-1.aws.neon.tech/neondb?sslmode=require"
NVIDIA_API_KEY = open("/home/z/my-project/.nvidia.env").read().split("=", 1)[1].strip()
NVIDIA_URL = "https://integrate.api.nvidia.com/v1/embeddings"
NVIDIA_MODEL = "nvidia/nemotron-3-embed-1b"


def embed_nvidia(text):
    res = requests.post(
        NVIDIA_URL,
        headers={"Authorization": f"Bearer {NVIDIA_API_KEY}", "Content-Type": "application/json"},
        json={"model": NVIDIA_MODEL, "input": [text[:8000]], "encoding_format": "float"},
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

    # Get ALL decisions
    cur.execute('SELECT id, title, summary, "fullText", "embeddingModel" FROM "LegalDecision" ORDER BY id')
    decisions = cur.fetchall()
    print(f"Total decisions: {len(decisions)}")

    # Count by model
    by_model = {}
    for d in decisions:
        model = d[4] or "none"
        by_model[model] = by_model.get(model, 0) + 1
    print(f"By model: {by_model}")

    updated = 0
    skipped = 0
    failed = 0

    for i, (d_id, title, summary, full_text, model) in enumerate(decisions):
        # Skip if already NVIDIA
        if model == NVIDIA_MODEL:
            skipped += 1
            continue

        try:
            # Embed document
            text_for_emb = f"{title or ''}\n{summary or ''}\n{(full_text or '')[:1000]}"
            embedding = embed_nvidia(text_for_emb)

            # Chunk
            chunks = chunk_text(full_text or "", 800, 200)

            # Update decision
            cur.execute(
                'UPDATE "LegalDecision" SET embedding = %s, "embeddingModel" = %s, "chunkCount" = %s WHERE id = %s',
                (json.dumps(embedding), NVIDIA_MODEL, len(chunks), d_id),
            )

            # Delete old chunks
            cur.execute('DELETE FROM "LegalDecisionChunk" WHERE "decisionId" = %s', (d_id,))

            # Insert new chunks with NVIDIA embeddings
            for ci, chunk in enumerate(chunks):
                chunk_emb = embed_nvidia(chunk)
                cur.execute(
                    'INSERT INTO "LegalDecisionChunk" (id, "decisionId", "chunkIndex", "chunkText", embedding, metadata) VALUES (gen_random_uuid(), %s, %s, %s, %s, %s)',
                    (d_id, ci, chunk, json.dumps(chunk_emb), json.dumps({"chunk_size": len(chunk), "model": NVIDIA_MODEL})),
                )

            conn.commit()
            updated += 1
            print(f"  [{updated}/{len(decisions) - skipped}] ✓ {str(d_id)[:8]}... {title[:40] if title else '?'} (emb=2048dim, chunks={len(chunks)})")
            time.sleep(0.3)  # Rate limit

        except Exception as e:
            print(f"  ✗ {str(d_id)[:8]}... ERROR: {e}")
            conn.rollback()
            cur = conn.cursor()
            failed += 1

    # Final count
    cur.execute('SELECT "embeddingModel", COUNT(*) FROM "LegalDecision" GROUP BY "embeddingModel"')
    final_counts = cur.fetchall()
    cur.execute('SELECT COUNT(*) FROM "LegalDecisionChunk"')
    total_chunks = cur.fetchone()[0]
    cur.close()
    conn.close()

    print(f"\n{'='*50}")
    print(f"✓ Updated: {updated}")
    print(f"○ Skipped (already NVIDIA): {skipped}")
    print(f"✗ Failed: {failed}")
    print(f"\nFinal embedding state:")
    for model, count in final_counts:
        print(f"  {model}: {count} karar")
    print(f"Total chunks: {total_chunks}")


if __name__ == "__main__":
    main()
