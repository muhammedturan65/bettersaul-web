'use client'

import { useEffect, useState } from 'react'
import {
  FolderOpen,
  Upload,
  FileText,
  MoreVertical,
  Trash2,
  Search as SearchIcon,
  CheckCircle2,
  Clock,
  AlertCircle,
} from 'lucide-react'
import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { cn } from '@/lib/utils'

interface Document {
  id: string
  filename: string
  mimeType: string | null
  sizeBytes: number | null
  parseStatus: string
  source: string
  summary: string | null
  createdAt: string
  chunks: Array<{ id: string; chunkIndex: number }>
}

const STATUS_CONFIG: Record<string, { label: string; icon: typeof Clock; color: string }> = {
  pending: { label: 'Bekliyor', icon: Clock, color: 'text-amber-600' },
  parsed: { label: 'Hazır', icon: CheckCircle2, color: 'text-emerald-600' },
  failed: { label: 'Başarısız', icon: AlertCircle, color: 'text-red-600' },
}

export function DocumentsView() {
  const [documents, setDocuments] = useState<Document[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')

  useEffect(() => {
    fetch('/api/documents')
      .then((r) => r.json())
      .then((d) => {
        setDocuments(d.documents || [])
        setLoading(false)
      })
      .catch(() => setLoading(false))
  }, [])

  const filtered = documents.filter((d) =>
    d.filename.toLowerCase().includes(search.toLowerCase())
  )

  return (
    <div className="p-4 sm:p-6 lg:p-8 space-y-6 max-w-[1600px] mx-auto">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold tracking-tight">Belgeler</h2>
          <p className="text-sm text-muted-foreground">
            Yüklediğiniz belgeler üzerinde semantic search yapın
          </p>
        </div>
        <Button className="brass-bar text-sidebar hover:opacity-90 font-semibold">
          <Upload className="w-4 h-4 mr-1.5" />
          Belge Yükle
        </Button>
      </div>

      {/* Upload zone (mock) */}
      <Card
        className="border-2 border-dashed border-border/60 p-8 text-center cursor-pointer hover:border-accent hover:bg-accent/5 transition-colors"
        onClick={() => alert('Belge yükleme özelliği Phase 2\'de gelecek. Bu sürüm demo veritabanını gösterir.')}
      >
        <div className="inline-flex w-12 h-12 rounded-lg bg-accent/10 items-center justify-center mb-3">
          <Upload className="w-5 h-5 text-accent" />
        </div>
        <div className="text-sm font-medium">PDF, DOCX veya TXT sürükleyin</div>
        <div className="text-xs text-muted-foreground mt-1">
          Maksimum 50MB · Otomatik OCR + chunking + embedding
        </div>
      </Card>

      {/* Search */}
      <div className="relative">
        <SearchIcon className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
        <Input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Belgelerde ara..."
          className="h-10 pl-10"
        />
      </div>

      {/* List */}
      {loading ? (
        <div className="space-y-3">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="h-20 rounded-lg shimmer" />
          ))}
        </div>
      ) : filtered.length === 0 ? (
        <Card className="border-border/60 p-12 text-center">
          <div className="inline-flex w-12 h-12 rounded-lg bg-muted items-center justify-center mb-3">
            <FolderOpen className="w-5 h-5 text-muted-foreground" />
          </div>
          <div className="text-sm font-medium">
            {documents.length === 0 ? 'Henüz belge yok' : 'Sonuç bulunamadı'}
          </div>
          <div className="text-xs text-muted-foreground mt-1">
            {documents.length === 0 ? 'İlk belgenizi yükleyin' : 'Farklı bir arama deneyin'}
          </div>
        </Card>
      ) : (
        <div className="space-y-2">
          {filtered.map((doc) => {
            const status = STATUS_CONFIG[doc.parseStatus] || STATUS_CONFIG.pending
            const StatusIcon = status.icon
            return (
              <Card key={doc.id} className="border-border/60 p-4 card-hover group cursor-pointer">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-md bg-accent/10 flex items-center justify-center shrink-0">
                    <FileText className="w-5 h-5 text-accent" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2 mb-0.5">
                      <span className="text-sm font-medium truncate">{doc.filename}</span>
                      <span className={cn('text-[10px] flex items-center gap-1', status.color)}>
                        <StatusIcon className="w-3 h-3" />
                        {status.label}
                      </span>
                    </div>
                    <div className="flex items-center gap-3 text-[11px] text-muted-foreground">
                      <span>{doc.mimeType || 'bilinmeyen'}</span>
                      <span>·</span>
                      <span>{doc.sizeBytes ? `${(doc.sizeBytes / 1024).toFixed(1)} KB` : '?'}</span>
                      <span>·</span>
                      <span>{doc.chunks?.length || 0} parça</span>
                      <span>·</span>
                      <span>{new Date(doc.createdAt).toLocaleDateString('tr-TR')}</span>
                    </div>
                    {doc.summary && (
                      <p className="text-xs text-muted-foreground mt-1 line-clamp-1">{doc.summary}</p>
                    )}
                  </div>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8 opacity-0 group-hover:opacity-100"
                    onClick={(e) => {
                      e.stopPropagation()
                      alert('Silme özelliği yakında')
                    }}
                  >
                    <MoreVertical className="w-4 h-4" />
                  </Button>
                </div>
              </Card>
            )
          })}
        </div>
      )}
    </div>
  )
}
