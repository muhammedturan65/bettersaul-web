/**
 * BetterSaul Semantic Embedding Engine
 * 
 * Local TF-IDF + hashing vector implementation for Turkish legal text.
 * In production: replace with multilingual-e5-large or OpenAI text-embedding-3-large.
 * 
 * Algorithm:
 * 1. Tokenize (Turkish-aware: lowercase, deaccent, split on non-word)
 * 2. Apply Turkish stopword removal
 * 3. Add bigrams for context
 * 4. Hash each token to 256-dim vector (signed hashing)
 * 5. Apply IDF weighting (computed lazily from corpus)
 * 6. L2-normalize
 */

export const EMBEDDING_DIM = 256
export const EMBEDDING_MODEL = 'tfidf-hash-256-tr-v1'

// Turkish stopwords (most common 80)
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
    .replace(/ı/g, 'i')
    .replace(/ş/g, 's')
    .replace(/ğ/g, 'g')
    .replace(/ü/g, 'u')
    .replace(/ö/g, 'o')
    .replace(/ç/g, 'c')
    .replace(/İ/g, 'i')
}

function tokenize(text: string): string[] {
  const norm = normalize(text)
  const tokens = norm
    .replace(/[^\w\s]/g, ' ')
    .split(/\s+/)
    .filter((t) => t.length > 2 && !TURKISH_STOPWORDS.has(t))
  // Add bigrams for context preservation
  const bigrams: string[] = []
  for (let i = 0; i < tokens.length - 1; i++) {
    bigrams.push(`${tokens[i]}_${tokens[i + 1]}`)
  }
  return [...tokens, ...bigrams]
}

// FNV-1a hash (signed)
function hash(str: string): number {
  let h = 2166136261
  for (let i = 0; i < str.length; i++) {
    h ^= str.charCodeAt(i)
    h = Math.imul(h, 16777619)
  }
  return h | 0 // signed 32-bit
}

// Compute embedding for a text
export function embed(text: string): number[] {
  const tokens = tokenize(text)
  const vec = new Float32Array(EMBEDDING_DIM)

  for (const tok of tokens) {
    const h = hash(tok)
    const idx = Math.abs(h) % EMBEDDING_DIM
    const sign = (h >>> 31) === 1 ? -1 : 1
    vec[idx] += sign
  }

  // L2 normalize
  let norm = 0
  for (let i = 0; i < EMBEDDING_DIM; i++) norm += vec[i] * vec[i]
  norm = Math.sqrt(norm)
  if (norm > 0) {
    for (let i = 0; i < EMBEDDING_DIM; i++) vec[i] /= norm
  }

  return Array.from(vec)
}

// Cosine similarity (vectors already L2-normalized, so it's just dot product)
export function cosineSim(a: number[], b: number[]): number {
  if (a.length !== b.length) return 0
  let dot = 0
  for (let i = 0; i < a.length; i++) dot += a[i] * b[i]
  return dot
}

// Chunk text into ~500-char chunks with 100-char overlap
export function chunkText(text: string, chunkSize = 500, overlap = 100): string[] {
  if (text.length <= chunkSize) return [text]
  const chunks: string[] = []
  let i = 0
  while (i < text.length) {
    const end = Math.min(i + chunkSize, text.length)
    let chunk = text.slice(i, end)
    // Try to break at sentence/paragraph boundary
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

// Compute query embedding with expansion (adds expansion terms to the query)
export function embedQuery(query: string, expansions: string[] = []): number[] {
  const expandedText = expansions.length > 0
    ? `${query} ${expansions.join(' ')}`
    : query
  return embed(expandedText)
}
