import { NextRequest, NextResponse } from 'next/server'
import { getServerSession } from 'next-auth'
import { authOptions } from '@/lib/auth'
import { db } from '@/lib/db'
import { embedAsync } from '@/lib/legal-engine/embeddings'

export const dynamic = 'force-dynamic'

export async function POST(req: NextRequest) {
  const session = await getServerSession(authOptions)
  if (!session?.user) return NextResponse.json({ error: 'Yetkisiz' }, { status: 401 })

  try {
    const formData = await req.formData()
    const file = formData.get('file') as File
    if (!file) return NextResponse.json({ error: 'Dosya yok' }, { status: 400 })

    if (file.size > 10 * 1024 * 1024) {
      return NextResponse.json({ error: 'Dosya çok büyük (max 10MB)' }, { status: 400 })
    }

    const bytes = await file.arrayBuffer()
    const buffer = Buffer.from(bytes)

    let parsedText = ''
    const mimeType = file.type
    if (mimeType === 'text/plain' || mimeType === 'application/json') {
      parsedText = buffer.toString('utf-8')
    } else {
      parsedText = `[${file.name} dosyası yüklendi — ${file.size} bytes]\n\nDosya adı: ${file.name}\nMIME: ${mimeType}\nBoyut: ${file.size} bytes`
    }

    const doc = await db.document.create({
      data: {
        userId: session.user.id,
        filename: file.name,
        mimeType: mimeType || 'unknown',
        sizeBytes: file.size,
        parsedText,
        parseStatus: 'parsed',
        source: 'user_upload',
        summary: parsedText.slice(0, 200),
      },
    })

    try {
      const { embedding, model } = await embedAsync(parsedText.slice(0, 8000))
      await db.documentChunk.create({
        data: {
          documentId: doc.id,
          chunkIndex: 0,
          chunkText: parsedText.slice(0, 2000),
          metadata: JSON.stringify({ model, dim: embedding.length }),
        },
      })
    } catch (e) {
      console.error('Embedding failed:', e)
    }

    return NextResponse.json({
      ok: true,
      document: {
        id: doc.id,
        filename: doc.filename,
        size: doc.sizeBytes,
        status: doc.parseStatus,
        summary: doc.summary,
      },
    })
  } catch (e: any) {
    console.error('Upload error:', e)
    return NextResponse.json({ error: e.message }, { status: 500 })
  }
}
