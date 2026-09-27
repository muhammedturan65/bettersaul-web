import { NextRequest, NextResponse } from 'next/server'
import { db } from '@/lib/db'

export const dynamic = 'force-dynamic'

interface SearchBody {
  query: string
  court?: string
  searchType?: 'semantic' | 'keyword' | 'hybrid'
}

// Simple Turkish text normalization for keyword search
function normalize(s: string): string {
  return s
    .toLocaleLowerCase('tr-TR')
    .replace(/ı/g, 'i')
    .replace(/ş/g, 's')
    .replace(/ğ/g, 'g')
    .replace(/ü/g, 'u')
    .replace(/ö/g, 'o')
    .replace(/ç/g, 'c')
    .replace(/[^\w\s]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
}

// Mock query expansion (in production: LLM-based)
function expandQuery(query: string): string[] {
  const expansions: Record<string, string[]> = {
    'guvenlik sorusturmasi': ['arşiv araştırması', 'kamu görevine atanma', 'memuriyet', 'ölçülülük', 'özel hayat'],
    'ise iade': ['feshin geçersizliği', 'iş sözleşmesi', 'geçerli sebep', 'kıdem tazminatı', 'ihbar tazminatı'],
    'anlasmali bosanma': ['TMK 166', 'boşanma protokolü', 'velayet', 'mal paylaşımı'],
    'tuketici kredisi': ['faiz oranı', '6502 sayılı kanun', 'sözleşme iptali', 'tüketicinin korunması'],
    'is sozlesmesi fesih': ['işe iade', 'feshin geçerli sebebi', '4857 sayılı kanun', 'kıdem'],
  }
  const q = normalize(query)
  for (const key in expansions) {
    if (q.includes(key)) {
      return expansions[key]
    }
  }
  // Default expansion: synonyms from the query itself
  return q.split(' ').filter((w) => w.length > 3).slice(0, 5)
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
    const expanded = expandQuery(query)

    // Build where clause
    const where: any = {}
    if (court && court !== 'all') {
      where.court = { contains: court }
    }

    // Get all candidate decisions (in production: pgvector + BM25)
    const allDecisions = await db.legalDecision.findMany({
      where,
      take: 100,
      orderBy: { decisionDate: 'desc' },
    })

    // Score each decision based on search type
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

      // Expansion match bonus
      for (const exp of expanded) {
        const expNorm = normalize(exp)
        if (titleNorm.includes(expNorm) || summaryNorm.includes(expNorm)) {
          keywordScore += 2
        }
        for (const kw of keywordsArr) {
          if (normalize(kw).includes(expNorm)) {
            keywordScore += 1.5
          }
        }
      }

      // Semantic score (mock: use pre-set similarityScore + keyword alignment)
      const baseSemantic = (d.similarityScore || 0.5)
      const expansionBonus = expanded.reduce((acc, exp) => {
        const expNorm = normalize(exp)
        return acc + (fullTextNorm.includes(expNorm) ? 0.05 : 0)
      }, 0)
      semanticScore = Math.min(0.99, baseSemantic + expansionBonus)

      // Combined score (hybrid)
      const combinedScore =
        searchType === 'semantic' ? semanticScore :
        searchType === 'keyword' ? keywordScore / 10 :
        (semanticScore * 0.6 + Math.min(keywordScore / 10, 1) * 0.4)

      return {
        ...d,
        similarityScore: combinedScore,
        _keywordScore: keywordScore,
        _semanticScore: semanticScore,
      }
    })

    // Filter & sort
    const filtered = scored
      .filter((d) => {
        if (searchType === 'keyword') return d._keywordScore > 0
        if (searchType === 'semantic') return d._semanticScore > 0.3
        return d._keywordScore > 0 || d._semanticScore > 0.3
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
      expandedQuery: expanded,
      total: results.length,
      results,
      durationMs: Date.now() - startTime,
      searchType,
    })
  } catch (error) {
    console.error('Search API error:', error)
    return NextResponse.json(
      { error: 'Arama sırasında hata oluştu', query, expandedQuery: [], total: 0, results: [], durationMs: 0, searchType },
      { status: 500 }
    )
  }
}
