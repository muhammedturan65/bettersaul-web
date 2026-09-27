import { NextRequest, NextResponse } from 'next/server'
import { getServerSession } from 'next-auth'
import { authOptions } from '@/lib/auth'
import { db } from '@/lib/db'
import { generatePetitionPipeline } from '@/lib/legal-engine/petition-pipeline'

export const dynamic = 'force-dynamic'

export async function POST(req: NextRequest) {
  try {
    const session = await getServerSession(authOptions)
    if (!session?.user) {
      return NextResponse.json({ error: 'Yetkisiz' }, { status: 401 })
    }

    const body = await req.json()
    const { formData, caseId, petitionId } = body

    if (!formData) {
      return NextResponse.json({ error: 'formData gerekli' }, { status: 400 })
    }

    // If no petitionId, create a new petition
    let actualPetitionId = petitionId
    let actualCaseId = caseId
    if (!actualPetitionId) {
      // Create case if not exists
      if (!actualCaseId) {
        const newCase = await db.case.create({
          data: {
            title: `${formData.petitioner_name || 'Yeni'} v. ${formData.defendant_name || 'Belirsiz'} — ${formData.petition_type || 'Dava'}`,
            track: formData.petition_type || 'is',
            status: 'open',
            createdById: session.user.id,
          },
        })
        actualCaseId = newCase.id
      }

      const newPetition = await db.petition.create({
        data: {
          userId: session.user.id,
          caseId: actualCaseId,
          petitionType: formData.petition_type || 'is',
          track: formData.petition_type || 'is',
          status: 'draft',
        },
      })
      actualPetitionId = newPetition.id
    }

    // Run the 4-stage pipeline
    const result = await generatePetitionPipeline({
      formData,
      userId: session.user.id,
      petitionId: actualPetitionId,
      caseId: actualCaseId,
    })

    return NextResponse.json({
      ok: true,
      petitionId: actualPetitionId,
      caseId: actualCaseId,
      bodyText: result.bodyText,
      brief: result.brief,
      qualityReport: result.qualityReport,
      stages: result.stages,
      totalDurationMs: result.totalDurationMs,
    })
  } catch (error: any) {
    console.error('Petition generation error:', error)
    return NextResponse.json(
      { error: 'Dilekçe üretimi sırasında hata: ' + error.message },
      { status: 500 }
    )
  }
}
