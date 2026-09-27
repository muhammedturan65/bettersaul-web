import { NextRequest, NextResponse } from 'next/server'
import { db } from '@/lib/db'
import { embedTfidf, embedAsync, embedQueryAsync, cosineSim, TFIDF_DIM, NVIDIA_DIM, EMBEDDING_MODEL } from '@/lib/legal-engine/embeddings'
import { expandQuery } from '@/lib/legal-engine/mcp-tools'

export const dynamic = 'force-dynamic'

interface SearchBody {
  query: string
  court?: string
  searchType?: 'semantic' | 'keyword' | 'hybrid'
}

function normalize(s: string): string {
  return s
    .toLocaleLowerCase('tr-TR')
    .replace(/ı/g, 'i').replace(/ş/g, 's').replace(/ğ/g, 'g')
    .replace(/ü/g, 'u').replace(/ö/g, 'o').replace(/ç/g, 'c')
    .replace(/[^\w\s]/g, ' ').replace(/\s+/g, ' ').trim()
}

export async function POST(req: NextRequest) {
  const startTime = Date.now()
  const body: SearchBody = await req.json()
  const { query, court = 'all', searchType = 'hybrid' } = body

  if (!query?.trim()) {
    return NextResponse.json({ error: 'Sorgu boş' }, { status: 400 })
  }

  try {
    const normalizedQuery = normalize(query)
    const expanded = await expandQuery({ query })
    const expandedArr = expanded.data || []

    // Build where clause
    const where: any = {}
    if (court && court !== 'all') {
      where.court = { contains: court }
    }

    // Get all candidate decisions
    const allDecisions = await db.legalDecision.findMany({
      where,
      take: 100,
      orderBy: { decisionDate: 'desc' },
    })

    // Compute query embedding (async — uses NVIDIA if available)
    const queryEmbResult = await embedQueryAsync(query, expandedArr)
    const queryEmb = queryEmbResult.embedding
    const isNvidia = queryEmbResult.model.startsWith('nvidia/')
    const queryDim = queryEmbResult.dim

    // Score each decision
    const scored = allDecisions.map((d) => {
      let semanticScore = 0
      let keywordScore = 0
      const titleNorm = normalize(d.title || '')
      const summaryNorm = normalize(d.summary || '')
      const fullTextNorm = normalize(d.fullText || '')
      const keywordsArr: string[] = d.keywords ? JSON.parse(d.keywords) : []

      // Keyword score (BM25-like)
      const queryTerms = normalizedQuery.split(' ').filter((w) => w.length > 2)
      for (const term of queryTerms) {
        if (titleNorm.includes(term)) keywordScore += 3
        if (summaryNorm.includes(term)) keywordScore += 2
        if (fullTextNorm.includes(term)) keywordScore += 1
      }
      for (const exp of expandedArr) {
        const expNorm = normalize(exp)
        if (titleNorm.includes(expNorm) || summaryNorm.includes(expNorm)) keywordScore += 2
        for (const kw of keywordsArr) {
          if (normalize(kw).includes(expNorm)) keywordScore += 1.5
        }
      }

      // Semantic score (cosine similarity with stored embedding)
      let dEmb: number[] | null = null
      if (d.embedding) {
        try {
          dEmb = JSON.parse(d.embedding)
          // Only compare if dimensions match
          if (dEmb.length === queryDim) {
            semanticScore = cosineSim(queryEmb, dEmb)
          } else if (isNvidia) {
            // Query is NVIDIA (2048) but decision is TF-IDF (256) — live embed
            const liveEmb = embedTfidf(`${d.title} ${d.summary} ${d.fullText}`.slice(0, 2000))
            semanticScore = cosineSim(embedTfidf(`${query} ${expandedArr.join(' ')}`), liveEmb)
          }
        } catch {}
      }
      // Fallback: compute on-the-fly if no stored embedding
      if (!dEmb && !isNvidia) {
        const liveEmb = embedTfidf(`${d.title} ${d.summary} ${d.fullText}`.slice(0, 2000))
        semanticScore = cosineSim(queryEmb, liveEmb)
      }

      // Combined score
      const combinedScore =
        searchType === 'semantic' ? semanticScore :
        searchType === 'keyword' ? keywordScore / 10 :
        (semanticScore * 0.6 + Math.min(keywordScore / 10, 1) * 0.4)

      return {
        ...d,
        similarityScore: combinedScore,
        _semanticScore: semanticScore,
        _keywordScore: keywordScore,
      }
    })

    const filtered = scored
      .filter((d) => {
        if (searchType === 'keyword') return d._keywordScore > 0
        if (searchType === 'semantic') return d._semanticScore > 0.05
        return d._keywordScore > 0 || d._semanticScore > 0.05
      })
      .sort((a, b) => (b.similarityScore || 0) - (a.similarityScore || 0))
      .slice(0, 20)

    const results = filtered.map(({ _keywordScore, _semanticScore, ...d }) => ({
      id: d.id,
      court: d.court,
      courtChamber: d.courtChamber,
      decisionNumber: d.decisionNumber,
      caseNumber: d.caseNumber,
      decisionDate: d.decisionDate?.toISOString() || null,
      documentType: d.documentType,
      title: d.title,
      summary: d.summary,
      keywords: d.keywords,
      topics: d.topics,
      similarityScore: d.similarityScore,
      fullText: d.fullText,
    }))

    return NextResponse.json({
      query,
      expandedQuery: expandedArr,
      total: results.length,
      results,
      durationMs: Date.now() - startTime,
      searchType,
      embeddingModel: queryEmbResult.model,
      embeddingDim: queryDim,
    })
  } catch (error) {
    console.error('Search API error:', error)
    return NextResponse.json(
      { error: 'Arama sırasında hata oluştu', query, expandedQuery: [], total: 0, results: [], durationMs: 0, searchType },
      { status: 500 }
    )
  }
}
