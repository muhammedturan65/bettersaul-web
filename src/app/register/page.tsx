'use client'

import { useState } from 'react'
import { signIn } from 'next-auth/react'
import { useRouter } from 'next/navigation'
import { Scale, Mail, Lock, User, Building2, ArrowRight, AlertCircle, CheckCircle2 } from 'lucide-react'
import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import Link from 'next/link'

export default function RegisterPage() {
  const router = useRouter()
  const [form, setForm] = useState({
    name: '',
    email: '',
    password: '',
    passwordConfirm: '',
    barNo: '',
    orgName: '',
  })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  function setField(k: string, v: string) {
    setForm((f) => ({ ...f, [k]: v }))
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError('')

    if (form.password !== form.passwordConfirm) {
      setError('Şifreler eşleşmiyor')
      return
    }
    if (form.password.length < 8) {
      setError('Şifre en az 8 karakter olmalı')
      return
    }

    setLoading(true)
    try {
      const res = await fetch('/api/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(form),
      })
      const data = await res.json()
      if (!res.ok) {
        setError(data.error || 'Kayıt başarısız')
        setLoading(false)
        return
      }
      // Auto-login
      const signInRes = await signIn('credentials', {
        email: form.email,
        password: form.password,
        redirect: false,
      })
      if (signInRes?.ok) {
        router.push('/')
        router.refresh()
      } else {
        router.push('/login')
      }
    } catch {
      setError('Bir hata oluştu')
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center p-4 bg-background">
      <div className="absolute inset-0 grid-bg opacity-30 pointer-events-none" />
      <div className="relative w-full max-w-md">
        <div className="text-center mb-6">
          <div className="inline-flex w-14 h-14 rounded-xl brass-bar items-center justify-center mb-4 shadow-md">
            <Scale className="w-7 h-7 text-sidebar" strokeWidth={2.2} />
          </div>
          <h1 className="text-2xl font-bold text-display">Hesap Oluştur</h1>
          <p className="text-[10px] uppercase tracking-[0.18em] text-muted-foreground mt-1">
            BetterSaul Legal Intelligence
          </p>
        </div>

        <Card className="border-border/60 p-6 sm:p-8">
          {error && (
            <div className="mb-4 px-3 py-2 rounded-md bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-900 text-xs text-red-700 dark:text-red-300 flex items-center gap-2">
              <AlertCircle className="w-3.5 h-3.5 shrink-0" />
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-3.5">
            <Field
              icon={User}
              label="Ad Soyad"
              type="text"
              value={form.name}
              onChange={(v) => setField('name', v)}
              placeholder="Av. Mehmet Demir"
              required
            />
            <Field
              icon={Mail}
              label="Email"
              type="email"
              value={form.email}
              onChange={(v) => setField('email', v)}
              placeholder="avukat@hukuk.legal"
              required
            />
            <div className="grid grid-cols-2 gap-3">
              <Field
                icon={Lock}
                label="Şifre"
                type="password"
                value={form.password}
                onChange={(v) => setField('password', v)}
                placeholder="••••••••"
                required
              />
              <Field
                icon={CheckCircle2}
                label="Şifre (tekrar)"
                type="password"
                value={form.passwordConfirm}
                onChange={(v) => setField('passwordConfirm', v)}
                placeholder="••••••••"
                required
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <Field
                icon={Building2}
                label="Baro Sicil No (opsiyonel)"
                type="text"
                value={form.barNo}
                onChange={(v) => setField('barNo', v)}
                placeholder="ANK-12345"
              />
              <Field
                icon={Building2}
                label="Büro Adı (opsiyonel)"
                type="text"
                value={form.orgName}
                onChange={(v) => setField('orgName', v)}
                placeholder="Demir & Partners"
              />
            </div>

            <Button
              type="submit"
              disabled={loading}
              className="w-full h-11 brass-bar text-sidebar hover:opacity-90 font-semibold mt-2"
            >
              {loading ? (
                <>
                  <div className="w-4 h-4 border-2 border-sidebar/30 border-t-sidebar rounded-full animate-spin mr-2" />
                  Hesap oluşturuluyor
                </>
              ) : (
                <>
                  Hesap oluştur
                  <ArrowRight className="w-4 h-4 ml-2" />
                </>
              )}
            </Button>
          </form>

          <div className="mt-5 pt-5 border-t border-border/60 text-center">
            <p className="text-xs text-muted-foreground">
              Zaten hesabınız var mı?{' '}
              <Link href="/login" className="text-accent hover:underline font-medium">
                Giriş yapın
              </Link>
            </p>
          </div>
        </Card>
      </div>
    </div>
  )
}

function Field({
  icon: Icon,
  label,
  type,
  value,
  onChange,
  placeholder,
  required,
}: {
  icon: typeof User
  label: string
  type: string
  value: string
  onChange: (v: string) => void
  placeholder: string
  required?: boolean
}) {
  return (
    <div className="space-y-1">
      <label className="text-xs font-medium text-muted-foreground">{label}</label>
      <div className="relative">
        <Icon className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
        <Input
          type={type}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          className="h-10 pl-10"
          required={required}
        />
      </div>
    </div>
  )
}
