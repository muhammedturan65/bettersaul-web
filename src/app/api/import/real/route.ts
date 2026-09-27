import { NextRequest, NextResponse } from 'next/server'
import { getServerSession } from 'next-auth'
import { authOptions } from '@/lib/auth'

export const dynamic = 'force-dynamic'

const PYTHON_SERVICE_URL = process.env.PYTHON_SERVICE_URL || 'http://localhost:8001'

export async function GET() {
  const session = await getServerSession(authOptions)
  if (!session?.user) return NextResponse.json({ error: 'Yetkisiz' }, { status: 401 })
  if (session.user.role !== 'admin') {
    return NextResponse.json({ error: 'Yetersiz yetki' }, { status: 403 })
  }

  try {
    const res = await fetch(`${PYTHON_SERVICE_URL}/import`, {
      signal: AbortSignal.timeout(5000),
    })
    if (!res.ok) {
      return NextResponse.json({
        available: false,
        error: `Python service returned ${res.status}`,
        jobs: [],
      })
    }
    const data = await res.json()
    return NextResponse.json({ available: true, ...data })
  } catch (e: any) {
    return NextResponse.json({
      available: false,
      error: e.message || 'Python service unavailable',
      jobs: [],
    })
  }
}

export async function POST(req: NextRequest) {
  const session = await getServerSession(authOptions)
  if (!session?.user) return NextResponse.json({ error: 'Yetkisiz' }, { status: 401 })
  if (session.user.role !== 'admin') {
    return NextResponse.json({ error: 'Yetersiz yetki' }, { status: 403 })
  }

  const body = await req.json()
  const { action, source, jobId, maxDocuments, concurrency, embeddingBackend, query } = body

  try {
    let url = `${PYTHON_SERVICE_URL}/import`
    let method = 'POST'
    let reqBody: any = null

    if (action === 'start') {
      reqBody = {
        source,
        query: query || '*',
        max_documents: maxDocuments || 100,
        concurrency: concurrency || 5,
        embedding_backend: embeddingBackend || 'auto',
      }
    } else if (action === 'pause' && jobId) {
      url = `${PYTHON_SERVICE_URL}/import/${jobId}/pause`
    } else if (action === 'resume' && jobId) {
      url = `${PYTHON_SERVICE_URL}/import/${jobId}/resume`
    } else if (action === 'cancel' && jobId) {
      url = `${PYTHON_SERVICE_URL}/import/${jobId}/cancel`
    } else {
      return NextResponse.json({ error: 'Geçersiz action' }, { status: 400 })
    }

    const res = await fetch(url, {
      method,
      headers: { 'Content-Type': 'application/json' },
      body: reqBody ? JSON.stringify(reqBody) : undefined,
      signal: AbortSignal.timeout(10000),
    })

    if (!res.ok) {
      const errText = await res.text()
      return NextResponse.json(
        { error: `Python service error: ${res.status} ${errText.slice(0, 200)}` },
        { status: res.status }
      )
    }

    const data = await res.json()
    return NextResponse.json(data)
  } catch (e: any) {
    return NextResponse.json(
      { error: `Python service unavailable: ${e.message}` },
      { status: 503 }
    )
  }
}
