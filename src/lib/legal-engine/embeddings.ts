/**
 * BetterSaul Semantic Embedding Engine
 *
 * Multi-backend support:
 * - NVIDIA nemotron-3-embed-1b (2048-dim, recommended, real semantic)
 * - TF-IDF + hashing (256-dim, fallback, CPU-only, free)
 *
 * Backend selection via EMBEDDING_BACKEND env var:
 * - "nvidia" → use NVIDIA API (requires NVIDIA_API_KEY)
 * - "tfidf" → use local TF-IDF (default, no API needed)
 * - "auto" → try NVIDIA, fallback to TF-IDF
 */

// ─── TF-IDF Backend (fallback) ─────────────────────────────────

export const TFIDF_DIM = 256
export const TFIDF_MODEL = 'tfidf-hash-256-tr-v1'

// NVIDIA Backend
export const NVIDIA_DIM = 2048
export const NVIDIA_MODEL = 'nvidia/nemotron-3-embed-1b'
export const NVIDIA_API_URL = 'https://integrate.api.nvidia.com/v1/embeddings'

// Current active backend
export const EMBEDDING_DIM = process.env.NVIDIA_API_KEY ? NVIDIA_DIM : TFIDF_DIM
export const EMBEDDING_MODEL = process.env.NVIDIA_API_KEY ? NVIDIA_MODEL : TFIDF_MODEL

// ─── Turkish stopwords ─────────────────────────────────────────
const TURKISH_STOPWORDS = new Set([
  'acaba', 'altı', 'altında', 'ama', 'ancak', 'arada', 'artık', 'asla', 'aslında', 'ayrıca',
  'az', 'bana', 'bazı', 'belki', 'ben', 'benden', 'beni', 'benim', 'beri', 'beş',
  'bile', 'bir', 'birçok', 'biri', 'birkaç', 'birşey', 'biz', 'bize', 'bizden', 'bizi',
  'bizim', 'böyle', 'böylece', 'bu', 'buna', 'bunda', 'bundan', 'bunlar', 'bunları', 'bunların',
  'bunu', 'bunun', 'burada', 'bütün', 'çünkü', 'da', 'daha', 'dahi', 'de', 'defa',
  'değil', 'diğer', 'diye', 'doksan', 'dokuz', 'dolayı', 'dolayısıyla', 'dört', 'edecek', 'eden',
  'ederek', 'edilecek', 'ediliyor', 'edilmesi', 'ediyor', 'eğer', 'elli', 'en', 'etmesi', 'etti',
  'ettiği', 'ettiğini', 'gibi', 'göre', 'halen', 'hangi', 'hatta', 'hem', 'henüz', 'hep',
  'hepsi', 'her', 'herhangi', 'herkes', 'herkesin', 'hiç', 'hiçbir', 'için', 'içinde', 'iki',
  'ile', 'ilgili', 'ise', 'işte', 'itibaren', 'itibariyle', 'kadar', 'karşın', 'kendi', 'kendilerine',
  'kendini', 'kendisi', 'kendisine', 'kendisini', 'kez', 'ki', 'kim', 'kimden', 'kime', 'kimi',
  'kimse', 'kýrk', 'mı', 'mı', 'mı', 'nasıl', 'ne', 'neden', 'nedenle', 'nerde',
  'nerede', 'nereye', 'niye', 'niçin', 'o', 'olan', 'olarak', 'oldu', 'olduğu', 'olduğunu',
  'olduklarını', 'olmadı', 'olmadığı', 'olmak', 'olması', 'olmayan', 'olmaz', 'olsa', 'olsun', 'olup',
  'olur', 'olursa', 'oluyor', 'on', 'ona', 'ondan', 'onlar', 'onlardan', 'onları', 'onların',
  'onu', 'onun', 'otuz', 'oysa', 'öyle', 'pek', 'rağmen', 'sadece', 'sanki', 'sekiz',
  'seksen', 'sen', 'senden', 'seni', 'senin', 'siz', 'sizden', 'sizi', 'sizin', 'şey',
  'şeyden', 'şeyi', 'şeyler', 'şöyle', 'şu', 'şuna', 'şunda', 'şundan', 'şunları', 'şunu',
  'tarafından', 'trilyon', 'tüm', 'üç', 'üzere', 'var', 'vardı', 've', 'veya', 'ya',
  'yani', 'yapacak', 'yapılan', 'yapılması', 'yapıyor', 'yapmak', 'yaptı', 'yaptığı', 'yaptığını', 'yaptıkları',
  'yedi', 'yerine', 'yetmiş', 'yine', 'yirmi', 'yoksa', 'yüz', 'zaten', 'çok', 'çık',
  'çünkü', 'daha', 'de', 'değil', 'diğer', 'gibi', 'için', 'ile', 'ise', 'ki',
  'kadar', 'ne', 'o', 'olan', 'olarak', 'oldu', 'olup', 'olur', 've', 'veya',
  'yine', 'bu', 'şu', 'her', 'hiç', 'çok', 'az', 'bir', 'iki', 'üç',
])

function normalize(s: string): string {
  return s
    .toLocaleLowerCase('tr-TR')
    .replace(/ı/g, 'i').replace(/ş/g, 's').replace(/ğ/g, 'g')
    .replace(/ü/g, 'u').replace(/ö/g, 'o').replace(/ç/g, 'c')
    .replace(/İ/g, 'i')
}

function tokenize(text: string): string[] {
  const norm = normalize(text)
  const tokens = norm
    .replace(/[^\w\s]/g, ' ')
    .split(/\s+/)
    .filter((t) => t.length > 2 && !TURKISH_STOPWORDS.has(t))
  const bigrams: string[] = []
  for (let i = 0; i < tokens.length - 1; i++) {
    bigrams.push(`${tokens[i]}_${tokens[i + 1]}`)
  }
  return [...tokens, ...bigrams]
}

function fnvHash(str: string): number {
  let h = 2166136261
  for (let i = 0; i < str.length; i++) {
    h ^= str.charCodeAt(i)
    h = Math.imul(h, 16777619)
  }
  return h | 0
}

// TF-IDF embed (synchronous, local)
export function embedTfidf(text: string): number[] {
  const tokens = tokenize(text)
  const vec = new Float32Array(TFIDF_DIM)
  for (const tok of tokens) {
    const h = fnvHash(tok)
    const idx = Math.abs(h) % TFIDF_DIM
    const sign = (h >>> 31) === 1 ? -1 : 1
    vec[idx] += sign
  }
  let norm = 0
  for (let i = 0; i < TFIDF_DIM; i++) norm += vec[i] * vec[i]
  norm = Math.sqrt(norm)
  if (norm > 0) {
    for (let i = 0; i < TFIDF_DIM; i++) vec[i] /= norm
  }
  return Array.from(vec)
}

// ─── NVIDIA Backend ────────────────────────────────────────────

interface NvidiaEmbedResponse {
  data: Array<{ embedding: number[] }>
  usage: { prompt_tokens: number; total_tokens: number }
}

/**
 * NVIDIA nemotron-3-embed-1b (2048-dim)
 * Real semantic embeddings — much better than TF-IDF for Turkish legal text.
 *
 * Cost: ~$0.0000128 per 1K tokens. 9M decisions × 1000 tokens = ~$0.12 total.
 */
export async function embedNvidia(text: string): Promise<number[]> {
  const apiKey = process.env.NVIDIA_API_KEY
  if (!apiKey) throw new Error('NVIDIA_API_KEY not set')

  const res = await fetch(NVIDIA_API_URL, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${apiKey}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      model: NVIDIA_MODEL,
      input: [text],
      encoding_format: 'float',
    }),
  })

  if (!res.ok) {
    const err = await res.text()
    throw new Error(`NVIDIA embed error ${res.status}: ${err.slice(0, 200)}`)
  }

  const data: NvidiaEmbedResponse = await res.json()
  return data.data[0].embedding
}

/**
 * Batch embed multiple texts via NVIDIA (more efficient — 1 API call for many texts)
 */
export async function embedNvidiaBatch(texts: string[]): Promise<number[][]> {
  const apiKey = process.env.NVIDIA_API_KEY
  if (!apiKey) throw new Error('NVIDIA_API_KEY not set')

  // NVIDIA allows up to 64 inputs per call
  const BATCH_SIZE = 32
  const results: number[][] = []

  for (let i = 0; i < texts.length; i += BATCH_SIZE) {
    const batch = texts.slice(i, i + BATCH_SIZE)
    const res = await fetch(NVIDIA_API_URL, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${apiKey}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        model: NVIDIA_MODEL,
        input: batch,
        encoding_format: 'float',
      }),
    })

    if (!res.ok) {
      const err = await res.text()
      throw new Error(`NVIDIA batch embed error ${res.status}: ${err.slice(0, 200)}`)
    }

    const data: NvidiaEmbedResponse = await res.json()
    for (const item of data.data) {
      results.push(item.embedding)
    }
  }

  return results
}

// ─── Unified API (auto-selects backend) ────────────────────────

/**
 * Embed text — uses NVIDIA if NVIDIA_API_KEY set, falls back to TF-IDF.
 * Sync version (TF-IDF only). For NVIDIA, use embedAsync.
 */
export function embed(text: string): number[] {
  return embedTfidf(text)
}

/**
 * Async embed — uses NVIDIA if available, else TF-IDF.
 * This is the recommended function for production.
 */
export async function embedAsync(text: string): Promise<{ embedding: number[]; model: string; dim: number }> {
  const backend = process.env.EMBEDDING_BACKEND || 'auto'

  if (backend === 'tfidf') {
    return { embedding: embedTfidf(text), model: TFIDF_MODEL, dim: TFIDF_DIM }
  }

  if (backend === 'nvidia' || (backend === 'auto' && process.env.NVIDIA_API_KEY)) {
    try {
      const embedding = await embedNvidia(text)
      return { embedding, model: NVIDIA_MODEL, dim: NVIDIA_DIM }
    } catch (e) {
      console.error('NVIDIA embed failed, falling back to TF-IDF:', e)
      if (backend === 'nvidia') throw e
    }
  }

  return { embedding: embedTfidf(text), model: TFIDF_MODEL, dim: TFIDF_DIM }
}

// ─── Utilities ─────────────────────────────────────────────────

// Cosine similarity (vectors must be L2-normalized)
export function cosineSim(a: number[], b: number[]): number {
  if (a.length !== b.length) return 0
  let dot = 0
  for (let i = 0; i < a.length; i++) dot += a[i] * b[i]
  return dot
}

// Chunk text into ~800-char chunks with 200-char overlap
export function chunkText(text: string, chunkSize = 500, overlap = 100): string[] {
  if (text.length <= chunkSize) return [text]
  const chunks: string[] = []
  let i = 0
  while (i < text.length) {
    const end = Math.min(i + chunkSize, text.length)
    let chunk = text.slice(i, end)
    if (end < text.length) {
      const lastDot = Math.max(chunk.lastIndexOf('.'), chunk.lastIndexOf('\n'))
      if (lastDot > chunkSize * 0.5) {
        chunk = chunk.slice(0, lastDot + 1)
      }
    }
    chunks.push(chunk.trim())
    i += chunk.length - overlap
    if (i >= end) break
  }
  return chunks.filter((c) => c.length > 0)
}

// Compute query embedding with expansion
export function embedQuery(text: string, expansions: string[] = []): number[] {
  // Sync version (TF-IDF only) — for backward compat
  const expandedText = expansions.length > 0
    ? `${text} ${expansions.join(' ')}`
    : text
  return embedTfidf(expandedText)
}

export async function embedQueryAsync(text: string, expansions: string[] = []): Promise<{ embedding: number[]; model: string; dim: number }> {
  const expandedText = expansions.length > 0
    ? `${text} ${expansions.join(' ')}`
    : text
  return embedAsync(expandedText)
}
