'use client'

import { useEffect, useState } from 'react'
import {
  FileText,
  Plus,
  ChevronRight,
  Shield,
  Clock,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  FileEdit,
  Eye,
} from 'lucide-react'
import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import { cn } from '@/lib/utils'

interface Petition {
  id: string
  caseTitle: string
  caseNo: string | null
  court: string | null
  petitionType: string
  track: string | null
  status: string
  qualityScore: number | null
  versionNo: number
  bodyText: string
  updatedAt: string
  formData: string | null
  qualityReport: string | null
}

const TRACK_LABELS: Record<string, string> = {
  is: 'İş Hukuku',
  bosanma: 'Aile Hukuku',
  idare: 'İdare Hukuku',
  tuketici: 'Tüketici Hukuku',
  kira: 'Eşya Hukuku',
  vergi: 'Vergi Hukuku',
  alacak: 'Alacak Hukuku',
  tazminat: 'Tazminat Hukuku',
  icra: 'İcra Hukuku',
  ceza: 'Ceza Hukuku',
}

const PETITION_TYPES = [
  { id: 'is', label: 'İş Davası', desc: 'İşe iade, kıdem, ihbar' },
  { id: 'bosanma', label: 'Boşanma', desc: 'Anlaşmalı / çekişmeli' },
  { id: 'idare', label: 'İdare Davası', desc: 'İptal, tam yargı' },
  { id: 'tuketici', label: 'Tüketici', desc: 'Ayıplı mal, kredi' },
  { id: 'kira', label: 'Kira', desc: 'Tahliye, kira tespiti' },
  { id: 'alacak', label: 'Alacak', desc: 'İcra, alacak davası' },
  { id: 'tazminat', label: 'Tazminat', desc: 'Maddi / manevi' },
  { id: 'ceza', label: 'Ceza', desc: 'Şikayet, savunma' },
]

const STATUS_CONFIG: Record<string, { label: string; icon: typeof Clock; color: string }> = {
  draft: { label: 'Taslak', icon: FileEdit, color: 'text-muted-foreground' },
  reviewed: { label: 'İncelendi', icon: Eye, color: 'text-blue-600' },
  final: { label: 'Tamamlandı', icon: CheckCircle2, color: 'text-emerald-600' },
  exported: { label: 'Dışa aktarıldı', icon: FileText, color: 'text-amber-600' },
}

export function PetitionsView() {
  const [petitions, setPetitions] = useState<Petition[]>([])
  const [loading, setLoading] = useState(true)
  const [selected, setSelected] = useState<Petition | null>(null)
  const [showNew, setShowNew] = useState(false)

  useEffect(() => {
    fetch('/api/petitions')
      .then((r) => r.json())
      .then((d) => {
        setPetitions(d.petitions || [])
        setLoading(false)
      })
      .catch(() => setLoading(false))
  }, [])

  if (loading) {
    return (
      <div className="p-6 sm:p-8 space-y-4">
        {[...Array(4)].map((_, i) => (
          <div key={i} className="h-24 rounded-lg shimmer" />
        ))}
      </div>
    )
  }

  return (
    <div className="p-4 sm:p-6 lg:p-8 space-y-6 max-w-[1600px] mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold tracking-tight">Dilekçeler</h2>
          <p className="text-sm text-muted-foreground">Toplam {petitions.length} dilekçe</p>
        </div>
        <Button onClick={() => setShowNew(!showNew)} className="brass-bar text-sidebar hover:opacity-90 font-semibold">
          <Plus className="w-4 h-4 mr-1.5" />
          Yeni Dilekçe
        </Button>
      </div>

      {/* New petition type picker */}
      {showNew && (
        <Card className="border-border/60 p-5">
          <div className="flex items-center justify-between mb-4">
            <div>
              <div className="text-sm font-semibold">Dava türü seçin</div>
              <div className="text-xs text-muted-foreground">AI, türüne göre usul kurallarını otomatik uygular</div>
            </div>
            <button
              onClick={() => setShowNew(false)}
              className="text-xs text-muted-foreground hover:text-foreground"
            >
              İptal
            </button>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
            {PETITION_TYPES.map((t) => (
              <button
                key={t.id}
                onClick={() => {
                  // In a full app this would navigate to a form
                  alert(`'${t.label}' dilekçe oluşturma sihirbazı Phase 2'de gelecek.\n\nBu sürümde mevcut dilekçelerinizi inceleyebilirsiniz.`)
                  setShowNew(false)
                }}
                className="text-left p-3 rounded-md border border-border/60 hover:border-accent hover:bg-accent/5 transition-colors group"
              >
                <div className="text-sm font-medium group-hover:text-accent transition-colors">{t.label}</div>
                <div className="text-[11px] text-muted-foreground mt-0.5">{t.desc}</div>
              </button>
            ))}
          </div>
        </Card>
      )}

      {/* Two-pane layout */}
      <div className="grid lg:grid-cols-3 gap-4">
        {/* List */}
        <div className="space-y-3">
          {petitions.length === 0 ? (
            <Card className="border-border/60 p-12 text-center">
              <div className="inline-flex w-12 h-12 rounded-lg bg-accent/10 items-center justify-center mb-3">
                <FileText className="w-5 h-5 text-accent" />
              </div>
              <div className="text-sm font-medium">Henüz dilekçe yok</div>
              <div className="text-xs text-muted-foreground mt-1">
                "Yeni Dilekçe" ile başlayın
              </div>
            </Card>
          ) : (
            petitions.map((p) => {
              const status = STATUS_CONFIG[p.status] || STATUS_CONFIG.draft
              const StatusIcon = status.icon
              return (
                <Card
                  key={p.id}
                  className={cn(
                    'border-border/60 p-4 cursor-pointer card-hover',
                    selected?.id === p.id && 'border-accent ring-1 ring-accent/30'
                  )}
                  onClick={() => setSelected(p)}
                >
                  <div className="flex items-start justify-between gap-2 mb-2">
                    <Badge variant="secondary" className="text-[10px]">
                      {TRACK_LABELS[p.petitionType] || p.petitionType}
                    </Badge>
                    <div className={cn('flex items-center gap-1 text-[10px] font-medium', status.color)}>
                      <StatusIcon className="w-3 h-3" />
                      {status.label}
                    </div>
                  </div>
                  <h4 className="text-sm font-semibold leading-snug mb-1 line-clamp-2">
                    {p.caseTitle}
                  </h4>
                  <div className="text-[11px] text-muted-foreground">
                    {p.court || 'Mahkeme belirtilmedi'}
                  </div>
                  <div className="flex items-center justify-between mt-3 pt-3 border-t border-border/60">
                    <span className="text-[10px] text-muted-foreground">
                      v{p.versionNo} · {new Date(p.updatedAt).toLocaleDateString('tr-TR', { day: '2-digit', month: 'short' })}
                    </span>
                    {p.qualityScore !== null && (
                      <span className={cn(
                        'text-xs font-mono font-semibold',
                        p.qualityScore >= 80 ? 'text-emerald-600' :
                        p.qualityScore >= 60 ? 'text-amber-600' : 'text-red-600'
                      )}>
                        {p.qualityScore}/100
                      </span>
                    )}
                  </div>
                </Card>
              )
            })
          )}
        </div>

        {/* Detail */}
        <div className="lg:col-span-2">
          {!selected ? (
            <Card className="border-border/60 p-12 text-center h-full flex flex-col items-center justify-center min-h-[400px]">
              <div className="inline-flex w-12 h-12 rounded-lg bg-muted items-center justify-center mb-3">
                <FileText className="w-5 h-5 text-muted-foreground" />
              </div>
              <div className="text-sm font-medium">Dilekçe seçin</div>
              <div className="text-xs text-muted-foreground mt-1">
                Detayları görmek için soldan bir dilekçe seçin
              </div>
            </Card>
          ) : (
            <PetitionDetail petition={selected} />
          )}
        </div>
      </div>
    </div>
  )
}

function PetitionDetail({ petition }: { petition: Petition }) {
  // Compute parsed values directly (no effect needed)
  let qualityReport: any = null
  let formData: any = null
  try {
    qualityReport = petition.qualityReport ? JSON.parse(petition.qualityReport) : null
    formData = petition.formData ? JSON.parse(petition.formData) : null
  } catch {}

  return (
    <Card className="border-border/60 overflow-hidden">
      {/* Header */}
      <div className="px-5 py-4 border-b border-border/60 bg-muted/30">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <Badge variant="secondary" className="text-[10px]">
                {TRACK_LABELS[petition.petitionType] || petition.petitionType}
              </Badge>
              <span className="text-[10px] text-muted-foreground">v{petition.versionNo}</span>
            </div>
            <h3 className="text-base font-semibold leading-snug">{petition.caseTitle}</h3>
            <div className="text-xs text-muted-foreground mt-1">
              {petition.court} · {petition.caseNo}
            </div>
          </div>
          {petition.qualityScore !== null && (
            <div className="text-right shrink-0">
              <div className="text-[10px] uppercase text-muted-foreground">Kalite puanı</div>
              <div className={cn(
                'text-2xl font-bold font-mono tabular-nums',
                petition.qualityScore >= 80 ? 'text-emerald-600' :
                petition.qualityScore >= 60 ? 'text-amber-600' : 'text-red-600'
              )}>
                {petition.qualityScore}
              </div>
              <div className="text-[10px] text-muted-foreground">/ 100</div>
            </div>
          )}
        </div>
      </div>

      {/* Body */}
      <div className="grid md:grid-cols-3 divide-x divide-border/60">
        {/* Petition text */}
        <div className="md:col-span-2 p-5">
          <div className="text-[10px] uppercase tracking-[0.18em] text-muted-foreground mb-2">
            Dilekçe metni
          </div>
          <pre className="text-xs leading-relaxed whitespace-pre-wrap font-mono max-h-[500px] overflow-y-auto scrollbar-thin bg-muted/20 p-4 rounded-md">
            {petition.bodyText}
          </pre>
        </div>

        {/* Quality report sidebar */}
        <div className="p-5">
          <div className="text-[10px] uppercase tracking-[0.18em] text-muted-foreground mb-3">
            Kalite analizi
          </div>
          {qualityReport ? (
            <div className="space-y-4">
              {/* Overall */}
              <div>
                <div className="flex items-baseline justify-between mb-1">
                  <span className="text-xs font-medium">Genel</span>
                  <span className={cn(
                    'text-sm font-mono font-bold',
                    (qualityReport.overall || 0) >= 80 ? 'text-emerald-600' :
                    (qualityReport.overall || 0) >= 60 ? 'text-amber-600' : 'text-red-600'
                  )}>
                    {qualityReport.overall || 0}
                  </span>
                </div>
                <Progress value={qualityReport.overall || 0} className="h-1.5" />
              </div>

              {/* Subscores */}
              {qualityReport.subscores && (
                <div className="space-y-2">
                  {Object.entries(qualityReport.subscores).map(([k, v]) => (
                    <div key={k}>
                      <div className="flex items-baseline justify-between mb-0.5">
                        <span className="text-[11px] text-muted-foreground capitalize">{k.replace(/_/g, ' ')}</span>
                        <span className="text-[11px] font-mono">{v as number}</span>
                      </div>
                      <Progress value={v as number} className="h-1" />
                    </div>
                  ))}
                </div>
              )}

              {/* Findings */}
              {qualityReport.findings && qualityReport.findings.length > 0 && (
                <div>
                  <div className="text-[10px] uppercase tracking-[0.18em] text-muted-foreground mb-2">
                    Bulgular
                  </div>
                  <div className="space-y-2">
                    {qualityReport.findings.map((f: any, i: number) => {
                      const Icon = f.severity === 'critical' ? XCircle :
                                   f.severity === 'warning' ? AlertTriangle : CheckCircle2
                      const color = f.severity === 'critical' ? 'text-red-600' :
                                    f.severity === 'warning' ? 'text-amber-600' : 'text-emerald-600'
                      return (
                        <div key={i} className="flex items-start gap-2">
                          <Icon className={cn('w-3.5 h-3.5 mt-0.5 shrink-0', color)} />
                          <div className="min-w-0">
                            <div className="text-[11px] font-medium text-foreground">{f.code}</div>
                            <div className="text-[10px] text-muted-foreground leading-snug">{f.message}</div>
                          </div>
                        </div>
                      )
                    })}
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="text-xs text-muted-foreground">Henüz analiz yapılmadı</div>
          )}

          {/* Form data */}
          {formData && (
            <div className="mt-5 pt-4 border-t border-border/60">
              <div className="text-[10px] uppercase tracking-[0.18em] text-muted-foreground mb-2">
                Form verisi
              </div>
              <div className="space-y-1.5">
                {Object.entries(formData).slice(0, 6).map(([k, v]) => (
                  <div key={k} className="text-[11px]">
                    <span className="text-muted-foreground">{k}: </span>
                    <span className="font-mono">{String(v).slice(0, 40)}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </Card>
  )
}
