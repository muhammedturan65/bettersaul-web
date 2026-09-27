import { NextResponse } from 'next/server'
import { db } from '@/lib/db'

export const dynamic = 'force-dynamic'

export async function GET() {
  try {
    const documents = await db.document.findMany({
      take: 20,
      orderBy: { createdAt: 'desc' },
      include: {
        chunks: { select: { id: true, chunkIndex: true } },
      },
    })

    return NextResponse.json({
      documents: documents.map((d) => ({
        id: d.id,
        filename: d.filename,
        mimeType: d.mimeType,
        sizeBytes: d.sizeBytes,
        parseStatus: d.parseStatus,
        source: d.source,
        summary: d.summary,
        createdAt: d.createdAt.toISOString(),
        chunks: d.chunks,
      })),
    })
  } catch (error) {
    console.error('Documents API error:', error)
    return NextResponse.json({ documents: [] })
  }
}
