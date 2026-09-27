'use client'

import { Menu, Bell, LogOut, Shield } from 'lucide-react'
import { signOut } from 'next-auth/react'
import { cn } from '@/lib/utils'

interface TopbarProps {
  onMenuClick: () => void
  currentView: string
  user: { name?: string | null; email: string; role: string }
}

const VIEW_LABELS: Record<string, { title: string; subtitle: string }> = {
  dashboard: { title: 'Dashboard', subtitle: 'Genel bakış ve hızlı işlemler' },
  search: { title: 'Hukuk Arama', subtitle: 'Semantic + keyword hybrid arama' },
  petitions: { title: 'Dilekçeler', subtitle: 'Oluştur, düzenle, versiyonla' },
  'petition-new': { title: 'Yeni Dilekçe', subtitle: 'AI ile dilekçe üretim pipeline' },
  chat: { title: 'AI Asistan', subtitle: 'Kaynak gösteren hukuki sohbet' },
  research: { title: 'Araştırma Oturumları', subtitle: 'AI araştırma şeffaflığı' },
  documents: { title: 'Belgeler', subtitle: 'Dosya yükleme ve analiz' },
  admin: { title: 'Admin Panel', subtitle: 'Import pipeline & kullanıcı yönetimi' },
}

export function Topbar({ onMenuClick, currentView, user }: TopbarProps) {
  const info = VIEW_LABELS[currentView] || VIEW_LABELS.dashboard
  const initials = (user.name || user.email)
    .split(' ')
    .map((s) => s[0])
    .slice(0, 2)
    .join('')
    .toUpperCase()

  return (
    <header className="sticky top-0 z-30 bg-background/95 backdrop-blur-sm border-b border-border">
      <div className="flex items-center justify-between px-4 sm:px-6 py-3">
        <div className="flex items-center gap-3 min-w-0">
          <button
            onClick={onMenuClick}
            className="lg:hidden p-2 -ml-2 rounded-md hover:bg-muted text-foreground/70"
            aria-label="Menüyü aç"
          >
            <Menu className="w-5 h-5" />
          </button>
          <div className="min-w-0">
            <div className="flex items-baseline gap-2">
              <h1 className="text-lg sm:text-xl font-bold tracking-tight truncate">
                {info.title}
              </h1>
              <span className="hidden sm:inline text-[10px] uppercase tracking-[0.18em] text-accent font-semibold">
                · Legal Intelligence
              </span>
            </div>
            <p className="text-xs text-muted-foreground truncate">{info.subtitle}</p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {/* AI status pill */}
          <div className="hidden md:flex items-center gap-2 px-3 py-1.5 rounded-full bg-accent/10 border border-accent/30 text-xs">
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-accent opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-accent"></span>
            </span>
            <span className="font-medium text-foreground/80">AI hazır</span>
            <span className="text-muted-foreground">·</span>
            <span className="text-mono-tabular text-muted-foreground">Z.ai</span>
          </div>

          <button
            className="p-2 rounded-md hover:bg-muted text-foreground/70 relative"
            aria-label="Bildirimler"
          >
            <Bell className="w-[18px] h-[18px]" />
            <span className="absolute top-1.5 right-1.5 w-1.5 h-1.5 rounded-full bg-accent" />
          </button>

          <div className="flex items-center gap-2 pl-2 ml-1 border-l border-border">
            <div className="hidden sm:block text-right leading-tight">
              <div className="text-sm font-medium">{user.name || user.email}</div>
              <div className="text-[10px] text-muted-foreground flex items-center gap-1 justify-end">
                {user.role === 'admin' && <Shield className="w-2.5 h-2.5 text-accent" />}
                {user.role}
              </div>
            </div>
            <button
              onClick={() => signOut({ callbackUrl: '/login' })}
              className="w-9 h-9 rounded-full brass-bar flex items-center justify-center text-sidebar font-bold text-sm shadow-sm hover:opacity-90"
              title="Çıkış yap"
            >
              {initials}
            </button>
          </div>
        </div>
      </div>
    </header>
  )
}
