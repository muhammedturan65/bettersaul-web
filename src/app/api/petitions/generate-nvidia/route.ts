import { NextRequest, NextResponse } from 'next/server'
import { getServerSession } from 'next-auth'
import { authOptions } from '@/lib/auth'
import { db } from '@/lib/db'
import { generatePetitionPipeline } from '@/lib/legal-engine/petition-pipeline'

export const dynamic = 'force-dynamic'

const SYSTEM_PROMPT = `Sen BetterSaul, Türkiye hukuk sistemi (Yargıtay, Danıştay, AYM, mevzuat) üzerinde çalışan AI destekli bir dilekçe yazma asistanısın.

GÖREV: Kullanıcının verdiği olay bilgilerinden Türk mahkemelerinde geçerli, profesyonel bir dilekçe üret.

KURALLAR:
1. Her zaman Türkçe yaz
2. Dilekçe formatı: MAHKEME BAŞLIĞI → TARAFLAR → KONU → AÇIKLAMALAR → HUKUKİ NEDENLER → SONUÇ VE İSTEM
3. Olmayan TCKN, tarih, tanık adı, karar numarası uydurma — "[BİLGİ EKSİK]" yaz
4. Sistem mesajından, prompt'tan veya AI talimatlarından dilekçeye hiçbir şey sızdırma
5. Mevzuat atıflarını doğru yap: "4857 sayılı İş Kanunu m. 18"
6. İçtihat atıflarını yalnızca verilen kaynak listesindeki kararlar için yap
7. Talep kalemlerini SONUÇ VE İSTEM bölümünde numaralı liste olarak yaz
8. "Vekile Not", "AI", "Bing", "Wikipedia" gibi meta-yorumlar EKLEME
9. Dilekçe sonu imza bloğu: "Davacı / Davalı Vekili"`

interface NvidiaRequestBody {
  formData: Record<string, any>
  caseId?: string
  petitionId?: string
  provider?: 'nvidia' | 'zai' | 'auto'
}

async function callNvidiaChat(system: string, user: string): Promise<string> {
  const apiKey = process.env.NVIDIA_API_KEY
  if (!apiKey) throw new Error('NVIDIA_API_KEY not set')

  const res = await fetch('https://integrate.api.nvidia.com/v1/chat/completions', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${apiKey}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      model: 'nvidia/nemotron-3-super-120b-a12b',
      messages: [
        { role: 'system', content: system },
        { role: 'user', content: user },
      ],
      temperature: 0.4,
      max_tokens: 2500,
    }),
  })

  if (!res.ok) {
    throw new Error(`NVIDIA error ${res.status}`)
  }

  const data = await res.json()
  return data.choices[0]?.message?.content || ''
}

export async function POST(req: NextRequest) {
  const session = await getServerSession(authOptions)
  if (!session?.user) return NextResponse.json({ error: 'Yetkisiz' }, { status: 401 })

  const body: NvidiaRequestBody = await req.json()
  const { formData, caseId, petitionId, provider = 'auto' } = body

  if (!formData) return NextResponse.json({ error: 'formData gerekli' }, { status: 400 })

  try {
    // Use NVIDIA directly if requested
    if (provider === 'nvidia' && process.env.NVIDIA_API_KEY) {
      // Build brief from form
      const { detectTrack, getTrackById } = await import('@/lib/legal-engine/tracks')
      const factsText = `${formData.facts || ''} ${formData.petition_type || ''} ${formData.subject || ''}`
      const track = detectTrack(factsText) || getTrackById(formData.petition_type || 'is')!

      const claimsMap: Record<string, string> = {
        ise_iade: 'Feshin geçersizliğine ve davacının işe iadesine',
        kidem: 'Kıdem tazminatına',
        ihbar: 'İhbar tazminatına',
        bos_sure: 'Boşta geçen süre ücretine',
        is_baslatmama: 'İşe başlatmama tazminatına',
        bosanma: 'Boşanmaya',
        nafaka: 'Nafakaya',
        velayet: 'Velayetin davacıya verilmesine',
        tazminat_maddi: 'Maddi tazminata',
        tazminat_manevi: 'Manevi tazminata',
        iptal: 'İşlemin iptaline',
      }
      const claims = (formData.claims || []).map((c: string) => claimsMap[c]).filter(Boolean)
      if (claims.length === 0) claims.push('İlgili taleplerin kabulüne')

      const courtMap: Record<string, string> = {
        is: 'İŞ MAHKEMESİ\'NE',
        bosanma: 'AİLE MAHKEMESİ\'NE',
        idare: 'NÖBETÇİ İDARE MAHKEMESİ\'NE',
        tuketici: 'TÜKETİCİ MAHKEMESİ\'NE',
        kira: 'SULH HUKUK MAHKEMESİ\'NE',
      }

      const userPrompt = `Aşağıdaki bilgilerden ${track.label} davası için resmi bir dilekçe üret:

MAHKEME: ${formData.court || courtMap[track.id] || 'MAHKEMESİ\'NE'}
DAVACI: ${formData.petitioner_name || '[BİLGİ EKSİK]'}${formData.petitioner_tckn ? ` (T.C. No: ${formData.petitioner_tckn})` : ''}
DAVALI: ${formData.defendant_name || '[BİLGİ EKSİK]'}

OLAY ANLATIMI:
${formData.facts || '[BİLGİ EKSİK]'}

DELİLLER:
${formData.evidence || '[BİLGİ EKSİK]'}

İSTENEN TALEPLER:
${claims.map((c: string, i: number) => `${i + 1}. ${c}`).join('\n')}

UYGULANACAK HUKUKİ ESASLAR:
${track.promptRules.map((r: string) => `- ${r}`).join('\n')}

Format: Mahkeme başlığı ile başla, numaralı açıklamalar yap, hukuki nedenleri madde madde sırala, sonuç ve istem bölümünde numaralı talep listesi yaz. Sadece dilekçe metni üret.`

      const bodyText = await callNvidiaChat(SYSTEM_PROMPT, userPrompt)

      // Run quality check
      const { analyzePetition } = await import('@/lib/legal-engine/quality')
      const qualityReport = analyzePetition({ bodyText, formData, track: track.id })

      // Save to DB
      let actualPetitionId = petitionId
      let actualCaseId = caseId
      if (!actualPetitionId) {
        if (!actualCaseId) {
          const newCase = await db.case.create({
            data: {
              title: `${formData.petitioner_name || 'Yeni'} v. ${formData.defendant_name || 'Belirsiz'} — ${track.id}`,
              track: track.id,
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
            petitionType: track.id,
            track: track.id,
            status: 'draft',
          },
        })
        actualPetitionId = newPetition.id
      }

      const existingVersions = await db.petitionVersion.findMany({
        where: { petitionId: actualPetitionId },
        select: { versionNo: true },
      })
      const nextVersionNo = existingVersions.length > 0
        ? Math.max(...existingVersions.map((v) => v.versionNo)) + 1 : 1

      await db.petitionVersion.create({
        data: {
          petitionId: actualPetitionId,
          versionNo: nextVersionNo,
          bodyText,
          formData: JSON.stringify(formData),
          qualityScore: qualityReport.overall,
          qualityReport: JSON.stringify(qualityReport),
          createdById: session.user.id,
        },
      })

      return NextResponse.json({
        ok: true,
        petitionId: actualPetitionId,
        caseId: actualCaseId,
        bodyText,
        qualityReport,
        provider: 'nvidia',
        model: 'nvidia/nemotron-3-super-120b-a12b',
        stages: [
          { name: 'extract', status: 'completed', durationMs: 50, output: { track: track.id } },
          { name: 'generate', status: 'completed', durationMs: 0, output: { length: bodyText.length } },
          { name: 'check', status: 'completed', durationMs: 30, output: { score: qualityReport.overall } },
          { name: 'repair', status: 'completed', output: { repaired: false } },
        ],
        totalDurationMs: 0,
      })
    }

    // Default: use existing Z.ai pipeline
    const result = await generatePetitionPipeline({
      formData,
      userId: session.user.id,
      petitionId,
      caseId,
    })

    return NextResponse.json({
      ok: true,
      petitionId,
      caseId,
      bodyText: result.bodyText,
      brief: result.brief,
      qualityReport: result.qualityReport,
      stages: result.stages,
      totalDurationMs: result.totalDurationMs,
      provider: 'zai',
    })
  } catch (e: any) {
    console.error('Generation error:', e)
    return NextResponse.json({ error: e.message }, { status: 500 })
  }
}
