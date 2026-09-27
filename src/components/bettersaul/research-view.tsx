'use client'

import { useEffect, useState } from 'react'
import {
  GitBranch,
  Search as SearchIcon,
  FileText,
  Scale,
  CheckCircle2,
  Clock,
  ChevronRight,
  Sparkles,
} from 'lucide-react'
import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'

interface ResearchSession {
  id: string
  query: string
  track: string | null
  status: string
  startedAt: string
  completedAt: string | null
  traces: Array<{
    id: string
    stepOrder: number
    stepType: string
    stepName: string
    input: string | null
    output: string | null
    durationMs: number | null
    startedAt: string | null
    completedAt: string | null
  }>
}

const STEP_ICONS: Record<string, typeof SearchIcon> = {
  intent_detect: Sparkles,
  query_gen: FileText,
  search: SearchIcon,
  semantic_search: SearchIcon,
  rerank: GitBranch,
  verify: CheckCircle2,
  synthesize: Scale,
}

export function ResearchView() {
  const [sessions, setSessions] = useState<ResearchSession[]>([])
  const [loading, setLoading] = useState(true)
  const [selected, setSelected] = useState<ResearchSession | null>(null)

  useEffect(() => {
    fetch('/api/research')
      .then((r) => r.json())
      .then((d) => {
        setSessions(d.sessions || [])
        if (d.sessions?.length > 0) setSelected(d.sessions[0])
        setLoading(false)
      })
      .catch(() => setLoading(false))
  }, [])

  if (loading) {
    return (
      <div className="p-6 sm:p-8 space-y-4">
        {[...Array(3)].map((_, i) => (
          <div key={i} className="h-32 rounded-lg shimmer" />
        ))}
      </div>
    )
  }

  return (
    <div className="p-4 sm:p-6 lg:p-8 space-y-6 max-w-[1600px] mx-auto">
      <div>
        <h2 className="text-xl font-bold tracking-tight">Araştırma Oturumları</h2>
        <p className="text-sm text-muted-foreground">
          AI araştırmasının adımlarını şeffaf şekilde görüntüleyin
        </p>
      </div>

      {sessions.length === 0 ? (
        <Card className="border-border/60 p-12 text-center">
          <div className="inline-flex w-12 h-12 rounded-lg bg-accent/10 items-center justify-center mb-3">
            <GitBranch className="w-5 h-5 text-accent" />
          </div>
          <div className="text-sm font-medium">Henüz araştırma oturumu yok</div>
          <div className="text-xs text-muted-foreground mt-1">
            AI Asistan'dan bir soru sorun, oturum otomatik oluşturulur
          </div>
        </Card>
      ) : (
        <div className="grid lg:grid-cols-3 gap-4">
          {/* Session list */}
          <div className="space-y-3">
            {sessions.map((s) => {
              const active = selected?.id === s.id
              return (
                <Card
                  key={s.id}
                  className={cn(
                    'border-border/60 p-4 cursor-pointer card-hover',
                    active && 'border-accent ring-1 ring-accent/30'
                  )}
                  onClick={() => setSelected(s)}
                >
                  <div className="flex items-start justify-between gap-2 mb-2">
                    <Badge variant="outline" className="text-[10px]">
                      {s.track || 'genel'}
                    </Badge>
                    <Badge
                      variant="secondary"
                      className={cn(
                        'text-[10px]',
                        s.status === 'completed' ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300' :
                        s.status === 'failed' ? 'bg-red-100 text-red-700 dark:bg-red-950 dark:text-red-300' :
                        'bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-300'
                      )}
                    >
                      {s.status === 'completed' ? 'Tamamlandı' : s.status === 'failed' ? 'Başarısız' : 'Çalışıyor'}
                    </Badge>
                  </div>
                  <p className="text-sm font-medium line-clamp-2 mb-1">{s.query}</p>
                  <div className="flex items-center justify-between text-[10px] text-muted-foreground">
                    <span>{new Date(s.startedAt).toLocaleString('tr-TR', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })}</span>
                    <span>{s.traces?.length || 0} adım</span>
                  </div>
                </Card>
              )
            })}
          </div>

          {/* Trace visualization */}
          <div className="lg:col-span-2">
            {selected && <TraceView session={selected} />}
          </div>
        </div>
      )}
    </div>
  )
}

function TraceView({ session }: { session: ResearchSession }) {
  const totalDuration = session.traces.reduce((sum, t) => sum + (t.durationMs || 0), 0)

  return (
    <Card className="border-border/60 overflow-hidden">
      <div className="px-5 py-4 border-b border-border/60 bg-muted/30">
        <div className="flex items-start justify-between gap-3 mb-2">
          <div className="min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <Badge variant="outline" className="text-[10px]">{session.track || 'genel'}</Badge>
              <span className="text-[10px] text-muted-foreground">
                {new Date(session.startedAt).toLocaleString('tr-TR')}
              </span>
            </div>
            <p className="text-sm font-semibold leading-snug">{session.query}</p>
          </div>
          <div className="text-right shrink-0">
            <div className="text-[10px] uppercase text-muted-foreground">Toplam</div>
            <div className="text-sm font-mono font-semibold">{(totalDuration / 1000).toFixed(2)}s</div>
          </div>
        </div>
      </div>

      <div className="p-5">
        <div className="text-[10px] uppercase tracking-[0.18em] text-muted-foreground mb-4">
          Araştırma akışı
        </div>

        {/* Vertical timeline */}
        <div className="relative">
          <div className="absolute left-[15px] top-2 bottom-2 w-px bg-border" />
          <div className="space-y-4">
            {session.traces.map((trace, i) => {
              const Icon = STEP_ICONS[trace.stepType] || GitBranch
              const output = trace.output ? JSON.parse(trace.output) : null
              const input = trace.input ? JSON.parse(trace.input) : null

              return (
                <div key={trace.id} className="relative pl-10">
                  <div className="absolute left-0 top-0 w-8 h-8 rounded-full bg-background border-2 border-accent flex items-center justify-center">
                    <Icon className="w-3.5 h-3.5 text-accent" />
                  </div>
                  <div className="flex items-start justify-between gap-2 mb-1">
                    <div className="flex items-center gap-2">
                      <span className="text-[10px] font-mono text-muted-foreground">
                        {String(i + 1).padStart(2, '0')}
                      </span>
                      <span className="text-sm font-medium">{trace.stepName}</span>
                    </div>
                    <div className="flex items-center gap-2 text-[10px] text-muted-foreground">
                      {trace.durationMs && (
                        <span className="font-mono">{trace.durationMs}ms</span>
                      )}
                      <CheckCircle2 className="w-3 h-3 text-emerald-600" />
                    </div>
                  </div>
                  <div className="text-[11px] text-muted-foreground mb-2">
                    <span className="text-foreground/70">{trace.stepType.replace(/_/g, ' ')}</span>
                  </div>

                  {/* Output details */}
                  {output && (
                    <div className="bg-muted/40 rounded-md p-2.5 mt-1.5 text-[11px]">
                      {output.queries && (
                        <div>
                          <span className="text-muted-700 dark:text-muted-300 font-medium">Üretilen sorgular: </span>
                          <span className="font-mono">{output.queries.join(' · ')}</span>
                        </div>
                      )}
                      {output.count !== undefined && (
                        <div>
                          <span className="text-muted-700 dark:text-muted-300 font-medium">Bulunan: </span>
                          <span className="font-mono font-semibold text-accent">{output.count}</span>
                          {output.relevant && (
                            <span> · ilgili: <span className="font-mono font-semibold">{output.relevant}</span></span>
                          )}
                          {output.top_score && (
                            <span> · en yüksek skor: <span className="font-mono font-semibold">{output.top_score.toFixed(2)}</span></span>
                          )}
                          {output.final_count && (
                            <span> · final: <span className="font-mono font-semibold">{output.final_count}</span></span>
                          )}
                        </div>
                      )}
                      {output.intent && (
                        <div>
                          <span className="text-muted-700 dark:text-muted-300 font-medium">Niyet: </span>
                          <span className="font-mono">{output.intent}</span>
                          {output.track && <span> · track: <span className="font-mono">{output.track}</span></span>}
                        </div>
                      )}
                      {output.answer_length && (
                        <div>
                          <span className="text-muted-700 dark:text-muted-300 font-medium">Cevap uzunluğu: </span>
                          <span className="font-mono">{output.answer_length} karakter</span>
                        </div>
                      )}
                      {output.verified !== undefined && (
                        <div>
                          <span className="text-muted-700 dark:text-muted-300 font-medium">Doğrulanan: </span>
                          <span className="font-mono">{output.verified} / {output.verified + (output.unverified || 0)}</span>
                        </div>
                      )}
                      {output.sources && Array.isArray(output.sources) && (
                        <div>
                          <span className="text-muted-700 dark:text-muted-300 font-medium">Mevzuat: </span>
                          <span className="font-mono">{output.sources.join(', ')}</span>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </div>
      </div>
    </Card>
  )
}
