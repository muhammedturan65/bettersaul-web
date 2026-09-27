'use client'

import { useState } from 'react'
import { Dashboard } from '@/components/bettersaul/dashboard'
import { SearchView } from '@/components/bettersaul/search-view'
import { PetitionsView } from '@/components/bettersaul/petitions-view'
import { ChatView } from '@/components/bettersaul/chat-view'
import { ResearchView } from '@/components/bettersaul/research-view'
import { DocumentsView } from '@/components/bettersaul/documents-view'
import { Sidebar } from '@/components/bettersaul/sidebar'
import { Topbar } from '@/components/bettersaul/topbar'

type View = 'dashboard' | 'search' | 'petitions' | 'chat' | 'research' | 'documents'

export default function Home() {
  const [view, setView] = useState<View>('dashboard')
  const [sidebarOpen, setSidebarOpen] = useState(false)

  return (
    <div className="min-h-screen flex bg-background text-foreground">
      {/* Sidebar */}
      <Sidebar
        currentView={view}
        onNavigate={(v) => {
          setView(v as View)
          setSidebarOpen(false)
        }}
        isOpen={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
      />

      {/* Main area */}
      <div className="flex-1 flex flex-col min-w-0 lg:ml-64">
        <Topbar onMenuClick={() => setSidebarOpen(true)} currentView={view} />

        <main className="flex-1 overflow-y-auto scrollbar-thin">
          {view === 'dashboard' && <Dashboard onNavigate={setView} />}
          {view === 'search' && <SearchView />}
          {view === 'petitions' && <PetitionsView />}
          {view === 'chat' && <ChatView />}
          {view === 'research' && <ResearchView />}
          {view === 'documents' && <DocumentsView />}
        </main>
      </div>
    </div>
  )
}
