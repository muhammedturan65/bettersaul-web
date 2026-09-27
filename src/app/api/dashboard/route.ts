import { NextRequest, NextResponse } from 'next/server'
import { db } from '@/lib/db'

export const dynamic = 'force-dynamic'

export async function GET() {
  try {
    const [petitions, researchSessions, documents, legalDecisions, legalSources] = await Promise.all([
      db.petition.count({ where: { deletedAt: null } }),
      db.researchSession.count(),
      db.document.count(),
      db.legalDecision.count(),
      db.legalSource.findMany({
        include: {
          _count: { select: { decisions: true } },
        },
      }),
    ])

    const recentPetitions = await db.petition.findMany({
      where: { deletedAt: null },
      take: 5,
      orderBy: { updatedAt: 'desc' },
      include: {
        case: true,
        versions: { take: 1, orderBy: { versionNo: 'desc' } },
      },
    })

    const recentResearch = await db.researchSession.findMany({
      take: 5,
      orderBy: { startedAt: 'desc' },
    })

    const recentDecisions = await db.legalDecision.findMany({
      take: 5,
      orderBy: { decisionDate: 'desc' },
      where: { similarityScore: { not: null } },
    })

    // Simulate search count for demo
    const totalSearches = await db.researchSession.count()

    return NextResponse.json({
      stats: {
        totalPetitions: petitions,
        totalResearch: researchSessions,
        totalDocuments: documents,
        totalSearches: totalSearches * 8, // Each research = ~8 search steps (mock multiplier)
      },
      recentPetitions: recentPetitions.map((p) => ({
        id: p.id,
        caseTitle: p.case?.title || 'Başlıksız Dilekçe',
        petitionType: p.petitionType || 'genel',
        status: p.status,
        qualityScore: p.versions[0]?.qualityScore ?? null,
        updatedAt: p.updatedAt.toISOString(),
      })),
      recentResearch: recentResearch.map((r) => ({
        id: r.id,
        query: r.query,
        track: r.track,
        status: r.status,
        startedAt: r.startedAt.toISOString(),
        completedAt: r.completedAt?.toISOString() || null,
      })),
      legalSources: legalSources.map((s) => ({
        name: s.name,
        label: s.label,
        lastSyncedAt: s.lastSyncedAt?.toISOString() || null,
        enabled: s.enabled,
        decisionCount: s._count.decisions,
      })),
      recentDecisions: recentDecisions.map((d) => ({
        id: d.id,
        court: d.court,
        courtChamber: d.courtChamber,
        decisionNumber: d.decisionNumber,
        title: d.title,
        decisionDate: d.decisionDate?.toISOString() || null,
        similarityScore: d.similarityScore,
      })),
    })
  } catch (error) {
    console.error('Dashboard API error:', error)
    return NextResponse.json(
      {
        stats: { totalPetitions: 0, totalResearch: 0, totalDocuments: 0, totalSearches: 0 },
        recentPetitions: [],
        recentResearch: [],
        legalSources: [],
        recentDecisions: [],
      },
      { status: 200 }
    )
  }
}
