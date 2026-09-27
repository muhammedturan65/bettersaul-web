"""Compute embeddings for legal decisions in Neon PostgreSQL."""
import psycopg2
import json
import sys

sys.path.insert(0, '/home/z/my-project/legacy/python-service')

NEON_URL = "postgresql://neondb_owner:npg_Nct1aqdKL9hp@ep-delicate-frost-b29rat94-pooler.c-6.eu-central-1.aws.neon.tech/neondb?sslmode=require"

TURKISH_STOPWORDS = {
    "acaba", "ama", "ancak", "bir", "bu", "çok", "da", "de", "için", "ile",
    "ve", "ya", "ye", "ise", "ki", "kadar", "ne", "o", "olan", "olarak",
    "oldu", "olup", "olur", "ve", "veya", "yine", "bu", "şu", "her", "hiç",
    "çok", "az", "bir", "iki", "üç", "dört", "beş", "altı", "yedi", "sekiz",
    "dokuz", "on", "yirmi", "otuz", "kırk", "elli", "altmış", "yetmiş",
    "seksen", "doksan", "yüz", "bin", "milyon", "milyar", "göre", "kendi",
    "içinde", "üzerine", "şey", "olarak", "gibi", "sonra", "önce", "daha",
}

def normalize(s):
    return (s.lower()
        .replace("ı", "i").replace("ş", "s").replace("ğ", "g")
        .replace("ü", "u").replace("ö", "o").replace("ç", "c")
        .replace("İ", "i"))

def tokenize(text):
    import re
    norm = normalize(text)
    tokens = re.findall(r"\w+", norm)
    tokens = [t for t in tokens if len(t) > 2 and t not in TURKISH_STOPWORDS]
    bigrams = [f"{tokens[i]}_{tokens[i+1]}" for i in range(len(tokens) - 1)]
    return tokens + bigrams

def hash_token(token):
    h = 2166136261
    for c in token:
        h ^= ord(c)
        h = (h * 16777619) & 0xFFFFFFFF
    return h - 0x100000000 if h >= 0x80000000 else h

def embed(text):
    tokens = tokenize(text)
    vec = [0.0] * 256
    for tok in tokens:
        h = hash_token(tok)
        idx = abs(h) % 256
        sign = -1 if (h >> 31) & 1 else 1
        vec[idx] += sign
    norm = sum(v * v for v in vec) ** 0.5
    if norm > 0:
        vec = [v / norm for v in vec]
    return vec

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
    
    # First check actual table names (Prisma uses camelCase by default, but might be "LegalDecision")
    print("=== Tables in public schema ===")
    cur.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
        ORDER BY table_name
    """)
    tables = [r[0] for r in cur.fetchall()]
    print(f"Found {len(tables)} tables:")
    for t in tables:
        print(f"  - {t}")
    
    # Find the legal decisions table (Prisma usually snake_cases the table name)
    decisions_table = None
    chunks_table = None
    for t in tables:
        if 'legal' in t.lower() and 'decision' in t.lower() and 'chunk' not in t.lower():
            decisions_table = t
        elif 'legal' in t.lower() and 'decision' in t.lower() and 'chunk' in t.lower():
            chunks_table = t
    
    if not decisions_table:
        # Try Prisma naming convention: "LegalDecision"
        if "LegalDecision" in tables:
            decisions_table = "LegalDecision"
        elif "legal_decision" in tables:
            decisions_table = "legal_decision"
    
    if not chunks_table:
        if "LegalDecisionChunk" in tables:
            chunks_table = "LegalDecisionChunk"
        elif "legal_decision_chunk" in tables:
            chunks_table = "legal_decision_chunk"
    
    print(f"\nDecisions table: {decisions_table}")
    print(f"Chunks table: {chunks_table}")
    
    if not decisions_table:
        print("✗ Could not find legal decisions table")
        return
    
    # Get column names
    cur.execute("""
        SELECT column_name FROM information_schema.columns 
        WHERE table_name = %s ORDER BY ordinal_position
    """, (decisions_table,))
    cols = [r[0] for r in cur.fetchall()]
    print(f"\nColumns in {decisions_table}: {cols}")
    
    # Map column names (handle both camelCase and snake_case)
    def get_col(name_options):
        for n in name_options:
            if n in cols:
                return n
        return None
    
    id_col = get_col(['id'])
    title_col = get_col(['title'])
    summary_col = get_col(['summary'])
    full_text_col = get_col(['fullText', 'full_text'])
    emb_col = get_col(['embedding'])
    emb_model_col = get_col(['embeddingModel', 'embedding_model'])
    chunk_count_col = get_col(['chunkCount', 'chunk_count'])
    
    print(f"id={id_col} title={title_col} summary={summary_col} full_text={full_text_col} emb={emb_col}")
    
    if not emb_col:
        print("✗ No embedding column! Schema not pushed correctly.")
        return
    
    # Fetch all decisions (use quoted identifiers for Prisma's PascalCase tables)
    cur.execute(f'SELECT "{id_col}", "{title_col}", "{summary_col}", "{full_text_col}" FROM "{decisions_table}" ORDER BY "{id_col}"')
    decisions = cur.fetchall()
    print(f"\nFound {len(decisions)} decisions")
    
    updated = 0
    for d_id, title, summary, full_text in decisions:
        try:
            text = f"{title or ''} {summary or ''} {full_text or ''}"
            embedding = embed(text)
            chunks = chunk_text(full_text or "", 800, 200)
            
            # Update decision with embedding
            cur.execute(
                f'UPDATE "{decisions_table}" SET "{emb_col}" = %s::vector, "{emb_model_col}" = %s, "{chunk_count_col}" = %s WHERE "{id_col}" = %s',
                (json.dumps(embedding), "tfidf-hash-256-tr-v1", len(chunks), d_id)
            )
            
            # Delete old chunks
            if chunks_table:
                cur.execute(f'DELETE FROM "{chunks_table}" WHERE "decisionId" = %s', (d_id,))
                
                # Insert new chunks with explicit id (gen_random_uuid)
                for i, chunk in enumerate(chunks):
                    chunk_emb = embed(chunk)
                    cur.execute(
                        f"""INSERT INTO "{chunks_table}" (id, "decisionId", "chunkIndex", "chunkText", "embedding", metadata) 
                           VALUES (gen_random_uuid(), %s, %s, %s, %s::vector, %s)""",
                        (d_id, i, chunk, json.dumps(chunk_emb), json.dumps({"chunk_size": len(chunk)}))
                    )
            
            updated += 1
            print(f"  ✓ {str(d_id)[:8]}... emb=256dim chunks={len(chunks)}")
        except Exception as e:
            print(f"  ✗ {str(d_id)[:8]}... ERROR: {e}")
            conn.rollback()
            cur = conn.cursor()
    
    conn.commit()
    cur.close()
    conn.close()
    
    print(f"\n✓ Done: {updated}/{len(decisions)} decisions embedded")

if __name__ == "__main__":
    main()
