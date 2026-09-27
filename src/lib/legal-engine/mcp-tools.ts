/**
 * BetterSaul MCP Tools (port of bettersaul_mcp/server.py — 21 tools)
 * 
 * Each tool has a TypeScript implementation that wraps the database/legal-engine.
 * In production: these would call the Python FastAPI service via HTTP.
 */

import { db } from '@/lib/db'
import { embed, embedQuery, cosineSim, chunkText } from './embeddings'
import { detectTrack, getTrackById, LEGAL_TRACKS } from './tracks'

export interface ToolResult<T = any> {
  ok: boolean
  data?: T
  error?: string
  durationMs?: number
}

// ─── 1. search_bedesten ───
export async function searchBedesten(opts: {
  phrase: string
  courtTypes?: string[]
  page?: number
}): Promise<ToolResult> {
  const start = Date.now()
  try {
    const queryEmb = embed(opts.phrase)
    const decisions = await db.legalDecision.findMany({
      where: {
        OR: [
          { court: { contains: 'Yargıtay' } },
          { court: { contains: 'Danıştay' } },
          { court: { contains: 'Emsal' } },
        ],
      },
      take: 50,
      orderBy: { decisionDate: 'desc' },
    })
    const scored = decisions.map((d) => {
      const dEmb = d.embedding ? JSON.parse(d.embedding) : null
      const sim = dEmb ? cosineSim(queryEmb, dEmb) : 0
      return { ...d, similarityScore: sim }
    }).sort((a, b) => (b.similarityScore || 0) - (a.similarityScore || 0))
      .slice(0, 20)
    return { ok: true, data: scored, durationMs: Date.now() - start }
  } catch (e: any) {
    return { ok: false, error: e.message, durationMs: Date.now() - start }
  }
}

// ─── 2. search_corpus (Yargıtay) ───
export async function searchCorpus(opts: {
  phrase: string
  pages?: number
}): Promise<ToolResult> {
  return searchBedesten({ ...opts, courtTypes: ['Yargıtay'] })
}

// ─── 3. search_corpus_deep ───
export async function searchCorpusDeep(opts: {
  phrase: string
  pages?: number
}): Promise<ToolResult> {
  // In production: paginate portal results
  return searchBedesten(opts)
}

// ─── 4. search_emsal ───
export async function searchEmsal(opts: { keyword: string; page?: number }): Promise<ToolResult> {
  const start = Date.now()
  try {
    const queryEmb = embed(opts.keyword)
    const decisions = await db.legalDecision.findMany({
      where: { court: { contains: 'Emsal' } },
      take: 20,
    })
    const scored = decisions.map((d) => {
      const dEmb = d.embedding ? JSON.parse(d.embedding) : null
      return { ...d, similarityScore: dEmb ? cosineSim(queryEmb, dEmb) : 0 }
    }).sort((a, b) => (b.similarityScore || 0) - (a.similarityScore || 0))
    return { ok: true, data: scored, durationMs: Date.now() - start }
  } catch (e: any) {
    return { ok: false, error: e.message }
  }
}

// ─── 5. search_mevzuat ───
export async function searchMevzuat(opts: { query: string; statuteNo?: string }): Promise<ToolResult> {
  const start = Date.now()
  try {
    const where: any = {}
    if (opts.statuteNo) where.statuteNo = opts.statuteNo
    const statutes = await db.statute.findMany({
      where,
      include: { articles: { where: { effectiveTo: null } } },
    })
    const queryEmb = embed(opts.query)
    const scored = statutes.map((s) => {
      const text = `${s.name} ${s.articles.map((a) => a.bodyText).join(' ')}`
      const emb = embed(text)
      return { ...s, similarityScore: cosineSim(queryEmb, emb) }
    }).sort((a, b) => (b.similarityScore || 0) - (a.similarityScore || 0))
    return { ok: true, data: scored, durationMs: Date.now() - start }
  } catch (e: any) {
    return { ok: false, error: e.message }
  }
}

// ─── 6. search_anayasa (AYM) ───
export async function searchAnayasa(opts: { query: string; kind?: 'BB' | 'ND' }): Promise<ToolResult> {
  const start = Date.now()
  try {
    const queryEmb = embed(opts.query)
    const decisions = await db.legalDecision.findMany({
      where: { court: { contains: 'Anayasa' } },
      take: 20,
    })
    const scored = decisions.map((d) => {
      const dEmb = d.embedding ? JSON.parse(d.embedding) : null
      return { ...d, similarityScore: dEmb ? cosineSim(queryEmb, dEmb) : 0 }
    }).sort((a, b) => (b.similarityScore || 0) - (a.similarityScore || 0))
    return { ok: true, data: scored, durationMs: Date.now() - start }
  } catch (e: any) {
    return { ok: false, error: e.message }
  }
}

// ─── 7. search_resmi_gazete ───
export async function searchResmiGazete(opts: {
  query: string
  dateStart?: string
  dateEnd?: string
}): Promise<ToolResult> {
  // In production: scrape Resmî Gazete site
  return { ok: true, data: [], durationMs: 0 }
}

// ─── 8. get_bedesten_document ───
export async function getBedestenDocument(opts: { id: string }): Promise<ToolResult> {
  const decision = await db.legalDecision.findUnique({ where: { id: opts.id } })
  return decision ? { ok: true, data: decision } : { ok: false, error: 'Belge bulunamadı' }
}

// ─── 9. write_court_petition ─── (handled by petition-generation pipeline)
// ─── 10. review_petition ───
export async function reviewPetition(opts: {
  bodyText: string
  formData?: Record<string, any>
  track?: string
  memory?: { cites?: string[]; aym?: string[] }
}): Promise<ToolResult> {
  const { analyzePetition } = await import('./quality')
  const report = analyzePetition(opts)
  return { ok: true, data: report }
}

// ─── 11. save_petition_pdf ─── (handled by export endpoint)
// ─── 12. save_petition_history ─── (handled by petitions API)
// ─── 13. detect_petition_type ───
export async function detectPetitionType(opts: { text: string }): Promise<ToolResult> {
  const track = detectTrack(opts.text)
  return { ok: true, data: track }
}

// ─── 14. get_legal_tracks ───
export async function getLegalTracks(): Promise<ToolResult> {
  return {
    ok: true,
    data: LEGAL_TRACKS.map((t) => ({
      id: t.id, label: t.label, ptype: t.ptype,
      procedure: t.procedure, required: t.required,
    })),
  }
}

// ─── 15. get_track_prompt_rules ───
export async function getTrackPromptRules(opts: { trackId: string }): Promise<ToolResult> {
  const track = getTrackById(opts.trackId)
  return track ? { ok: true, data: track.promptRules } : { ok: false, error: 'Track bulunamadı' }
}

// ─── 16. expand_query ───
export async function expandQuery(opts: { query: string }): Promise<ToolResult> {
  const expansions: Record<string, string[]> = {
    'guvenlik sorusturmasi': ['arşiv araştırması', 'kamu görevine atanma', 'memuriyet', 'ölçülülük', 'özel hayat'],
    'ise iade': ['feshin geçersizliği', 'iş sözleşmesi', 'geçerli sebep', 'kıdem tazminatı'],
    'anlasmali bosanma': ['TMK 166', 'boşanma protokolü', 'velayet', 'mal paylaşımı'],
    'tuketici kredisi': ['faiz oranı', '6502 sayılı kanun', 'sözleşme iptali'],
  }
  const norm = opts.query.toLocaleLowerCase('tr-TR')
    .replace(/ı/g, 'i').replace(/ş/g, 's').replace(/ğ/g, 'g')
    .replace(/ü/g, 'u').replace(/ö/g, 'o').replace(/ç/g, 'c')
  for (const k in expansions) {
    if (norm.includes(k)) return { ok: true, data: expansions[k] }
  }
  return { ok: true, data: norm.split(' ').filter((w) => w.length > 3).slice(0, 5) }
}

// ─── 17. embed_text ───
export async function embedText(opts: { text: string }): Promise<ToolResult> {
  const vec = embed(opts.text)
  return { ok: true, data: { embedding: vec, model: 'tfidf-hash-256-tr-v1', dim: 256 } }
}

// ─── 18. semantic_search ───
export async function semanticSearch(opts: {
  query: string
  expansions?: string[]
  topK?: number
  court?: string
}): Promise<ToolResult> {
  const start = Date.now()
  const queryEmb = embedQuery(opts.query, opts.expansions || [])
  const where: any = {}
  if (opts.court && opts.court !== 'all') where.court = { contains: opts.court }

  const decisions = await db.legalDecision.findMany({
    where,
    take: 100,
    orderBy: { decisionDate: 'desc' },
  })
  const scored = decisions.map((d) => {
    const dEmb = d.embedding ? JSON.parse(d.embedding) : null
    return { ...d, similarityScore: dEmb ? cosineSim(queryEmb, dEmb) : 0 }
  })
    .filter((d) => d.similarityScore > 0.1)
    .sort((a, b) => (b.similarityScore || 0) - (a.similarityScore || 0))
    .slice(0, opts.topK || 20)
  return { ok: true, data: scored, durationMs: Date.now() - start }
}

// ─── 19. chunk_document ───
export async function chunkDocument(opts: { text: string }): Promise<ToolResult> {
  const chunks = chunkText(opts.text)
  return { ok: true, data: { chunks, count: chunks.length } }
}

// ─── 20. ping ───
export async function ping(): Promise<ToolResult> {
  return { ok: true, data: { pong: true, ts: new Date().toISOString(), version: '1.0.0' } }
}

// ─── 21. get_version ───
export async function getVersion(): Promise<ToolResult> {
  return {
    ok: true,
    data: {
      version: '1.0.0',
      phase: 2,
      tools: 21,
      embedding_model: 'tfidf-hash-256-tr-v1',
      embedding_dim: 256,
    },
  }
}

// Tool registry for dynamic dispatch
export const MCP_TOOLS: Record<string, { fn: (...args: any[]) => Promise<ToolResult>; description: string }> = {
  search_bedesten: { fn: searchBedesten, description: 'Yargıtay+Danıştay+Emsal araması' },
  search_corpus: { fn: searchCorpus, description: 'Yargıtay içtihat araması' },
  search_corpus_deep: { fn: searchCorpusDeep, description: 'Sayfa sayfa derin arama' },
  search_emsal: { fn: searchEmsal, description: 'Emsal karar arama' },
  search_mevzuat: { fn: searchMevzuat, description: 'Mevzuat arama' },
  search_anayasa: { fn: searchAnayasa, description: 'AYM kararı arama' },
  search_resmi_gazete: { fn: searchResmiGazete, description: 'Resmî Gazete arama' },
  get_bedesten_document: { fn: getBedestenDocument, description: 'Belge detayı ID ile' },
  review_petition: { fn: reviewPetition, description: 'Dilekçe kalite kontrol' },
  detect_petition_type: { fn: detectPetitionType, description: 'Dava türü tespiti' },
  get_legal_tracks: { fn: getLegalTracks, description: 'Dava türleri listesi' },
  get_track_prompt_rules: { fn: getTrackPromptRules, description: 'Track prompt kuralları' },
  expand_query: { fn: expandQuery, description: 'AI sorgu genişletme' },
  embed_text: { fn: embedText, description: 'Metin embedding' },
  semantic_search: { fn: semanticSearch, description: 'Semantic vektör arama' },
  chunk_document: { fn: chunkDocument, description: 'Belge parçalama' },
  ping: { fn: ping, description: 'Sağlık kontrolü' },
  get_version: { fn: getVersion, description: 'Sürüm bilgisi' },
}

export async function dispatchTool(name: string, args: any): Promise<ToolResult> {
  const tool = MCP_TOOLS[name]
  if (!tool) return { ok: false, error: `Bilinmeyen araç: ${name}` }
  return tool.fn(args)
}
