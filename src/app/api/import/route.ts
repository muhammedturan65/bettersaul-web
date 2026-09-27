import { NextRequest, NextResponse } from 'next/server'
import { getServerSession } from 'next-auth'
import { authOptions } from '@/lib/auth'
import { createJob, startJob, listJobs, pauseJob, resumeJob, cancelJob, getJob } from '@/lib/import-queue'

export const dynamic = 'force-dynamic'

const SOURCE_SIZES: Record<string, number> = {
  yargitay: 4_500_000,
  danistay: 1_200_000,
  emsal: 2_800_000,
  aym: 65_000,
  resmi_gazete: 350_000,
  mevzuat: 28_000,
}

export async function GET() {
  const session = await getServerSession(authOptions)
  if (!session?.user) return NextResponse.json({ error: 'Yetkisiz' }, { status: 401 })
  if (session.user.role !== 'admin') {
    return NextResponse.json({ error: 'Yetersiz yetki' }, { status: 403 })
  }
  return NextResponse.json({ jobs: listJobs() })
}

export async function POST(req: NextRequest) {
  const session = await getServerSession(authOptions)
  if (!session?.user) return NextResponse.json({ error: 'Yetkisiz' }, { status: 401 })
  if (session.user.role !== 'admin') {
    return NextResponse.json({ error: 'Yetersiz yetki' }, { status: 403 })
  }

  const body = await req.json()
  const { action, sourceName, jobId, totalItems } = body

  if (action === 'create') {
    if (!sourceName) return NextResponse.json({ error: 'sourceName gerekli' }, { status: 400 })
    // For demo: use small numbers (production would use SOURCE_SIZES)
    const total = totalItems || (sourceName === 'mevzuat' ? 30 : sourceName === 'aym' ? 50 : sourceName === 'resmi_gazete' ? 80 : 100)
    const job = createJob(sourceName, total)
    startJob(job.id)
    return NextResponse.json({ ok: true, job })
  }

  if (action === 'pause' && jobId) {
    return NextResponse.json({ ok: pauseJob(jobId) })
  }
  if (action === 'resume' && jobId) {
    return NextResponse.json({ ok: resumeJob(jobId) })
  }
  if (action === 'cancel' && jobId) {
    return NextResponse.json({ ok: cancelJob(jobId) })
  }
  if (action === 'get' && jobId) {
    const job = getJob(jobId)
    return job ? NextResponse.json({ job }) : NextResponse.json({ error: 'Job bulunamadı' }, { status: 404 })
  }

  return NextResponse.json({ error: 'Geçersiz action' }, { status: 400 })
}
