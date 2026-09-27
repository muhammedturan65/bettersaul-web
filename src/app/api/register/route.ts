import { NextRequest, NextResponse } from 'next/server'
import bcrypt from 'bcryptjs'
import { db } from '@/lib/db'

export const dynamic = 'force-dynamic'

export async function POST(req: NextRequest) {
  try {
    const body = await req.json()
    const { name, email, password, barNo, orgName } = body

    if (!email || !password || !name) {
      return NextResponse.json({ error: 'Eksik alan' }, { status: 400 })
    }
    if (password.length < 8) {
      return NextResponse.json({ error: 'Şifre en az 8 karakter olmalı' }, { status: 400 })
    }

    const existing = await db.user.findUnique({ where: { email: email.toLowerCase() } })
    if (existing) {
      return NextResponse.json({ error: 'Bu email zaten kayıtlı' }, { status: 409 })
    }

    const passwordHash = await bcrypt.hash(password, 10)
    const user = await db.user.create({
      data: {
        email: email.toLowerCase(),
        name,
        passwordHash,
        role: 'lawyer',
        barNo: barNo || null,
        emailVerified: new Date(),
      },
    })

    // Create organization if name provided
    if (orgName) {
      const slug = orgName
        .toLocaleLowerCase('tr-TR')
        .replace(/ı/g, 'i').replace(/ş/g, 's').replace(/ğ/g, 'g')
        .replace(/ü/g, 'u').replace(/ö/g, 'o').replace(/ç/g, 'c')
        .replace(/[^a-z0-9]+/g, '-')
        .replace(/^-+|-+$/g, '') + '-' + user.id.slice(-4)

      const org = await db.organization.create({
        data: {
          name: orgName,
          slug,
          plan: 'free',
          seatCount: 1,
          members: {
            create: {
              userId: user.id,
              role: 'org_admin',
            },
          },
        },
      })

      await db.auditLog.create({
        data: {
          userId: user.id,
          orgId: org.id,
          action: 'register',
          entityType: 'user',
          entityId: user.id,
          metadata: JSON.stringify({ orgName, barNo }),
        },
      })
    } else {
      await db.auditLog.create({
        data: {
          userId: user.id,
          action: 'register',
          entityType: 'user',
          entityId: user.id,
        },
      })
    }

    return NextResponse.json({ ok: true, userId: user.id })
  } catch (error) {
    console.error('Register error:', error)
    return NextResponse.json({ error: 'Kayıt sırasında hata oluştu' }, { status: 500 })
  }
}
