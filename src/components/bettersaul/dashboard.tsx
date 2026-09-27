'use client'

import { useEffect, useState } from 'react'
import {
  Search,
  FileText,
  MessageSquare,
  GitBranch,
  TrendingUp,
  Scale,
  ArrowUpRight,
  Clock,
  CheckCircle2,
  AlertTriangle,
  FileSearch,
  Sparkles,
  ChevronRight,
} from 'lucide-react'
import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import { cn } from '@/lib/utils'

type View = 'dashboard' | 'search' | 'petitions' | 'chat' | 'research' | 'documents'

interface DashboardData {
  stats: {
    totalPetitions: number
    totalResearch: number
    totalDocuments: number
    totalSearches: number
  }
  recentPetitions: Array<{
    id: string
    caseTitle: string
    petitionType: string
    status: string
    qualityScore: number | null
    updatedAt: string
  }>
  recentResearch: Array<{
    id: string
    query: string
    track: string | null
    status: string
    startedAt: string
    completedAt: string | null
  }>
  legalSources: Array<{
    name: string
    label: string
    lastSyncedAt: string | null
    enabled: boolean
    decisionCount: number
  }>
  recentDecisions: Array<{
    id: string
    court: string | null
    courtChamber: string | null
    decisionNumber: string | null
    title: string | null
    decisionDate: string | null
    similarityScore: number | null
  }>
}

const TRACK_LABELS: Record<string, string> = {
  is: 'İş Hukuku',
  bosanma: 'Aile Hukuku',
  idare: 'İdare Hukuku',
  tuketici: 'Tüketici Hukuku',
  kira: 'Eşya Hukuku',
  vergi: 'Vergi Hukuku',
}

const STATUS_LABELS: Record<string, { label: string; color: string }> = {
  draft: { label: 'Taslak', color: 'bg-muted text-muted-foreground' },
  reviewed: { label: 'İncelendi', color: 'bg-blue-100 text-blue-700 dark:bg-blue-950 dark:text-blue-300' },
  final: { label: 'Tamamlandı', color: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300' },
  exported: { label: 'Dışa aktarıldı', color: 'bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-300' },
  running: { label: 'Çalışıyor', color: 'bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-300' },
  completed: { label: 'Tamamlandı', color: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300' },
  failed: { label: 'Başarısız', color: 'bg-red-100 text-red-700 dark:bg-red-950 dark:text-red-300' },
}

export function Dashboard({ onNavigate }: { onNavigate: (v: View) => void }) {
  const [data, setData] = useState<DashboardData | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetch('/api/dashboard')
      .then((r) => r.json())
      .then((d) => {
        setData(d)
        setLoading(false)
      })
      .catch(() => setLoading(false))
  }, [])

  if (loading || !data) {
    return (
      <div className="p-6 sm:p-8 space-y-6">
        <div className="h-32 rounded-xl shimmer" />
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="h-28 rounded-xl shimmer" />
          ))}
        </div>
        <div className="grid lg:grid-cols-3 gap-4">
          <div className="lg:col-span-2 h-96 rounded-xl shimmer" />
          <div className="h-96 rounded-xl shimmer" />
        </div>
      </div>
    )
  }

  return (
    <div className="p-4 sm:p-6 lg:p-8 space-y-6 max-w-[1600px] mx-auto">
      {/* Hero — quick actions */}
      <Card className="relative overflow-hidden border-border/60 card-hover">
        <div className="absolute inset-0 grid-bg opacity-50 pointer-events-none" />
        <div className="relative p-6 sm:p-8 flex flex-col lg:flex-row gap-6 items-start lg:items-center justify-between">
          <div className="space-y-2 max-w-2xl">
            <div className="inline-flex items-center gap-2 px-2.5 py-1 rounded-full bg-accent/10 border border-accent/30 text-[11px] font-medium text-accent">
              <Sparkles className="w-3 h-3" />
              AI Destekli Hukuk Araştırması
            </div>
            <h2 className="text-2xl sm:text-3xl text-display">
              Hukuki sorunuzu sorun.
              <br />
              <span className="text-accent">Kaynak gösteren cevap</span> alın.
            </h2>
            <p className="text-sm text-muted-foreground max-w-xl">
              Yargıtay, Danıştay, Emsal, AYM, Resmî Gazete ve mevzuat kaynakları üzerinde semantic + keyword hybrid arama.
              AI hiçbir hukuki iddiayı kaynak olmadan üretmez.
            </p>
          </div>
          <div className="grid grid-cols-2 gap-2 w-full lg:w-auto">
            <Button
              onClick={() => onNavigate('search')}
              className="h-12 px-5 brass-bar text-sidebar hover:opacity-90 shadow-md font-semibold"
            >
              <Search className="w-4 h-4 mr-2" />
              Hızlı Araştırma
            </Button>
            <Button
              onClick={() => onNavigate('petitions')}
              variant="outline"
              className="h-12 px-5 border-border bg-background hover:bg-muted font-semibold"
            >
              <FileText className="w-4 h-4 mr-2" />
              Dilekçe Oluştur
            </Button>
          </div>
        </div>
      </Card>

      {/* Stats row */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          icon={FileText}
          label="Aktif Dilekçe"
          value={data.stats.totalPetitions}
          trend="+2 bu hafta"
          onClick={() => onNavigate('petitions')}
        />
        <StatCard
          icon={GitBranch}
          label="Araştırma Oturumu"
          value={data.stats.totalResearch}
          trend="+5 bu hafta"
          onClick={() => onNavigate('research')}
        />
        <StatCard
          icon={Search}
          label="Toplam Arama"
          value={data.stats.totalSearches}
          trend="+18 bu hafta"
          onClick={() => onNavigate('search')}
        />
        <StatCard
          icon={Scale}
          label="İndeksli Karar"
          value={1247832}
          trend="+2.4K bu hafta"
          onClick={() => onNavigate('search')}
          formatNumber
        />
      </div>

      {/* Main grid */}
      <div className="grid lg:grid-cols-3 gap-4">
        {/* Recent petitions */}
        <Card className="lg:col-span-2 border-border/60 overflow-hidden">
          <div className="flex items-center justify-between px-5 py-4 border-b border-border/60">
            <div className="flex items-center gap-2">
              <FileText className="w-4 h-4 text-accent" />
              <h3 className="text-sm font-semibold tracking-tight">Son Dilekçeler</h3>
            </div>
            <Button
              variant="ghost"
              size="sm"
              className="h-8 text-xs"
              onClick={() => onNavigate('petitions')}
            >
              Tümünü gör
              <ChevronRight className="w-3.5 h-3.5 ml-1" />
            </Button>
          </div>
          <div className="divide-y divide-border/60">
            {data.recentPetitions.length === 0 ? (
              <EmptyState
                icon={FileText}
                title="Henüz dilekçe yok"
                hint="İlk dilekçenizi oluşturmak için 'Dilekçe Oluştur'a tıklayın"
              />
            ) : (
              data.recentPetitions.map((p) => {
                const status = STATUS_LABELS[p.status] || STATUS_LABELS.draft
                return (
                  <div
                    key={p.id}
                    className="px-5 py-3.5 hover:bg-muted/40 transition-colors cursor-pointer group"
                    onClick={() => onNavigate('petitions')}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2 mb-1">
                          <Badge variant="secondary" className="text-[10px] font-medium">
                            {TRACK_LABELS[p.petitionType] || p.petitionType}
                          </Badge>
                          <span className={cn('text-[10px] px-1.5 py-0.5 rounded font-medium', status.color)}>
                            {status.label}
                          </span>
                        </div>
                        <div className="text-sm font-medium truncate group-hover:text-accent transition-colors">
                          {p.caseTitle}
                        </div>
                        <div className="text-[11px] text-muted-foreground mt-0.5">
                          {new Date(p.updatedAt).toLocaleString('tr-TR', {
                            day: '2-digit',
                            month: 'short',
                            hour: '2-digit',
                            minute: '2-digit',
                          })}
                        </div>
                      </div>
                      {p.qualityScore !== null && (
                        <QualityScore score={p.qualityScore} />
                      )}
                    </div>
                  </div>
                )
              })
            )}
          </div>
        </Card>

        {/* Legal sources status */}
        <Card className="border-border/60 overflow-hidden">
          <div className="flex items-center justify-between px-5 py-4 border-b border-border/60">
            <div className="flex items-center gap-2">
              <Scale className="w-4 h-4 text-accent" />
              <h3 className="text-sm font-semibold tracking-tight">Kaynak Durumu</h3>
            </div>
            <Badge variant="outline" className="text-[10px] font-mono">
              {data.legalSources.filter((s) => s.enabled).length}/{data.legalSources.length} aktif
            </Badge>
          </div>
          <div className="divide-y divide-border/60">
            {data.legalSources.map((s) => (
              <div key={s.name} className="px-5 py-3 flex items-center justify-between gap-2">
                <div className="min-w-0">
                  <div className="text-sm font-medium">{s.label}</div>
                  <div className="text-[11px] text-muted-foreground flex items-center gap-1.5">
                    {s.lastSyncedAt ? (
                      <>
                        <Clock className="w-3 h-3" />
                        {new Date(s.lastSyncedAt).toLocaleDateString('tr-TR', {
                          day: '2-digit',
                          month: 'short',
                          hour: '2-digit',
                          minute: '2-digit',
                        })}
                      </>
                    ) : (
                      <span className="text-amber-600 dark:text-amber-400">Hiç senkronize edilmedi</span>
                    )}
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <div className="text-right">
                    <div className="text-xs text-muted-foreground">Karar</div>
                    <div className="text-sm font-mono tabular-nums">
                      {s.decisionCount.toLocaleString('tr-TR')}
                    </div>
                  </div>
                  <span
                    className={cn(
                      'w-2 h-2 rounded-full shrink-0',
                      s.enabled ? 'bg-emerald-500' : 'bg-red-500'
                    )}
                    title={s.enabled ? 'Aktif' : 'Devre dışı'}
                  />
                </div>
              </div>
            ))}
          </div>
        </Card>
      </div>

      {/* Research + Recent decisions */}
      <div className="grid lg:grid-cols-3 gap-4">
        <Card className="border-border/60 overflow-hidden">
          <div className="flex items-center justify-between px-5 py-4 border-b border-border/60">
            <div className="flex items-center gap-2">
              <GitBranch className="w-4 h-4 text-accent" />
              <h3 className="text-sm font-semibold tracking-tight">Son Araştırmalar</h3>
            </div>
            <Button variant="ghost" size="sm" className="h-8 text-xs" onClick={() => onNavigate('research')}>
              Tümünü gör
              <ChevronRight className="w-3.5 h-3.5 ml-1" />
            </Button>
          </div>
          <div className="divide-y divide-border/60">
            {data.recentResearch.length === 0 ? (
              <EmptyState
                icon={GitBranch}
                title="Araştırma yok"
                hint="AI ile ilk araştırmanızı başlatın"
              />
            ) : (
              data.recentResearch.map((r) => {
                const status = STATUS_LABELS[r.status] || STATUS_LABELS.running
                return (
                  <div
                    key={r.id}
                    className="px-5 py-3.5 hover:bg-muted/40 transition-colors cursor-pointer"
                    onClick={() => onNavigate('research')}
                  >
                    <div className="text-sm font-medium line-clamp-2 mb-1">{r.query}</div>
                    <div className="flex items-center justify-between text-[11px] text-muted-foreground">
                      <div className="flex items-center gap-2">
                        {r.track && (
                          <Badge variant="outline" className="text-[10px] py-0">
                            {TRACK_LABELS[r.track] || r.track}
                          </Badge>
                        )}
                        <span>{new Date(r.startedAt).toLocaleDateString('tr-TR', { day: '2-digit', month: 'short' })}</span>
                      </div>
                      <span className={cn('px-1.5 py-0.5 rounded font-medium', status.color)}>
                        {status.label}
                      </span>
                    </div>
                  </div>
                )
              })
            )}
          </div>
        </Card>

        <Card className="lg:col-span-2 border-border/60 overflow-hidden">
          <div className="flex items-center justify-between px-5 py-4 border-b border-border/60">
            <div className="flex items-center gap-2">
              <FileSearch className="w-4 h-4 text-accent" />
              <h3 className="text-sm font-semibold tracking-tight">Son İndekslenen Kararlar</h3>
            </div>
            <Button variant="ghost" size="sm" className="h-8 text-xs" onClick={() => onNavigate('search')}>
              Araştır
              <ArrowUpRight className="w-3.5 h-3.5 ml-1" />
            </Button>
          </div>
          <div className="divide-y divide-border/60">
            {data.recentDecisions.map((d) => (
              <div
                key={d.id}
                className="px-5 py-3.5 hover:bg-muted/40 transition-colors cursor-pointer group"
                onClick={() => onNavigate('search')}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      <Badge variant="outline" className="text-[10px] font-medium">
                        {d.court}
                      </Badge>
                      {d.courtChamber && (
                        <span className="text-[11px] text-muted-foreground">{d.courtChamber}</span>
                      )}
                    </div>
                    <div className="text-sm font-medium line-clamp-1 group-hover:text-accent transition-colors">
                      {d.title}
                    </div>
                    {d.decisionNumber && (
                      <div className="text-[11px] text-muted-foreground mt-0.5 font-mono">
                        {d.decisionNumber}
                      </div>
                    )}
                  </div>
                  {d.similarityScore && (
                    <div className="text-right shrink-0">
                      <div className="text-[10px] uppercase tracking-wide text-muted-foreground">Benzerlik</div>
                      <div className="text-sm font-mono tabular-nums text-accent font-semibold">
                        %{Math.round(d.similarityScore * 100)}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </div>
  )
}

function StatCard({
  icon: Icon,
  label,
  value,
  trend,
  onClick,
  formatNumber,
}: {
  icon: typeof TrendingUp
  label: string
  value: number
  trend: string
  onClick: () => void
  formatNumber?: boolean
}) {
  return (
    <Card
      className="border-border/60 p-4 cursor-pointer card-hover group"
      onClick={onClick}
    >
      <div className="flex items-start justify-between mb-2">
        <div className="w-8 h-8 rounded-md bg-accent/10 flex items-center justify-center">
          <Icon className="w-4 h-4 text-accent" />
        </div>
        <ArrowUpRight className="w-3.5 h-3.5 text-muted-foreground group-hover:text-accent transition-colors" />
      </div>
      <div className="text-2xl font-bold text-mono-tabular tracking-tight">
        {formatNumber ? value.toLocaleString('tr-TR') : value}
      </div>
      <div className="text-[11px] text-muted-foreground mt-0.5">{label}</div>
      <div className="text-[10px] text-emerald-600 dark:text-emerald-400 mt-1.5 flex items-center gap-1">
        <TrendingUp className="w-3 h-3" />
        {trend}
      </div>
    </Card>
  )
}

function QualityScore({ score }: { score: number }) {
  const color = score >= 80 ? 'text-emerald-600' : score >= 60 ? 'text-amber-600' : 'text-red-600'
  const label = score >= 80 ? 'İyi' : score >= 60 ? 'Orta' : 'Zayıf'
  return (
    <div className="text-right shrink-0">
      <div className="text-[10px] uppercase tracking-wide text-muted-foreground">Kalite</div>
      <div className={cn('text-sm font-mono tabular-nums font-semibold', color)}>{score}</div>
      <div className={cn('text-[10px]', color)}>{label}</div>
    </div>
  )
}

function EmptyState({ icon: Icon, title, hint }: { icon: typeof FileText; title: string; hint: string }) {
  return (
    <div className="px-5 py-10 text-center">
      <div className="inline-flex w-10 h-10 rounded-md bg-muted items-center justify-center mb-3">
        <Icon className="w-4 h-4 text-muted-foreground" />
      </div>
      <div className="text-sm font-medium">{title}</div>
      <div className="text-xs text-muted-foreground mt-1">{hint}</div>
    </div>
  )
}
