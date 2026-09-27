import { NextResponse } from 'next/server'
import { getServerSession } from 'next-auth'
import { authOptions } from '@/lib/auth'
import { db } from '@/lib/db'
import { embedAsync, chunkText, TFIDF_MODEL, NVIDIA_MODEL } from '@/lib/legal-engine/embeddings'

export const dynamic = 'force-dynamic'

export async function POST() {
  const session = await getServerSession(authOptions)
  if (!session?.user) return NextResponse.json({ error: 'Yetkisiz' }, { status: 401 })
  if (session.user.role !== 'admin') {
    return NextResponse.json({ error: 'Yetersiz yetki' }, { status: 403 })
  }

  const startTime = Date.now()
  try {
    // Get all decisions that need re-embedding (no embedding OR using TF-IDF)
    const decisions = await db.legalDecision.findMany({
      where: {
        OR: [
          { embedding: null },
          { embeddingModel: { not: { equals: NVIDIA_MODEL } } },
        ],
      },
      select: { id: true, title: true, summary: true, fullText: true, embeddingModel: true },
    })

    const total = decisions.length
    let updated = 0
    let failed = 0
    const errors: string[] = []

    for (const d of decisions) {
      try {
        // Build text for embedding (title + summary + first 1000 chars of fullText)
        const textForEmb = `${d.title || ''}\n${d.summary || ''}\n${(d.fullText || '').slice(0, 1000)}`

        // Use NVIDIA if available, else TF-IDF
        const { embedding, model, dim } = await embedAsync(textForEmb)

        // Chunk the full text
        const chunks = chunkText(d.fullText || '', 800, 200)

        // Update decision with new embedding
        await db.legalDecision.update({
          where: { id: d.id },
          data: {
            embedding: JSON.stringify(embedding),
            embeddingModel: model,
            chunkCount: chunks.length,
          },
        })

        // Delete old chunks
        await db.legalDecisionChunk.deleteMany({ where: { decisionId: d.id } })

        // Create new chunks with embeddings
        for (let i = 0; i < chunks.length; i++) {
          const chunkResult = await embedAsync(chunks[i])
          // Generate a CUID-like ID for chunk
          const chunkId = `chunk_${Date.now()}_${Math.random().toString(36).slice(2, 12)}`
          await db.legalDecisionChunk.create({
            data: {
              id: chunkId,
              decisionId: d.id,
              chunkIndex: i,
              chunkText: chunks[i],
              metadata: JSON.stringify({ chunk_size: chunks[i].length, model: chunkResult.model, dim: chunkResult.dim }),
            },
          })
        }

        updated++
      } catch (e: any) {
        failed++
        errors.push(`${d.id}: ${e.message?.slice(0, 100)}`)
      }
    }

    const durationMs = Date.now() - startTime
    return NextResponse.json({
      ok: true,
      total,
      updated,
      failed,
      durationMs,
      model: process.env.NVIDIA_API_KEY ? NVIDIA_MODEL : TFIDF_MODEL,
      message: `${updated}/${total} karar NVIDIA 2048-dim ile embed edildi (${failed} hata, ${durationMs}ms)`,
      errors: errors.slice(0, 5),
    })
  } catch (e: any) {
    return NextResponse.json({ error: e.message }, { status: 500 })
  }
}
