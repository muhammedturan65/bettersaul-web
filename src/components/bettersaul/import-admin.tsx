'use client'

import { useEffect, useState } from 'react'
import {
  Shield,
  Plus,
  Play,
  Pause,
  X,
  RefreshCw,
  Database,
  Loader2,
  CheckCircle2,
  Clock,
  AlertCircle,
  ChevronDown,
} from 'lucide-react'
import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Progress } from '@/components/ui/progress'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { cn } from '@/lib/utils'

interface ImportJob {
  id: string
  sourceName: string
  status: 'queued' | 'running' | 'completed' | 'failed' | 'paused'
  totalItems: number
  processedItems: number
  failedItems: number
  startedAt: string | null
  completedAt: string | null
  progress: number
  currentStep?: string
  log: Array<{ ts: string; level: 'info' | 'warn' | 'error'; msg: string }>
}

const SOURCE_INFO: Record<string, { label: string; total: number; desc: string }> = {
  yargitay: { label: 'Yargıtay', total: 4_500_000, desc: 'Tüm daireler 2000-2026' },
  danistay: { label: 'Danıştay', total: 1_200_000, desc: 'Tüm daireler 2000-2026' },
  emsal: { label: 'Emsal (UYAP)', total: 2_800_000, desc: 'Tüm mahkemeler' },
  aym: { label: 'Anayasa Mahkemesi', total: 65_000, desc: 'BB + ND kararları' },
  resmi_gazete: { label: 'Resmî Gazete', total: 350_000, desc: "1920'den günümüze" },
  mevzuat: { label: 'Mevzuat', total: 28_000, desc: 'Kanun/KK/Yönetmelik' },
}

const STATUS_CONFIG: Record<string, { label: string; color: string; icon: typeof Clock }> = {
  queued: { label: 'Sırada', color: 'text-muted-foreground', icon: Clock },
  running: { label: 'Çalışıyor', color: 'text-amber-600', icon: Loader2 },
  completed: { label: 'Tamamlandı', color: 'text-emerald-600', icon: CheckCircle2 },
  failed: { label: 'Başarısız', color: 'text-red-600', icon: AlertCircle },
  paused: { label: 'Duraklatıldı', color: 'text-amber-600', icon: Pause },
}

export function ImportAdmin() {
  const [jobs, setJobs] = useState<ImportJob[]>([])
  const [loading, setLoading] = useState(true)
  const [newSource, setNewSource] = useState('yargitay')
  const [reindexing, setReindexing] = useState(false)
  const [reindexResult, setReindexResult] = useState<{ updated: number; total: number; skipped: number; message?: string } | null>(null)
  const [expandedLog, setExpandedLog] = useState<string | null>(null)

  // Real source import state (Python service)
  const [realSource, setRealSource] = useState('yargitay')
  const [realMax, setRealMax] = useState('')
  const [realBackend, setRealBackend] = useState('auto')
  const [realStarting, setRealStarting] = useState(false)
  const [realError, setRealError] = useState('')
  const [realJobs, setRealJobs] = useState<any[]>([])
  const [realServiceStatus, setRealServiceStatus] = useState<'available' | 'unavailable' | 'unknown'>('unknown')

  async function refresh() {
    try {
      const res = await fetch('/api/import')
      const data = await res.json()
      setJobs(data.jobs || [])
    } catch {} finally {
      setLoading(false)
    }
    // Also refresh Python service jobs
    refreshRealJobs()
  }

  async function refreshRealJobs() {
    try {
      const res = await fetch('/api/import/real')
      const data = await res.json()
      if (data.available) {
        setRealServiceStatus('available')
        setRealJobs(data.jobs || [])
      } else {
        setRealServiceStatus('unavailable')
        setRealJobs([])
      }
    } catch {
      setRealServiceStatus('unavailable')
    }
  }

  async function startRealImport() {
    setRealStarting(true)
    setRealError('')
    try {
      const res = await fetch('/api/import/real', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          action: 'start',
          source: realSource,
          maxDocuments: realMax ? parseInt(realMax) : undefined,
          embeddingBackend: realBackend,
        }),
      })
      const data = await res.json()
      if (!res.ok) {
        setRealError(data.error || 'Başlatma başarısız')
      } else {
        // Refresh list after a short delay
        setTimeout(refreshRealJobs, 1000)
      }
    } catch (e: any) {
      setRealError(e.message)
    } finally {
      setRealStarting(false)
    }
  }

  useEffect(() => {
    refresh()
    const interval = setInterval(refresh, 2000) // Poll every 2s for live progress
    return () => clearInterval(interval)
  }, [])

  async function createJob() {
    await fetch('/api/import', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action: 'create', sourceName: newSource }),
    })
    refresh()
  }

  async function pauseJob(id: string) {
    await fetch('/api/import', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action: 'pause', jobId: id }),
    })
    refresh()
  }
  async function resumeJob(id: string) {
    await fetch('/api/import', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action: 'resume', jobId: id }),
    })
    refresh()
  }
  async function cancelJob(id: string) {
    await fetch('/api/import', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action: 'cancel', jobId: id }),
    })
    refresh()
  }

  async function reindex() {
    setReindexing(true)
    setReindexResult(null)
    try {
      const res = await fetch('/api/embeddings/reindex', { method: 'POST' })
      const data = await res.json()
      setReindexResult({ updated: data.updated, total: data.total })
    } finally {
      setReindexing(false)
    }
  }

  return (
    <div className="p-4 sm:p-6 lg:p-8 space-y-6 max-w-[1400px] mx-auto">
      {/* Header */}
      <div className="flex items-center gap-2">
        <Shield className="w-5 h-5 text-accent" />
        <div>
          <h2 className="text-xl font-bold tracking-tight">Admin Panel</h2>
          <p className="text-sm text-muted-foreground">Import pipeline & embedding indeksi yönetimi</p>
        </div>
      </div>

      {/* Source launcher */}
      <Card className="border-border/60 p-5">
        <div className="flex items-center gap-2 pb-3 mb-3 border-b border-border/60">
          <Database className="w-4 h-4 text-accent" />
          <h3 className="text-sm font-semibold">Yeni Import Job</h3>
        </div>
        <div className="flex flex-col sm:flex-row gap-3">
          <Select value={newSource} onValueChange={setNewSource}>
            <SelectTrigger className="flex-1 h-10">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {Object.entries(SOURCE_INFO).map(([k, v]) => (
                <SelectItem key={k} value={k}>
                  <div>
                    <div className="font-medium">{v.label}</div>
                    <div className="text-[10px] text-muted-foreground">{v.total.toLocaleString('tr-TR')} karar · {v.desc}</div>
                  </div>
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Button onClick={createJob} className="h-10 brass-bar text-sidebar hover:opacity-90 font-semibold">
            <Plus className="w-4 h-4 mr-1.5" />
            Import Başlat
          </Button>
        </div>
      </Card>

      {/* Reindex embeddings */}
      <Card className="border-border/60 p-5">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-md bg-accent/10 flex items-center justify-center">
              <RefreshCw className="w-4 h-4 text-accent" />
            </div>
            <div>
              <div className="text-sm font-medium">Embedding İndeksini Yenile</div>
              <div className="text-[11px] text-muted-foreground">
                Mevcut kararlar için TF-IDF + hashing vektörlerini (256-dim) yeniden hesapla
              </div>
            </div>
          </div>
          <Button
            onClick={reindex}
            disabled={reindexing}
            variant="outline"
            className="h-9"
          >
            {reindexing ? (
              <>
                <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" />
                Hesaplanıyor
              </>
            ) : (
              <>
                <RefreshCw className="w-3.5 h-3.5 mr-1.5" />
                Reindex
              </>
            )}
          </Button>
        </div>
        {reindexResult && (
          <div className="mt-3 px-3 py-2 rounded-md bg-emerald-50 dark:bg-emerald-950/30 border border-emerald-200 dark:border-emerald-900 text-xs">
            <CheckCircle2 className="w-3.5 h-3.5 inline mr-1.5 text-emerald-600" />
            {reindexResult.message || `${reindexResult.updated} / ${reindexResult.total} karar indekslendi (TF-IDF + hashing v1)`}
          </div>
        )}
      </Card>

      {/* Real Source Import (Python service) */}
      <Card className="border-border/60 p-5">
        <div className="flex items-center gap-2 pb-3 mb-3 border-b border-border/60">
          <Database className="w-4 h-4 text-accent" />
          <h3 className="text-sm font-semibold">Gerçek Kaynak Import (Python Service)</h3>
          <Badge variant="outline" className="text-[10px] ml-auto">
            multilingual-e5-large
          </Badge>
        </div>
        <div className="space-y-3">
          <p className="text-[11px] text-muted-foreground">
            Python source connector service'ini kullanarak <b>9M+ gerçek kararı</b> Yargıtay/Danıştay/Emsal portallarından scrape eder,
            multilingual-e5-large (1024-dim) embedding hesaplar ve PostgreSQL + pgvector'a yazar.
            Demo mod (yukarıdaki) sadece mock veri üretir.
          </p>

          <div className="grid sm:grid-cols-3 gap-2">
            <Select value={realSource} onValueChange={setRealSource}>
              <SelectTrigger className="h-9 text-xs">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {Object.entries(SOURCE_INFO).map(([k, v]) => (
                  <SelectItem key={k} value={k}>
                    <div>
                      <div className="font-medium text-xs">{v.label}</div>
                      <div className="text-[10px] text-muted-foreground">{v.total.toLocaleString('tr-TR')} karar</div>
                    </div>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Input
              type="number"
              placeholder="Max karar (boş=sınırsız)"
              value={realMax}
              onChange={(e) => setRealMax(e.target.value)}
              className="h-9 text-xs"
            />
            <Select value={realBackend} onValueChange={setRealBackend}>
              <SelectTrigger className="h-9 text-xs">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="auto">Auto (e5 → tfidf)</SelectItem>
                <SelectItem value="e5">multilingual-e5-large (1024-dim)</SelectItem>
                <SelectItem value="openai">OpenAI text-embedding-3-large (1536-dim)</SelectItem>
                <SelectItem value="tfidf">TF-IDF fallback (256-dim)</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="flex items-center gap-2">
            <Button
              onClick={startRealImport}
              disabled={realStarting}
              className="h-9 brass-bar text-sidebar hover:opacity-90 font-semibold text-xs"
            >
              {realStarting ? (
                <>
                  <Loader2 className="w-3 h-3 mr-1.5 animate-spin" />
                  Başlatılıyor
                </>
              ) : (
                <>
                  <Plus className="w-3 h-3 mr-1.5" />
                  Gerçek Import Başlat
                </>
              )}
            </Button>
            {realServiceStatus === 'available' && (
              <Badge variant="outline" className="text-[10px] text-emerald-600 border-emerald-300">
                <CheckCircle2 className="w-3 h-3 mr-1" />
                Python service hazır
              </Badge>
            )}
            {realServiceStatus === 'unavailable' && (
              <Badge variant="outline" className="text-[10px] text-amber-600 border-amber-300">
                Python service yok (mock mod)
              </Badge>
            )}
          </div>

          {realError && (
            <div className="px-3 py-2 rounded-md bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-900 text-xs text-amber-700 dark:text-amber-300">
              <AlertCircle className="w-3.5 h-3.5 inline mr-1.5" />
              {realError}
            </div>
          )}

          {realJobs.length > 0 && (
            <div className="space-y-1.5 mt-2">
              <div className="text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
                Python Service Job'ları
              </div>
              {realJobs.map((job: any) => (
                <div key={job.job_id} className="px-3 py-2 rounded-md border border-border/60 bg-muted/30 text-xs">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <Badge variant="outline" className="text-[10px]">{job.source}</Badge>
                      <span className={cn(
                        'text-[10px] font-medium',
                        job.status === 'completed' ? 'text-emerald-600' :
                        job.status === 'failed' || job.status === 'cancelled' ? 'text-red-600' :
                        'text-amber-600'
                      )}>
                        {job.status}
                      </span>
                      <span className="text-[10px] text-muted-foreground font-mono">{job.job_id.slice(-12)}</span>
                    </div>
                    <span className="font-mono text-[10px]">
                      {job.processed}/{job.total || '?'} ({job.progress || 0}%)
                    </span>
                  </div>
                  {job.current_step && (
                    <div className="text-[10px] text-muted-foreground mt-1">{job.current_step}</div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </Card>

      {/* Jobs list */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold">Import Job'ları ({jobs.length})</h3>
          <Button variant="ghost" size="sm" onClick={refresh} className="h-8 text-xs">
            <RefreshCw className="w-3 h-3 mr-1" />
            Yenile
          </Button>
        </div>

        {loading ? (
          <div className="space-y-2">
            {[...Array(2)].map((_, i) => (
              <div key={i} className="h-24 rounded-lg shimmer" />
            ))}
          </div>
        ) : jobs.length === 0 ? (
          <Card className="border-border/60 p-12 text-center">
            <div className="inline-flex w-12 h-12 rounded-lg bg-muted items-center justify-center mb-3">
              <Database className="w-5 h-5 text-muted-foreground" />
            </div>
            <div className="text-sm font-medium">Henüz import job yok</div>
            <div className="text-xs text-muted-foreground mt-1">
              Yukarıdan bir kaynak seçip import başlatın
            </div>
          </Card>
        ) : (
          <div className="space-y-2">
            {jobs.map((job) => {
              const status = STATUS_CONFIG[job.status] || STATUS_CONFIG.queued
              const StatusIcon = status.icon
              const sourceInfo = SOURCE_INFO[job.sourceName]
              const isExpanded = expandedLog === job.id
              return (
                <Card key={job.id} className="border-border/60 p-4">
                  <div className="flex items-start justify-between gap-3 mb-3">
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2 mb-1">
                        <Badge variant="outline" className="text-[10px]">
                          {sourceInfo?.label || job.sourceName}
                        </Badge>
                        <span className={cn('flex items-center gap-1 text-[10px] font-medium', status.color)}>
                          <StatusIcon className={cn('w-3 h-3', job.status === 'running' && 'animate-spin')} />
                          {status.label}
                        </span>
                        <span className="text-[10px] text-muted-foreground font-mono">{job.id.slice(-8)}</span>
                      </div>
                      {job.currentStep && job.status === 'running' && (
                        <div className="text-[11px] text-muted-foreground mb-1.5">{job.currentStep}</div>
                      )}
                      <div className="flex items-baseline justify-between mb-1">
                        <span className="text-xs font-mono tabular-nums">
                          {job.processedItems.toLocaleString('tr-TR')} / {job.totalItems.toLocaleString('tr-TR')}
                        </span>
                        <span className="text-xs font-mono text-accent font-semibold">{job.progress}%</span>
                      </div>
                      <Progress value={job.progress} className="h-1.5" />
                      <div className="flex items-center justify-between mt-2 text-[10px] text-muted-foreground">
                        <span>
                          {job.startedAt && `Başlangıç: ${new Date(job.startedAt).toLocaleTimeString('tr-TR')}`}
                          {job.completedAt && ` · Bitiş: ${new Date(job.completedAt).toLocaleTimeString('tr-TR')}`}
                        </span>
                        {job.failedItems > 0 && (
                          <span className="text-red-600">{job.failedItems} hatalı</span>
                        )}
                      </div>
                    </div>
                    <div className="flex items-center gap-1">
                      {job.status === 'running' && (
                        <Button variant="outline" size="icon" className="h-7 w-7" onClick={() => pauseJob(job.id)} title="Duraklat">
                          <Pause className="w-3 h-3" />
                        </Button>
                      )}
                      {job.status === 'paused' && (
                        <Button variant="outline" size="icon" className="h-7 w-7" onClick={() => resumeJob(job.id)} title="Devam et">
                          <Play className="w-3 h-3" />
                        </Button>
                      )}
                      {(job.status === 'running' || job.status === 'paused') && (
                        <Button variant="outline" size="icon" className="h-7 w-7" onClick={() => cancelJob(job.id)} title="İptal">
                          <X className="w-3 h-3" />
                        </Button>
                      )}
                    </div>
                  </div>
                  {/* Log */}
                  {job.log.length > 0 && (
                    <button
                      onClick={() => setExpandedLog(isExpanded ? null : job.id)}
                      className="flex items-center gap-1 text-[10px] text-muted-foreground hover:text-foreground"
                    >
                      <ChevronDown className={cn('w-3 h-3 transition-transform', isExpanded && 'rotate-180')} />
                      {job.log.length} log kaydı
                    </button>
                  )}
                  {isExpanded && (
                    <div className="mt-2 p-2.5 rounded-md bg-muted/40 max-h-40 overflow-y-auto scrollbar-thin font-mono text-[10px] space-y-0.5">
                      {job.log.slice().reverse().map((l, i) => (
                        <div key={i} className="flex gap-2">
                          <span className="text-muted-foreground/60 shrink-0">
                            {new Date(l.ts).toLocaleTimeString('tr-TR')}
                          </span>
                          <span className={cn(
                            l.level === 'error' ? 'text-red-600' :
                            l.level === 'warn' ? 'text-amber-600' : 'text-foreground/80'
                          )}>
                            {l.msg}
                          </span>
                        </div>
                      ))}
                    </div>
                  )}
                </Card>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}
