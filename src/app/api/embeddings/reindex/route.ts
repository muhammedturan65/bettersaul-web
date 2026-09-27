import { NextResponse } from 'next/server'
import { getServerSession } from 'next-auth'
import { authOptions } from '@/lib/auth'
import { reindexEmbeddings } from '@/lib/import-queue'

export const dynamic = 'force-dynamic'

export async function POST() {
  const session = await getServerSession(authOptions)
  if (!session?.user) return NextResponse.json({ error: 'Yetkisiz' }, { status: 401 })
  if (session.user.role !== 'admin') {
    return NextResponse.json({ error: 'Yetersiz yetki' }, { status: 403 })
  }
  try {
    const result = await reindexEmbeddings()
    return NextResponse.json({ ok: true, ...result })
  } catch (e: any) {
    return NextResponse.json({ error: e.message }, { status: 500 })
  }
}
