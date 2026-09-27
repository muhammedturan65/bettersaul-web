'use client'

import { ScrollArea } from '@/components/ui/scroll-area'
import {
  LayoutDashboard,
  Search,
  FileText,
  MessageSquare,
  GitBranch,
  FolderOpen,
  Scale,
  X,
} from 'lucide-react'
import { cn } from '@/lib/utils'

type View = 'dashboard' | 'search' | 'petitions' | 'chat' | 'research' | 'documents'

interface NavItem {
  id: View
  label: string
  icon: typeof LayoutDashboard
  description: string
}

const NAV_ITEMS: NavItem[] = [
  { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard, description: 'Genel bakış' },
  { id: 'search', label: 'Hukuk Arama', icon: Search, description: 'Semantic + keyword' },
  { id: 'petitions', label: 'Dilekçeler', icon: FileText, description: 'Oluştur & düzenle' },
  { id: 'chat', label: 'AI Asistan', icon: MessageSquare, description: 'Kaynak gösteren sohbet' },
  { id: 'research', label: 'Araştırma', icon: GitBranch, description: 'Trace & oturumlar' },
  { id: 'documents', label: 'Belgeler', icon: FolderOpen, description: 'Yükle & analiz et' },
]

interface SidebarProps {
  currentView: View
  onNavigate: (view: string) => void
  isOpen: boolean
  onClose: () => void
}

export function Sidebar({ currentView, onNavigate, isOpen, onClose }: SidebarProps) {
  return (
    <>
      {isOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-40 lg:hidden"
          onClick={onClose}
          aria-hidden="true"
        />
      )}

      <aside
        className={cn(
          'fixed top-0 left-0 z-50 h-screen w-64 bg-sidebar text-sidebar-foreground border-r border-sidebar-border flex flex-col transition-transform duration-300',
          isOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'
        )}
      >
        <div className="px-5 py-5 border-b border-sidebar-border">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-md brass-bar flex items-center justify-center shadow-md">
                <Scale className="w-5 h-5 text-sidebar" strokeWidth={2.2} />
              </div>
              <div className="leading-tight">
                <div className="text-base font-bold tracking-tight">BetterSaul</div>
                <div className="text-[10px] uppercase tracking-[0.18em] text-sidebar-foreground/55">
                  Legal Intelligence
                </div>
              </div>
            </div>
            <button
              onClick={onClose}
              className="lg:hidden text-sidebar-foreground/70 hover:text-sidebar-foreground"
              aria-label="Menüyü kapat"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        <ScrollArea className="flex-1 px-3 py-4">
          <nav className="space-y-0.5">
            <div className="px-3 mb-2 text-[10px] font-semibold uppercase tracking-[0.18em] text-sidebar-foreground/45">
              Çalışma alanı
            </div>
            {NAV_ITEMS.map((item) => {
              const Icon = item.icon
              const active = currentView === item.id
              return (
                <button
                  key={item.id}
                  onClick={() => onNavigate(item.id)}
                  className={cn(
                    'group w-full flex items-center gap-3 px-3 py-2.5 rounded-md text-sm font-medium transition-all',
                    active
                      ? 'bg-sidebar-accent text-sidebar-accent-foreground border-l-2 border-accent'
                      : 'text-sidebar-foreground/75 hover:text-sidebar-foreground hover:bg-sidebar-accent/50 border-l-2 border-transparent'
                  )}
                >
                  <Icon
                    className={cn(
                      'w-[18px] h-[18px] shrink-0',
                      active ? 'text-accent' : 'text-sidebar-foreground/55 group-hover:text-sidebar-foreground/80'
                    )}
                    strokeWidth={2}
                  />
                  <div className="flex-1 text-left">
                    <div className="leading-tight">{item.label}</div>
                    <div className="text-[10px] text-sidebar-foreground/45 font-normal">
                      {item.description}
                    </div>
                  </div>
                </button>
              )
            })}
          </nav>

          <div className="mt-6 mx-1 p-3.5 rounded-md bg-sidebar-accent/40 border border-sidebar-border/60">
            <div className="text-[10px] uppercase tracking-[0.18em] text-sidebar-foreground/55 mb-2">
              Bu ay
            </div>
            <div className="space-y-2">
              <div className="flex items-baseline justify-between">
                <span className="text-xs text-sidebar-foreground/70">Araştırma</span>
                <span className="text-sm font-semibold text-mono-tabular text-sidebar-foreground">24</span>
              </div>
              <div className="flex items-baseline justify-between">
                <span className="text-xs text-sidebar-foreground/70">Dilekçe</span>
                <span className="text-sm font-semibold text-mono-tabular text-sidebar-foreground">8</span>
              </div>
              <div className="flex items-baseline justify-between">
                <span className="text-xs text-sidebar-foreground/70">Token</span>
                <span className="text-sm font-semibold text-mono-tabular text-sidebar-foreground">142K</span>
              </div>
            </div>
          </div>
        </ScrollArea>

        <div className="px-4 py-3 border-t border-sidebar-border text-[10px] text-sidebar-foreground/50">
          <div className="flex items-center justify-between">
            <span>v1.0 · Phase 1</span>
            <span className="text-mono-tabular">2026</span>
          </div>
        </div>
      </aside>
    </>
  )
}
