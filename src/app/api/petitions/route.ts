import { NextRequest, NextResponse } from 'next/server'
import { db } from '@/lib/db'

export const dynamic = 'force-dynamic'

export async function GET() {
  try {
    const petitions = await db.petition.findMany({
      where: { deletedAt: null },
      take: 20,
      orderBy: { updatedAt: 'desc' },
      include: {
        case: true,
        versions: {
          take: 1,
          orderBy: { versionNo: 'desc' },
        },
      },
    })

    return NextResponse.json({
      petitions: petitions.map((p) => ({
        id: p.id,
        caseTitle: p.case?.title || 'Başlıksız Dilekçe',
        caseNo: p.case?.caseNo || null,
        court: p.case?.court || null,
        petitionType: p.petitionType || 'genel',
        track: p.track,
        status: p.status,
        qualityScore: p.versions[0]?.qualityScore ?? null,
        versionNo: p.versions[0]?.versionNo ?? 1,
        bodyText: p.versions[0]?.bodyText || '',
        formData: p.versions[0]?.formData ?? null,
        qualityReport: p.versions[0]?.qualityReport ?? null,
        updatedAt: p.updatedAt.toISOString(),
      })),
    })
  } catch (error) {
    console.error('Petitions API error:', error)
    return NextResponse.json({ petitions: [] })
  }
}
