/* eslint-disable @typescript-eslint/no-require-imports */
/* Test reindex directly to see errors */
const { PrismaClient } = require('@prisma/client')
const db = new PrismaClient()

// Inline embed function (simplified)
const TURKISH_STOPWORDS = new Set(['acaba', 'ama', 'ancak', 'bir', 'bu', 'çok', 'da', 'de', 'için', 'ile', 've', 'ya', 'ye', 'the', 'is', 'at', 'which', 'on'])

function normalize(s) {
  return s.toLocaleLowerCase('tr-TR')
    .replace(/ı/g, 'i').replace(/ş/g, 's').replace(/ğ/g, 'g')
    .replace(/ü/g, 'u').replace(/ö/g, 'o').replace(/ç/g, 'c')
}

function tokenize(text) {
  const norm = normalize(text)
  const tokens = norm.replace(/[^\w\s]/g, ' ').split(/\s+/)
    .filter((t) => t.length > 2 && !TURKISH_STOPWORDS.has(t))
  const bigrams = []
  for (let i = 0; i < tokens.length - 1; i++) {
    bigrams.push(`${tokens[i]}_${tokens[i + 1]}`)
  }
  return [...tokens, ...bigrams]
}

function hashFn(str) {
  let h = 2166136261
  for (let i = 0; i < str.length; i++) {
    h ^= str.charCodeAt(i)
    h = Math.imul(h, 16777619)
  }
  return h | 0
}

function embed(text) {
  const tokens = tokenize(text)
  const vec = new Float32Array(256)
  for (const tok of tokens) {
    const h = hashFn(tok)
    const idx = Math.abs(h) % 256
    const sign = (h >>> 31) === 1 ? -1 : 1
    vec[idx] += sign
  }
  let norm = 0
  for (let i = 0; i < 256; i++) norm += vec[i] * vec[i]
  norm = Math.sqrt(norm)
  if (norm > 0) {
    for (let i = 0; i < 256; i++) vec[i] /= norm
  }
  return Array.from(vec)
}

function chunkText(text, chunkSize = 800, overlap = 200) {
  if (text.length <= chunkSize) return [text]
  const chunks = []
  let i = 0
  while (i < text.length) {
    const end = Math.min(i + chunkSize, text.length)
    let chunk = text.slice(i, end)
    if (end < text.length) {
      const lastDot = Math.max(chunk.lastIndexOf('.'), chunk.lastIndexOf('\n'))
      if (lastDot > chunkSize * 0.5) chunk = chunk.slice(0, lastDot + 1)
    }
    chunks.push(chunk.trim())
    i += chunk.length - overlap
    if (i >= end) break
  }
  return chunks.filter((c) => c.length > 0)
}

async function main() {
  const decisions = await db.legalDecision.findMany()
  console.log(`Found ${decisions.length} decisions`)
  let updated = 0
  let skipped = 0
  for (const d of decisions) {
    try {
      console.log(`Processing: ${d.id} - ${d.title?.slice(0, 40)}`)
      const text = `${d.title || ''} ${d.summary || ''} ${d.fullText || ''}`
      const embedding = embed(text)
      const chunks = chunkText(d.fullText || '', 800, 200)
      console.log(`  Embedding dim: ${embedding.length}, chunks: ${chunks.length}`)

      await db.legalDecision.update({
        where: { id: d.id },
        data: {
          embedding: JSON.stringify(embedding),
          embeddingModel: 'tfidf-hash-256-tr-v1',
          chunkCount: chunks.length,
        },
      })
      console.log('  ✓ Decision updated')

      await db.legalDecisionChunk.deleteMany({ where: { decisionId: d.id } })
      console.log('  ✓ Old chunks deleted')

      for (let i = 0; i < chunks.length; i++) {
        await db.legalDecisionChunk.create({
          data: {
            decisionId: d.id,
            chunkIndex: i,
            chunkText: chunks[i],
            embedding: JSON.stringify(embed(chunks[i])),
          },
        })
      }
      console.log(`  ✓ ${chunks.length} chunks created`)
      updated++
    } catch (e) {
      console.error(`  ✗ ERROR: ${e.message}`)
      skipped++
    }
  }
  console.log(`\nFinal: updated=${updated}, skipped=${skipped}, total=${decisions.length}`)
}
main().finally(() => db.$disconnect())
