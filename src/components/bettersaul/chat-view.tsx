'use client'

import { useState, useRef, useEffect } from 'react'
import {
  Send,
  Sparkles,
  Scale,
  FileText,
  Search as SearchIcon,
  ChevronRight,
  CheckCircle2,
  Clock,
} from 'lucide-react'
import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'

interface Message {
  id: string
  role: 'user' | 'assistant' | 'system' | 'tool'
  content: string
  citations?: Array<{ source: string; ref: string; verified: boolean }>
  toolName?: string
  toolResult?: any
  pending?: boolean
}

const SUGGESTED = [
  'İş sözleşmem sebepsiz feshedildi, ne yapmalıyım?',
  'Güvenlik soruşturması nedeniyle kamu görevine atanamadım',
  'Anlaşmalı boşanma için hangi belgeler gerekli?',
  'Tüketici kredisinde faiz oranı net belirtilmemiş',
]

export function ChatView() {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [toolSteps, setToolSteps] = useState<Array<{ name: string; status: 'running' | 'done'; detail?: string }>>([])
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
  }, [messages, toolSteps])

  async function send(text?: string) {
    const content = (text || input).trim()
    if (!content || loading) return

    const userMsg: Message = { id: Math.random().toString(36), role: 'user', content }
    setMessages((m) => [...m, userMsg])
    setInput('')
    setLoading(true)
    setToolSteps([])

    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: content }),
      })
      const data = await res.json()

      // Simulate streaming tool steps then final answer
      const steps = data.toolSteps || []
      for (const step of steps) {
        setToolSteps((s) => [...s, { name: step.name, status: 'running' }])
        await new Promise((r) => setTimeout(r, step.durationMs || 300))
        setToolSteps((s) => s.map((x, i) => (i === s.length - 1 ? { ...x, status: 'done', detail: step.detail } : x)))
      }

      const assistantMsg: Message = {
        id: Math.random().toString(36),
        role: 'assistant',
        content: data.content,
        citations: data.citations,
      }
      setMessages((m) => [...m, assistantMsg])
    } catch {
      setMessages((m) => [
        ...m,
        { id: Math.random().toString(36), role: 'assistant', content: 'Üzgünüm, bir hata oluştu. Lütfen tekrar deneyin.' },
      ])
    } finally {
      setLoading(false)
      setToolSteps([])
    }
  }

  return (
    <div className="h-[calc(100vh-65px)] flex flex-col max-w-[1200px] mx-auto">
      {/* Messages */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto scrollbar-thin p-4 sm:p-6 space-y-6">
        {messages.length === 0 && (
          <div className="max-w-2xl mx-auto pt-12">
            <div className="text-center mb-8">
              <div className="inline-flex w-14 h-14 rounded-xl brass-bar items-center justify-center mb-4 shadow-md">
                <Scale className="w-7 h-7 text-sidebar" />
              </div>
              <h2 className="text-2xl font-bold text-display mb-2">
                Hukuki sorularınız için <span className="text-accent">akıllı asistan</span>
              </h2>
              <p className="text-sm text-muted-foreground max-w-md mx-auto">
                AI her cevabını gerçek hukuk kaynaklarına dayandırır. Halüsinasyon kontrolü, içtihat doğrulama ve citation sistemi ile.
              </p>
            </div>
            <div className="grid sm:grid-cols-2 gap-2">
              {SUGGESTED.map((s) => (
                <button
                  key={s}
                  onClick={() => send(s)}
                  className="text-left p-3 rounded-lg border border-border/60 hover:border-accent hover:bg-accent/5 transition-colors group"
                >
                  <div className="flex items-center gap-2">
                    <Sparkles className="w-3.5 h-3.5 text-accent shrink-0" />
                    <span className="text-xs font-medium group-hover:text-accent transition-colors">{s}</span>
                  </div>
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((m) => (
          <MessageBubble key={m.id} message={m} />
        ))}

        {/* Tool steps */}
        {toolSteps.length > 0 && (
          <Card className="border-border/60 p-4 max-w-2xl mx-auto bg-muted/30">
            <div className="text-[10px] uppercase tracking-[0.18em] text-muted-foreground mb-3 flex items-center gap-1.5">
              <SearchIcon className="w-3 h-3" />
              Araştırma yapılıyor
            </div>
            <div className="space-y-2">
              {toolSteps.map((s, i) => (
                <div key={i} className="flex items-center gap-2 text-xs">
                  {s.status === 'done' ? (
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600 shrink-0" />
                  ) : (
                    <div className="w-3.5 h-3.5 border-2 border-accent/30 border-t-accent rounded-full animate-spin shrink-0" />
                  )}
                  <span className={s.status === 'done' ? 'text-foreground' : 'text-muted-foreground'}>
                    {s.name}
                  </span>
                  {s.detail && (
                    <span className="text-muted-foreground text-[11px] font-mono">· {s.detail}</span>
                  )}
                </div>
              ))}
            </div>
          </Card>
        )}
      </div>

      {/* Input */}
      <div className="border-t border-border/60 bg-background p-4">
        <div className="max-w-3xl mx-auto">
          <form
            onSubmit={(e) => {
              e.preventDefault()
              send()
            }}
            className="relative flex items-end gap-2"
          >
            <div className="flex-1 relative">
              <textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault()
                    send()
                  }
                }}
                placeholder="Hukuki sorunuza yazın..."
                rows={1}
                disabled={loading}
                className="w-full resize-none px-4 py-3 pr-12 text-sm border border-border rounded-lg bg-background focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent/50 max-h-32 disabled:opacity-50"
              />
            </div>
            <Button
              type="submit"
              disabled={loading || !input.trim()}
              className="h-11 w-11 p-0 brass-bar text-sidebar hover:opacity-90 shrink-0"
            >
              <Send className="w-4 h-4" />
            </Button>
          </form>
          <div className="flex items-center justify-center gap-3 mt-2 text-[10px] text-muted-foreground">
            <span className="flex items-center gap-1">
              <Sparkles className="w-2.5 h-2.5" />
              Z.ai tabanlı
            </span>
            <span>·</span>
            <span>Kaynak gösteren mod</span>
            <span>·</span>
            <span>Halüsinasyon koruması aktif</span>
          </div>
        </div>
      </div>
    </div>
  )
}

function MessageBubble({ message }: { message: Message }) {
  if (message.role === 'user') {
    return (
      <div className="flex justify-end max-w-3xl mx-auto">
        <div className="bg-accent/10 border border-accent/30 rounded-lg px-4 py-2.5 max-w-[80%]">
          <p className="text-sm leading-relaxed">{message.content}</p>
        </div>
      </div>
    )
  }

  return (
    <div className="max-w-3xl mx-auto">
      <div className="flex items-start gap-3">
        <div className="w-8 h-8 rounded-md brass-bar flex items-center justify-center shrink-0 mt-0.5">
          <Scale className="w-4 h-4 text-sidebar" />
        </div>
        <div className="flex-1 min-w-0 space-y-3">
          <div className="bg-card border border-border/60 rounded-lg px-4 py-3">
            <div className="prose prose-sm max-w-none">
              <FormattedContent text={message.content} />
            </div>
          </div>

          {message.citations && message.citations.length > 0 && (
            <div className="space-y-1.5">
              <div className="text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
                Kaynaklar
              </div>
              {message.citations.map((c, i) => (
                <div
                  key={i}
                  className="flex items-center gap-2 px-3 py-2 rounded-md border border-border/60 bg-muted/30 text-xs hover:bg-muted/60 cursor-pointer group"
                >
                  <Badge variant="outline" className="text-[10px] py-0 font-mono">
                    [{i + 1}]
                  </Badge>
                  <span className="text-xs flex-1">{c.ref}</span>
                  <Badge variant="secondary" className="text-[10px] py-0">
                    {c.source}
                  </Badge>
                  {c.verified && (
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                  )}
                  <ChevronRight className="w-3 h-3 text-muted-foreground group-hover:text-accent" />
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function FormattedContent({ text }: { text: string }) {
  // Simple markdown-ish formatter: **bold**, line breaks, [n] citation refs
  const lines = text.split('\n')
  return (
    <div className="text-sm leading-relaxed space-y-2">
      {lines.map((line, i) => {
        if (line.trim() === '') return <div key={i} className="h-2" />
        // Bold segments
        const parts = line.split(/(\*\*[^*]+\*\*)/g)
        return (
          <p key={i} className="leading-relaxed">
            {parts.map((p, j) => {
              if (p.startsWith('**') && p.endsWith('**')) {
                return <strong key={j} className="font-semibold text-foreground">{p.slice(2, -2)}</strong>
              }
              // Citation refs [1], [2] -> small badge
              const citeParts = p.split(/(\[\d+\])/g)
              return citeParts.map((cp, k) => {
                if (/^\[\d+\]$/.test(cp)) {
                  return (
                    <sup key={`${j}-${k}`} className="text-accent font-mono font-semibold text-[10px] mx-0.5">
                      {cp}
                    </sup>
                  )
                }
                return <span key={`${j}-${k}`}>{cp}</span>
              })
            })}
          </p>
        )
      })}
    </div>
  )
}
