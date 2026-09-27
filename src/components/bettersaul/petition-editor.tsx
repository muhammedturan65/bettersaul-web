'use client'

import { useState } from 'react'
import {
  ArrowLeft,
  Sparkles,
  FileText,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Loader2,
  ChevronRight,
} from 'lucide-react'
import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Progress } from '@/components/ui/progress'
import { cn } from '@/lib/utils'

interface Stage {
  name: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  durationMs?: number
  output?: any
}

const TRACKS = [
  { id: 'is', label: 'İş Davası' },
  { id: 'bosanma', label: 'Boşanma' },
  { id: 'idare', label: 'İdare Davası' },
  { id: 'tuketici', label: 'Tüketici' },
  { id: 'kira', label: 'Kira' },
  { id: 'alacak', label: 'Alacak' },
  { id: 'tazminat', label: 'Tazminat' },
  { id: 'ceza', label: 'Ceza' },
]

const STAGE_LABELS: Record<string, string> = {
  extract: 'Olgu çıkarımı',
  generate: 'AI dilekçe üretimi',
  check: 'Kalite kontrol (17 boyut)',
  repair: 'AI düzeltme',
}

interface PetitionEditorProps {
  onBack: () => void
}

export function PetitionEditor({ onBack }: PetitionEditorProps) {
  const [form, setForm] = useState({
    petition_type: 'is',
    petitioner_name: '',
    petitioner_tckn: '',
    petitioner_address: '',
    defendant_name: '',
    defendant_address: '',
    court: '',
    facts: '',
    evidence: '',
    claims: [] as string[],
  })
  const [loading, setLoading] = useState(false)
  const [stages, setStages] = useState<Stage[]>([])
  const [result, setResult] = useState<any>(null)
  const [error, setError] = useState('')
  const [provider, setProvider] = useState<'auto' | 'nvidia' | 'zai'>('auto')

  const ALL_CLAIMS = [
    { id: 'ise_iade', label: 'İşe iade' },
    { id: 'kidem', label: 'Kıdem tazminatı' },
    { id: 'ihbar', label: 'İhbar tazminatı' },
    { id: 'bos_sure', label: 'Boşta geçen süre' },
    { id: 'is_baslatmama', label: 'İşe başlatmama tazminatı' },
    { id: 'fazla_calisma', label: 'Fazla çalışma' },
    { id: 'yillik_izin', label: 'Kullanılmayan izin' },
    { id: 'bosanma', label: 'Boşanma' },
    { id: 'nafaka', label: 'Nafaka' },
    { id: 'velayet', label: 'Velayet' },
    { id: 'mal_paylasimi', label: 'Mal paylaşımı' },
    { id: 'tazminat_maddi', label: 'Maddi tazminat' },
    { id: 'tazminat_manevi', label: 'Manevi tazminat' },
    { id: 'iptal', label: 'İptal' },
    { id: 'icra', label: 'İcra' },
  ]

  function setField(k: string, v: any) {
    setForm((f) => ({ ...f, [k]: v }))
  }

  function toggleClaim(id: string) {
    setForm((f) => ({
      ...f,
      claims: f.claims.includes(id)
        ? f.claims.filter((c) => c !== id)
        : [...f.claims, id],
    }))
  }

  async function handleGenerate() {
    setLoading(true)
    setError('')
    setResult(null)
    setStages([])

    try {
      const url = provider === 'nvidia' ? '/api/petitions/generate-nvidia' : '/api/petitions/generate'
      const res = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ formData: form, provider }),
      })
      const data = await res.json()
      if (!res.ok) {
        setError(data.error || 'Üretim başarısız')
      } else {
        setResult(data)
        setStages(data.stages || [])
      }
    } catch (e: any) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="p-4 sm:p-6 lg:p-8 space-y-6 max-w-[1400px] mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="icon" onClick={onBack} className="h-9 w-9">
            <ArrowLeft className="w-4 h-4" />
          </Button>
          <div>
            <h2 className="text-xl font-bold tracking-tight">Yeni Dilekçe</h2>
            <p className="text-sm text-muted-foreground">
              AI destekli 4-aşamalı pipeline: çıkarım → üretim → kontrol → düzeltme
            </p>
          </div>
        </div>
      </div>

      <div className="grid lg:grid-cols-2 gap-6">
        {/* Form */}
        <Card className="border-border/60 p-5 sm:p-6 space-y-5">
          <div className="flex items-center gap-2 pb-3 border-b border-border/60">
            <FileText className="w-4 h-4 text-accent" />
            <h3 className="text-sm font-semibold">Dava Bilgileri</h3>
          </div>

          <div className="space-y-2">
            <Label className="text-xs">Dava Türü</Label>
            <Select value={form.petition_type} onValueChange={(v) => setField('petition_type', v)}>
              <SelectTrigger className="h-10">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {TRACKS.map((t) => (
                  <SelectItem key={t.id} value={t.id}>{t.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="grid sm:grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label className="text-xs">Davacı Ad Soyad</Label>
              <Input
                value={form.petitioner_name}
                onChange={(e) => setField('petitioner_name', e.target.value)}
                placeholder="Mustafa Y."
                className="h-10"
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs">T.C. No</Label>
              <Input
                value={form.petitioner_tckn}
                onChange={(e) => setField('petitioner_tckn', e.target.value)}
                placeholder="12345678901"
                className="h-10 font-mono"
              />
            </div>
          </div>

          <div className="space-y-1.5">
            <Label className="text-xs">Davacı Adresi</Label>
            <Input
              value={form.petitioner_address}
              onChange={(e) => setField('petitioner_address', e.target.value)}
              placeholder="Çankaya / Ankara"
              className="h-10"
            />
          </div>

          <div className="grid sm:grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label className="text-xs">Davalı Ad</Label>
              <Input
                value={form.defendant_name}
                onChange={(e) => setField('defendant_name', e.target.value)}
                placeholder="ABC Teknoloji A.Ş."
                className="h-10"
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs">Davalı Adresi</Label>
              <Input
                value={form.defendant_address}
                onChange={(e) => setField('defendant_address', e.target.value)}
                placeholder="Odtü Teknokent / Ankara"
                className="h-10"
              />
            </div>
          </div>

          <div className="space-y-1.5">
            <Label className="text-xs">Mahkeme (opsiyonel)</Label>
            <Input
              value={form.court}
              onChange={(e) => setField('court', e.target.value)}
              placeholder="Ankara 3. İş Mahkemesi"
              className="h-10"
            />
          </div>

          <div className="space-y-1.5">
            <Label className="text-xs">Olay Anlatımı</Label>
            <Textarea
              value={form.facts}
              onChange={(e) => setField('facts', e.target.value)}
              placeholder="Davacı, davalı işyerinde 15.01.2022 tarihinden itibaren yazılım mühendisi olarak çalışmaktadır. Davalı işveren, 10.03.2026 tarihinde herhangi bir geçerli sebep göstermeksizin iş sözleşmesini feshetmiştir..."
              className="min-h-[120px] text-sm"
            />
          </div>

          <div className="space-y-1.5">
            <Label className="text-xs">Deliller (her satır bir delil)</Label>
            <Textarea
              value={form.evidence}
              onChange={(e) => setField('evidence', e.target.value)}
              placeholder={'İş sözleşmesi\nBanka dekontları\nSGK hizmet dökümü\nTanık beyanları'}
              className="min-h-[80px] text-sm"
            />
          </div>

          <div className="space-y-2">
            <Label className="text-xs">Talep Kalemleri</Label>
            <div className="flex flex-wrap gap-1.5">
              {ALL_CLAIMS.map((c) => (
                <button
                  key={c.id}
                  type="button"
                  onClick={() => toggleClaim(c.id)}
                  className={cn(
                    'px-2.5 py-1 text-[11px] font-medium rounded-md border transition-colors',
                    form.claims.includes(c.id)
                      ? 'bg-accent text-sidebar border-accent'
                      : 'bg-background text-muted-foreground border-border hover:border-accent'
                  )}
                >
                  {c.label}
                </button>
              ))}
            </div>
          </div>

          {/* Provider selection */}
          <div className="flex items-center gap-2 text-xs">
            <span className="text-muted-foreground">AI Sağlayıcı:</span>
            {(['auto', 'nvidia', 'zai'] as const).map((p) => (
              <button
                key={p}
                type="button"
                onClick={() => setProvider(p)}
                className={cn(
                  'px-2.5 py-1 text-[11px] font-medium rounded-md transition-colors',
                  provider === p
                    ? 'bg-accent text-sidebar'
                    : 'bg-muted text-muted-foreground hover:bg-muted/70'
                )}
              >
                {p === 'auto' ? 'Auto' : p === 'nvidia' ? 'NVIDIA Nemotron 120B' : 'Z.ai'}
              </button>
            ))}
          </div>

          <Button
            onClick={handleGenerate}
            disabled={loading || !form.petitioner_name || !form.facts}
            className="w-full h-11 brass-bar text-sidebar hover:opacity-90 font-semibold"
          >
            {loading ? (
              <>
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                Dilekçe üretiliyor ({provider})
              </>
            ) : (
              <>
                <Sparkles className="w-4 h-4 mr-2" />
                AI ile Dilekçe Üret
              </>
            )}
          </Button>
          {error && (
            <div className="px-3 py-2 rounded-md bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-900 text-xs text-red-700 dark:text-red-300">
              {error}
            </div>
          )}
        </Card>

        {/* Right: Pipeline + Result */}
        <div className="space-y-4">
          {/* Pipeline stages */}
          {(loading || stages.length > 0) && (
            <Card className="border-border/60 p-5">
              <div className="flex items-center gap-2 pb-3 mb-3 border-b border-border/60">
                <Sparkles className="w-4 h-4 text-accent" />
                <h3 className="text-sm font-semibold">AI Üretim Pipeline</h3>
              </div>
              <div className="space-y-3">
                {stages.map((s, i) => {
                  const label = STAGE_LABELS[s.name] || s.name
                  return (
                    <div key={i} className="flex items-start gap-3">
                      <div className="mt-0.5">
                        {s.status === 'completed' ? (
                          <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                        ) : s.status === 'running' ? (
                          <Loader2 className="w-4 h-4 text-accent animate-spin" />
                        ) : s.status === 'failed' ? (
                          <XCircle className="w-4 h-4 text-red-600" />
                        ) : (
                          <div className="w-4 h-4 rounded-full border-2 border-muted-foreground/30" />
                        )}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center justify-between gap-2">
                          <span className="text-sm font-medium">{label}</span>
                          {s.durationMs && (
                            <span className="text-[10px] font-mono text-muted-foreground">{s.durationMs}ms</span>
                          )}
                        </div>
                        {s.output && (
                          <div className="text-[11px] text-muted-foreground mt-0.5 font-mono">
                            {s.output.score !== undefined && `Skor: ${s.output.score}/100`}
                            {s.output.length !== undefined && `Uzunluk: ${s.output.length} karakter`}
                            {s.output.repaired !== undefined && (s.output.repaired ? '· Düzeltildi' : '· Düzeltme gerekmedi')}
                            {s.output.findings !== undefined && ` · ${s.output.findings} bulgu`}
                            {s.output.critical !== undefined && ` · ${s.output.critical} kritik`}
                          </div>
                        )}
                      </div>
                    </div>
                  )
                })}
              </div>
            </Card>
          )}

          {/* Result */}
          {result && (
            <>
              <Card className="border-border/60 overflow-hidden">
                <div className="px-5 py-4 border-b border-border/60 bg-muted/30 flex items-center justify-between">
                  <div>
                    <h3 className="text-sm font-semibold">Üretilen Dilekçe</h3>
                    <div className="text-[11px] text-muted-foreground mt-0.5">
                      Toplam süre: {result.totalDurationMs}ms · {result.brief?.trackLabel}
                    </div>
                  </div>
                  {result.qualityReport?.overall !== undefined && (
                    <div className="text-right">
                      <div className="text-[10px] uppercase text-muted-foreground">Kalite</div>
                      <div className={cn(
                        'text-2xl font-bold font-mono',
                        result.qualityReport.overall >= 80 ? 'text-emerald-600' :
                        result.qualityReport.overall >= 60 ? 'text-amber-600' : 'text-red-600'
                      )}>
                        {result.qualityReport.overall}
                      </div>
                    </div>
                  )}
                </div>
                <pre className="text-xs leading-relaxed whitespace-pre-wrap font-mono max-h-[400px] overflow-y-auto scrollbar-thin p-4 bg-muted/20">
                  {result.bodyText}
                </pre>
                <div className="px-4 py-3 border-t border-border/60 flex items-center justify-between">
                  <span className="text-[10px] text-muted-foreground">
                    Sağlayıcı: {result.provider || 'zai'} · Model: {result.model || 'GLM'}
                  </span>
                  {result.petitionId && (
                    <a
                      href={`/api/petitions/export-pdf?petitionId=${result.petitionId}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-md brass-bar text-sidebar hover:opacity-90"
                    >
                      <FileText className="w-3.5 h-3.5" />
                      PDF/HTML İndir
                    </a>
                  )}
                </div>
              </Card>

              {/* Quality findings */}
              {result.qualityReport?.findings?.length > 0 && (
                <Card className="border-border/60 p-5">
                  <div className="flex items-center gap-2 pb-3 mb-3 border-b border-border/60">
                    <AlertTriangle className="w-4 h-4 text-amber-600" />
                    <h3 className="text-sm font-semibold">Kalite Bulguları ({result.qualityReport.findings.length})</h3>
                  </div>
                  <div className="space-y-2 max-h-60 overflow-y-auto scrollbar-thin">
                    {result.qualityReport.findings.map((f: any, i: number) => (
                      <div key={i} className="flex items-start gap-2 text-xs">
                        {f.severity === 'critical' ? (
                          <XCircle className="w-3.5 h-3.5 mt-0.5 text-red-600 shrink-0" />
                        ) : f.severity === 'warning' ? (
                          <AlertTriangle className="w-3.5 h-3.5 mt-0.5 text-amber-600 shrink-0" />
                        ) : (
                          <CheckCircle2 className="w-3.5 h-3.5 mt-0.5 text-emerald-600 shrink-0" />
                        )}
                        <div className="min-w-0">
                          <div className="font-medium text-foreground">{f.code}</div>
                          <div className="text-muted-foreground text-[11px]">{f.message}</div>
                          {f.hint && <div className="text-muted-foreground/70 text-[10px] italic mt-0.5">{f.hint}</div>}
                        </div>
                      </div>
                    ))}
                  </div>
                </Card>
              )}
            </>
          )}

          {!loading && !result && (
            <Card className="border-border/60 p-12 text-center h-full flex flex-col items-center justify-center min-h-[400px]">
              <div className="inline-flex w-12 h-12 rounded-lg bg-accent/10 items-center justify-center mb-3">
                <Sparkles className="w-5 h-5 text-accent" />
              </div>
              <div className="text-sm font-medium">AI üretim pipeline</div>
              <div className="text-xs text-muted-foreground mt-1 max-w-xs">
                Sol taraftaki formu doldurun, AI 4 aşamalı pipeline ile dilekçenizi üretsin:
                çıkarım → üretim → kontrol → düzeltme
              </div>
            </Card>
          )}
        </div>
      </div>
    </div>
  )
}
