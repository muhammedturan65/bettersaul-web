'use client'

import { useState } from 'react'
import {
  Search as SearchIcon,
  Filter,
  Scale,
  Calendar,
  ChevronRight,
  Sparkles,
  X,
  FileText,
} from 'lucide-react'
import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { cn } from '@/lib/utils'

interface Decision {
  id: string
  court: string | null
  courtChamber: string | null
  decisionNumber: string | null
  caseNumber: string | null
  decisionDate: string | null
  documentType: string | null
  title: string | null
  summary: string | null
  keywords: string | null
  topics: string | null
  similarityScore: number | null
  fullText: string
}

interface SearchResponse {
  query: string
  expandedQuery: string[] | null
  total: number
  results: Decision[]
  durationMs: number
  searchType: string
}

const COURTS = ['all', 'Yargıtay', 'Danıştay', 'Emsal', 'Anayasa Mahkemesi']

export function SearchView() {
  const [query, setQuery] = useState('')
  const [court, setCourt] = useState('all')
  const [searchType, setSearchType] = useState<'semantic' | 'keyword' | 'hybrid'>('hybrid')
  const [results, setResults] = useState<Decision[]>([])
  const [expandedQuery, setExpandedQuery] = useState<string[] | null>(null)
  const [total, setTotal] = useState(0)
  const [durationMs, setDurationMs] = useState(0)
  const [loading, setLoading] = useState(false)
  const [searched, setSearched] = useState(false)
  const [selected, setSelected] = useState<Decision | null>(null)

  async function handleSearch(e?: React.FormEvent) {
    if (e) e.preventDefault()
    if (!query.trim()) return

    setLoading(true)
    setSearched(true)
    try {
      const res = await fetch('/api/legal/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query, court, searchType }),
      })
      const data: SearchResponse = await res.json()
      setResults(data.results)
      setTotal(data.total)
      setDurationMs(data.durationMs)
      setExpandedQuery(data.expandedQuery)
    } catch {
      setResults([])
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="p-4 sm:p-6 lg:p-8 space-y-6 max-w-[1600px] mx-auto">
      {/* Search header */}
      <Card className="border-border/60 p-5 sm:p-6">
        <form onSubmit={handleSearch} className="space-y-4">
          <div className="flex items-center gap-2 mb-1">
            <Sparkles className="w-4 h-4 text-accent" />
            <span className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
              AI Destekli Hybrid Search
            </span>
          </div>
          <div className="flex flex-col sm:flex-row gap-2">
            <div className="relative flex-1">
              <SearchIcon className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
              <Input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Örn: güvenlik soruşturması nedeniyle kamu görevine atanmama"
                className="h-12 pl-10 pr-4 text-base border-border bg-background"
                autoFocus
              />
            </div>
            <Button
              type="submit"
              disabled={loading || !query.trim()}
              className="h-12 px-6 brass-bar text-sidebar hover:opacity-90 font-semibold shadow-sm"
            >
              {loading ? (
                <>
                  <div className="w-4 h-4 border-2 border-sidebar/30 border-t-sidebar rounded-full animate-spin mr-2" />
                  Araştırılıyor
                </>
              ) : (
                <>
                  <SearchIcon className="w-4 h-4 mr-2" />
                  Ara
                </>
              )}
            </Button>
          </div>

          {/* Filters */}
          <div className="flex flex-wrap items-center gap-3">
            <div className="flex items-center gap-2">
              <Filter className="w-3.5 h-3.5 text-muted-foreground" />
              <span className="text-xs text-muted-foreground">Mahkeme:</span>
            </div>
            <Select value={court} onValueChange={setCourt}>
              <SelectTrigger className="w-[160px] h-8 text-xs">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {COURTS.map((c) => (
                  <SelectItem key={c} value={c}>
                    {c === 'all' ? 'Tümü' : c}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            <div className="flex items-center gap-1 ml-2">
              {(['hybrid', 'semantic', 'keyword'] as const).map((t) => (
                <button
                  key={t}
                  type="button"
                  onClick={() => setSearchType(t)}
                  className={cn(
                    'px-2.5 py-1 text-[11px] font-medium rounded-md transition-colors',
                    searchType === t
                      ? 'bg-accent text-sidebar'
                      : 'bg-muted text-muted-foreground hover:bg-muted/70'
                  )}
                >
                  {t === 'hybrid' ? 'Hibrit' : t === 'semantic' ? 'Semantik' : 'Anahtar kelime'}
                </button>
              ))}
            </div>
          </div>

          {/* Query expansion preview */}
          {expandedQuery && expandedQuery.length > 0 && (
            <div className="pt-3 border-t border-border/60">
              <div className="text-[10px] uppercase tracking-[0.18em] text-muted-foreground mb-1.5">
                AI Sorgu Genişletmesi
              </div>
              <div className="flex flex-wrap gap-1.5">
                {expandedQuery.map((q, i) => (
                  <Badge key={i} variant="outline" className="text-[10px] py-0.5 font-normal">
                    {q}
                  </Badge>
                ))}
              </div>
            </div>
          )}
        </form>
      </Card>

      {/* Results meta */}
      {searched && !loading && (
        <div className="flex items-center justify-between text-xs text-muted-foreground px-1">
          <span>
            <span className="font-mono tabular-nums text-foreground">{total.toLocaleString('tr-TR')}</span> sonuç ·{' '}
            <span className="font-mono tabular-nums">{durationMs}ms</span>
          </span>
          <span className="text-[10px] uppercase tracking-[0.18em]">
            {searchType === 'hybrid' ? 'Hibrit arama' : searchType === 'semantic' ? 'Semantic arama' : 'Keyword arama'}
          </span>
        </div>
      )}

      {/* Results list */}
      <div className="grid lg:grid-cols-3 gap-4">
        <div className={cn('space-y-3', selected && 'lg:col-span-2')}>
          {!searched ? (
            <Card className="border-border/60 p-12 text-center">
              <div className="inline-flex w-12 h-12 rounded-lg bg-accent/10 items-center justify-center mb-3">
                <SearchIcon className="w-5 h-5 text-accent" />
              </div>
              <div className="text-sm font-medium">Hukuki aramaya başlayın</div>
              <div className="text-xs text-muted-foreground mt-1 max-w-md mx-auto">
                Semantic search, anahtar kelime araması ve metadata filtreleme bir arada. AI sorgunuzu otomatik olarak genişletir.
              </div>
              <div className="mt-6 grid sm:grid-cols-2 gap-2 max-w-lg mx-auto">
                {[
                  'güvenlik soruşturması nedeniyle atanamama',
                  'işe iade davası feshin geçersizliği',
                  'anlaşmalı boşanma protokolü',
                  'tüketici kredisi faiz oranı',
                ].map((s) => (
                  <button
                    key={s}
                    onClick={() => {
                      setQuery(s)
                      setTimeout(() => handleSearch(), 100)
                    }}
                    className="text-left px-3 py-2 text-xs rounded-md border border-border/60 hover:border-accent hover:bg-accent/5 transition-colors"
                  >
                    <SearchIcon className="w-3 h-3 inline mr-2 text-muted-foreground" />
                    {s}
                  </button>
                ))}
              </div>
            </Card>
          ) : loading ? (
            [...Array(5)].map((_, i) => (
              <div key={i} className="h-32 rounded-lg shimmer" />
            ))
          ) : results.length === 0 ? (
            <Card className="border-border/60 p-12 text-center">
              <div className="text-sm font-medium">Sonuç bulunamadı</div>
              <div className="text-xs text-muted-foreground mt-1">
                Farklı bir sorgu veya arama tipi deneyin
              </div>
            </Card>
          ) : (
            results.map((d) => (
              <DecisionCard
                key={d.id}
                decision={d}
                onClick={() => setSelected(d)}
                isSelected={selected?.id === d.id}
              />
            ))
          )}
        </div>

        {/* Detail panel */}
        {selected && (
          <Card className="lg:sticky lg:top-20 h-fit border-border/60 overflow-hidden">
            <div className="flex items-center justify-between px-4 py-3 border-b border-border/60 bg-muted/30">
              <div className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                Karar Detayı
              </div>
              <button
                onClick={() => setSelected(null)}
                className="text-muted-foreground hover:text-foreground"
                aria-label="Kapat"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
            <div className="p-5 space-y-4 max-h-[70vh] overflow-y-auto scrollbar-thin">
              <div>
                <div className="flex items-center gap-2 mb-2">
                  <Badge variant="outline" className="text-[10px]">{selected.court}</Badge>
                  {selected.courtChamber && (
                    <span className="text-[11px] text-muted-foreground">{selected.courtChamber}</span>
                  )}
                </div>
                <h3 className="text-sm font-semibold leading-snug">{selected.title}</h3>
              </div>

              <div className="grid grid-cols-2 gap-3 text-xs">
                {selected.decisionNumber && (
                  <div>
                    <div className="text-[10px] uppercase text-muted-foreground">Karar No</div>
                    <div className="font-mono mt-0.5">{selected.decisionNumber}</div>
                  </div>
                )}
                {selected.decisionDate && (
                  <div>
                    <div className="text-[10px] uppercase text-muted-foreground flex items-center gap-1">
                      <Calendar className="w-3 h-3" /> Tarih
                    </div>
                    <div className="mt-0.5">
                      {new Date(selected.decisionDate).toLocaleDateString('tr-TR')}
                    </div>
                  </div>
                )}
                {selected.similarityScore && (
                  <div>
                    <div className="text-[10px] uppercase text-muted-foreground">Benzerlik</div>
                    <div className="font-mono text-accent font-semibold mt-0.5">
                      %{Math.round(selected.similarityScore * 100)}
                    </div>
                  </div>
                )}
                {selected.caseNumber && (
                  <div>
                    <div className="text-[10px] uppercase text-muted-foreground">Esas No</div>
                    <div className="font-mono mt-0.5">{selected.caseNumber}</div>
                  </div>
                )}
              </div>

              {selected.summary && (
                <div>
                  <div className="text-[10px] uppercase tracking-[0.18em] text-muted-foreground mb-1.5">
                    Özet
                  </div>
                  <p className="text-xs leading-relaxed text-foreground/85">{selected.summary}</p>
                </div>
              )}

              {selected.keywords && (
                <div>
                  <div className="text-[10px] uppercase tracking-[0.18em] text-muted-foreground mb-1.5">
                    Anahtar kelimeler
                  </div>
                  <div className="flex flex-wrap gap-1">
                    {JSON.parse(selected.keywords).map((k: string, i: number) => (
                      <Badge key={i} variant="secondary" className="text-[10px] py-0.5 font-normal">
                        {k}
                      </Badge>
                    ))}
                  </div>
                </div>
              )}

              <div>
                <div className="text-[10px] uppercase tracking-[0.18em] text-muted-foreground mb-1.5">
                  Tam metin
                </div>
                <pre className="text-[11px] leading-relaxed font-mono whitespace-pre-wrap bg-muted/40 p-3 rounded-md max-h-60 overflow-y-auto scrollbar-thin">
                  {selected.fullText}
                </pre>
              </div>

              <Button variant="outline" size="sm" className="w-full text-xs">
                <FileText className="w-3.5 h-3.5 mr-1.5" />
                Bu karar ile dilekçe oluştur
              </Button>
            </div>
          </Card>
        )}
      </div>
    </div>
  )
}

function DecisionCard({
  decision,
  onClick,
  isSelected,
}: {
  decision: Decision
  onClick: () => void
  isSelected: boolean
}) {
  return (
    <Card
      className={cn(
        'border-border/60 p-4 cursor-pointer card-hover group',
        isSelected && 'border-accent ring-1 ring-accent/30'
      )}
      onClick={onClick}
    >
      <div className="flex items-start justify-between gap-3 mb-2">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-md bg-accent/10 flex items-center justify-center shrink-0">
            <Scale className="w-3.5 h-3.5 text-accent" />
          </div>
          <div>
            <Badge variant="outline" className="text-[10px] py-0">
              {decision.court}
            </Badge>
            {decision.courtChamber && (
              <span className="text-[10px] text-muted-foreground ml-1.5">{decision.courtChamber}</span>
            )}
          </div>
        </div>
        {decision.similarityScore && (
          <div className="text-right shrink-0">
            <div className="text-[9px] uppercase text-muted-foreground">Benzerlik</div>
            <div className="text-sm font-mono tabular-nums text-accent font-bold">
              %{Math.round(decision.similarityScore * 100)}
            </div>
          </div>
        )}
      </div>
      <h4 className="text-sm font-semibold leading-snug mb-1 group-hover:text-accent transition-colors line-clamp-2">
        {decision.title}
      </h4>
      <p className="text-xs text-muted-foreground line-clamp-2 leading-relaxed">
        {decision.summary}
      </p>
      <div className="flex items-center justify-between mt-3 pt-3 border-t border-border/60">
        {decision.decisionNumber && (
          <span className="text-[10px] font-mono text-muted-foreground">{decision.decisionNumber}</span>
        )}
        {decision.decisionDate && (
          <span className="text-[10px] text-muted-foreground">
            {new Date(decision.decisionDate).toLocaleDateString('tr-TR', { day: '2-digit', month: 'short', year: 'numeric' })}
          </span>
        )}
        <ChevronRight className="w-3.5 h-3.5 text-muted-foreground group-hover:text-accent transition-colors ml-auto" />
      </div>
    </Card>
  )
}
