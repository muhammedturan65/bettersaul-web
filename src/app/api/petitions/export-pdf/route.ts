import { NextRequest, NextResponse } from 'next/server'
import { getServerSession } from 'next-auth'
import { authOptions } from '@/lib/auth'
import { db } from '@/lib/db'

export const dynamic = 'force-dynamic'

function generatePetitionHTML(bodyText: string, title: string): string {
  return `<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="utf-8">
<title>${title}</title>
<style>
  @page { size: A4; margin: 2.5cm; }
  body {
    font-family: 'Times New Roman', serif;
    font-size: 12pt;
    line-height: 1.6;
    color: #1a1a1a;
    text-align: justify;
  }
  h1 {
    text-align: center;
    font-size: 14pt;
    font-weight: bold;
    text-transform: uppercase;
    margin-bottom: 24pt;
  }
  .petition-text {
    white-space: pre-wrap;
    text-align: justify;
  }
  .footer {
    position: fixed;
    bottom: 1cm;
    left: 2.5cm;
    right: 2.5cm;
    text-align: center;
    font-size: 9pt;
    color: #888;
    border-top: 1px solid #ccc;
    padding-top: 5pt;
  }
</style>
</head>
<body>
<h1>${title}</h1>
<div class="petition-text">${bodyText.replace(/</g, '&lt;').replace(/>/g, '&gt;')}</div>
<div class="footer">BetterSaul Legal Intelligence Platform — AI ile üretilmiştir</div>
</body>
</html>`
}

export async function GET(req: NextRequest) {
  const session = await getServerSession(authOptions)
  if (!session?.user) return NextResponse.json({ error: 'Yetkisiz' }, { status: 401 })

  try {
    const { searchParams } = new URL(req.url)
    const petitionId = searchParams.get('petitionId')
    const versionId = searchParams.get('versionId')

    if (!petitionId) return NextResponse.json({ error: 'petitionId gerekli' }, { status: 400 })

    const version = versionId
      ? await db.petitionVersion.findUnique({ where: { id: versionId } })
      : await db.petitionVersion.findFirst({
          where: { petitionId },
          orderBy: { versionNo: 'desc' },
        })

    if (!version) return NextResponse.json({ error: 'Dilekçe bulunamadı' }, { status: 404 })

    const petition = await db.petition.findUnique({
      where: { id: petitionId },
      include: { case: true },
    })

    const title = petition?.case?.title || 'Dilekçe'
    const html = generatePetitionHTML(version.bodyText, title)

    return new NextResponse(html, {
      headers: {
        'Content-Type': 'text/html; charset=utf-8',
        'Content-Disposition': `inline; filename="${title.replace(/[^a-zA-Z0-9]/g, '_')}.html"`,
      },
    })
  } catch (e: any) {
    return NextResponse.json({ error: e.message }, { status: 500 })
  }
}

export async function POST(req: NextRequest) {
  const session = await getServerSession(authOptions)
  if (!session?.user) return NextResponse.json({ error: 'Yetkisiz' }, { status: 401 })

  try {
    const { petitionId, versionId } = await req.json()

    const version = versionId
      ? await db.petitionVersion.findUnique({ where: { id: versionId } })
      : await db.petitionVersion.findFirst({
          where: { petitionId },
          orderBy: { versionNo: 'desc' },
        })

    if (!version) {
      return NextResponse.json({ error: 'Dilekçe bulunamadı' }, { status: 404 })
    }

    const petition = await db.petition.findUnique({
      where: { id: petitionId },
      include: { case: true },
    })

    const title = petition?.case?.title || 'Dilekçe'
    const html = generatePetitionHTML(version.bodyText, title)

    return new NextResponse(html, {
      headers: {
        'Content-Type': 'text/html; charset=utf-8',
        'Content-Disposition': `inline; filename="${title.replace(/[^a-zA-Z0-9]/g, '_')}.html"`,
      },
    })
  } catch (e: any) {
    console.error('Export error:', e)
    return NextResponse.json({ error: e.message }, { status: 500 })
  }
}
