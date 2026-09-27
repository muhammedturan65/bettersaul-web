'use client'

import { useState, Suspense } from 'react'
import { signIn } from 'next-auth/react'
import { useRouter, useSearchParams } from 'next/navigation'
import { Scale, Mail, Lock, ArrowRight, AlertCircle, Sparkles } from 'lucide-react'
import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import Link from 'next/link'

export default function LoginPage() {
  return (
    <Suspense fallback={<LoginLoading />}>
      <LoginForm />
    </Suspense>
  )
}

function LoginLoading() {
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

function LoginForm() {
  const router = useRouter()
  const params = useSearchParams()
  const [email, setEmail] = useState('demo@bettersaul.legal')
  const [password, setPassword] = useState('demo1234')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const callbackUrl = params.get('callbackUrl') || '/'

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setLoading(true)
    setError('')
    const res = await signIn('credentials', {
      email,
      password,
      redirect: false,
    })
    if (res?.error) {
      setError('Email veya şifre hatalı')
      setLoading(false)
    } else if (res?.ok) {
      router.push(callbackUrl)
      router.refresh()
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center p-4 bg-background">
      <div className="absolute inset-0 grid-bg opacity-30 pointer-events-none" />
      <div className="relative w-full max-w-md">
        {/* Brand */}
        <div className="text-center mb-8">
          <div className="inline-flex w-14 h-14 rounded-xl brass-bar items-center justify-center mb-4 shadow-md">
            <Scale className="w-7 h-7 text-sidebar" strokeWidth={2.2} />
          </div>
          <h1 className="text-2xl font-bold text-display">BetterSaul</h1>
          <p className="text-[10px] uppercase tracking-[0.18em] text-muted-foreground mt-1">
            Legal Intelligence Platform
          </p>
        </div>

        <Card className="border-border/60 p-6 sm:p-8">
          <div className="mb-6">
            <h2 className="text-lg font-semibold">Giriş yapın</h2>
            <p className="text-xs text-muted-foreground mt-1">
              Hesabınıza erişmek için email ve şifrenizi girin
            </p>
          </div>

          {error && (
            <div className="mb-4 px-3 py-2 rounded-md bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-900 text-xs text-red-700 dark:text-red-300 flex items-center gap-2">
              <AlertCircle className="w-3.5 h-3.5 shrink-0" />
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-muted-foreground">Email</label>
              <div className="relative">
                <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                <Input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="avukat@hukuk.legal"
                  className="h-11 pl-10"
                  required
                  autoComplete="email"
                />
              </div>
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-medium text-muted-foreground">Şifre</label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                <Input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className="h-11 pl-10"
                  required
                  autoComplete="current-password"
                />
              </div>
            </div>

            <Button
              type="submit"
              disabled={loading}
              className="w-full h-11 brass-bar text-sidebar hover:opacity-90 font-semibold"
            >
              {loading ? (
                <>
                  <div className="w-4 h-4 border-2 border-sidebar/30 border-t-sidebar rounded-full animate-spin mr-2" />
                  Giriş yapılıyor
                </>
              ) : (
                <>
                  Giriş yap
                  <ArrowRight className="w-4 h-4 ml-2" />
                </>
              )}
            </Button>
          </form>

          <div className="mt-5 pt-5 border-t border-border/60 text-center">
            <p className="text-xs text-muted-foreground">
              Hesabınız yok mu?{' '}
              <Link href="/register" className="text-accent hover:underline font-medium">
                Kayıt olun
              </Link>
            </p>
          </div>

          {/* Demo credentials hint */}
          <div className="mt-4 px-3 py-2.5 rounded-md bg-accent/5 border border-accent/20">
            <div className="flex items-center gap-1.5 text-[10px] uppercase tracking-[0.18em] text-accent font-semibold mb-1">
              <Sparkles className="w-3 h-3" />
              Demo Hesap
            </div>
            <div className="text-[11px] text-muted-foreground font-mono">
              demo@bettersaul.legal / demo1234
            </div>
          </div>
        </Card>

        <div className="mt-6 text-center text-[10px] text-muted-foreground">
          © 2026 BetterSaul · Türkiye Hukuk AI Platformu
        </div>
      </div>
    </div>
  )
}
