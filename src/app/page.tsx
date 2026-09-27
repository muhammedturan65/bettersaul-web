'use client'

import { useEffect, useState } from 'react'
import { useSession } from 'next-auth/react'
import { Dashboard } from '@/components/bettersaul/dashboard'
import { SearchView } from '@/components/bettersaul/search-view'
import { PetitionsView } from '@/components/bettersaul/petitions-view'
import { PetitionEditor } from '@/components/bettersaul/petition-editor'
import { ChatView } from '@/components/bettersaul/chat-view'
import { ResearchView } from '@/components/bettersaul/research-view'
import { DocumentsView } from '@/components/bettersaul/documents-view'
import { ImportAdmin } from '@/components/bettersaul/import-admin'
import { Sidebar } from '@/components/bettersaul/sidebar'
import { Topbar } from '@/components/bettersaul/topbar'
import { Scale } from 'lucide-react'

type View = 'dashboard' | 'search' | 'petitions' | 'petition-new' | 'chat' | 'research' | 'documents' | 'admin'

export default function Home() {
  const { data: session, status } = useSession()
  const [view, setView] = useState<View>('dashboard')
  const [sidebarOpen, setSidebarOpen] = useState(false)

  // Redirect to login if unauthenticated
  useEffect(() => {
    if (status === 'unauthenticated') {
      window.location.href = '/login'
    }
  }, [status])

  if (status === 'loading' || !session) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <div className="text-center">
          <div className="inline-flex w-12 h-12 rounded-xl brass-bar items-center justify-center mb-3 shadow-md animate-pulse">
            <Scale className="w-6 h-6 text-sidebar" />
          </div>
          <div className="text-sm text-muted-foreground">Yükleniyor...</div>
        </div>
      </div>
    )
  }

  const isAdmin = session.user.role === 'admin'

  return (
    <div className="min-h-screen flex bg-background text-foreground">
      <Sidebar
        currentView={view}
        onNavigate={(v) => {
          setView(v as View)
          setSidebarOpen(false)
        }}
        isOpen={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
        isAdmin={isAdmin}
      />

      <div className="flex-1 flex flex-col min-w-0 lg:ml-64">
        <Topbar
          onMenuClick={() => setSidebarOpen(true)}
          currentView={view}
          user={session.user}
        />

        <main className="flex-1 overflow-y-auto scrollbar-thin">
          {view === 'dashboard' && <Dashboard onNavigate={setView} />}
          {view === 'search' && <SearchView />}
          {view === 'petitions' && <PetitionsView onNew={() => setView('petition-new')} />}
          {view === 'petition-new' && <PetitionEditor onBack={() => setView('petitions')} />}
          {view === 'chat' && <ChatView />}
          {view === 'research' && <ResearchView />}
          {view === 'documents' && <DocumentsView />}
          {view === 'admin' && isAdmin && <ImportAdmin />}
        </main>
      </div>
    </div>
  )
}
