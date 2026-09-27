import { NextRequest, NextResponse } from 'next/server'
import { db } from '@/lib/db'

export const dynamic = 'force-dynamic'

export async function GET() {
  try {
    const sessions = await db.researchSession.findMany({
      take: 20,
      orderBy: { startedAt: 'desc' },
      include: {
        traces: {
          orderBy: { stepOrder: 'asc' },
        },
      },
    })

    return NextResponse.json({
      sessions: sessions.map((s) => ({
        id: s.id,
        query: s.query,
        track: s.track,
        status: s.status,
        startedAt: s.startedAt.toISOString(),
        completedAt: s.completedAt?.toISOString() || null,
        traces: s.traces.map((t) => ({
          id: t.id,
          stepOrder: t.stepOrder,
          stepType: t.stepType,
          stepName: t.stepName,
          input: t.input,
          output: t.output,
          durationMs: t.durationMs,
          startedAt: t.startedAt?.toISOString() || null,
          completedAt: t.completedAt?.toISOString() || null,
        })),
      })),
    })
  } catch (error) {
    console.error('Research API error:', error)
    return NextResponse.json({ sessions: [] })
  }
}
