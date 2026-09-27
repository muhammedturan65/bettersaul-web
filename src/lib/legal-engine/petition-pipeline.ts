/**
 * BetterSaul Petition Generation Pipeline
 * 
 * 4-stage pipeline (port of engine.py write_petition logic):
 * 1. EXTRACT  — form data → structured case brief (via Z.ai or rule-based)
 * 2. GENERATE — case brief → petition text (via Z.ai)
 * 3. CHECK    — run quality checks (regex-based, 17 dimensions)
 * 4. REPAIR   — if score < 80, ask Z.ai to fix issues
 */

import ZAI from 'z-ai-web-dev-sdk'
import { db } from '@/lib/db'
import { analyzePetition } from './quality'
import { detectTrack, getTrackById } from './tracks'

export interface CaseBrief {
  track: string
  trackLabel: string
  court: string
  parties: {
    petitioner: { name: string; tckn?: string; address?: string }
    defendant: { name: string; address?: string }
  }
  facts: string[]
  claims: string[]
  evidence: string[]
  legalBasis: string[]
  promptRules: string[]
  procedure: string[]
}

export interface PipelineStage {
  name: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  durationMs?: number
  input?: any
  output?: any
  error?: string
}

export interface PipelineResult {
  bodyText: string
  brief: CaseBrief | null
  qualityReport: any
  stages: PipelineStage[]
  totalDurationMs: number
}

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

export async function generatePetitionPipeline(params: {
  formData: Record<string, any>
  userId: string
  orgId?: string
  caseId?: string
  petitionId?: string
  onProgress?: (stage: PipelineStage) => void
}): Promise<PipelineResult> {
  const startTime = Date.now()
  const stages: PipelineStage[] = []
  const { formData, userId, onProgress } = params

  // ════════════════════════════════════════════════════════════
  // STAGE 1: EXTRACT — form → case brief
  // ════════════════════════════════════════════════════════════
  const stage1: PipelineStage = { name: 'extract', status: 'running' }
  stages.push(stage1)
  onProgress?.(stage1)
  const t1Start = Date.now()

  let brief: CaseBrief
  try {
    // Determine track
    const factsText = `${formData.facts || ''} ${formData.petition_type || ''} ${formData.subject || ''}`
    const track = detectTrack(factsText) || getTrackById(formData.petition_type || 'is')!
    
    // Build claims from form
    const claims: string[] = []
    if (formData.claims && Array.isArray(formData.claims)) {
      const claimMap: Record<string, string> = {
        ise_iade: 'Feshin geçersizliğine ve davacının işe iadesine',
        kidem: 'Kıdem tazminatına',
        ihbar: 'İhbar tazminatına',
        bos_sure: 'Boşta geçen süre ücretine (en fazla 4 ay)',
        is_baslatmama: 'İşe başlatmama tazminatına (4 aylık ücret)',
        fazla_calisma: 'Fazla çalışma ücretine',
        yillik_izin: 'Kullanılmayan yıllık izin ücretine',
        bosanma: 'Boşanmaya',
        nafaka: 'Nafakaya',
        velayet: 'Velayetin davacıya verilmesine',
        mal_paylasimi: 'Mal paylaşımına',
        tazminat_maddi: 'Maddi tazminata',
        tazminat_manevi: 'Manevi tazminata',
        iptal: 'İşlemin iptaline',
        icra: 'İlamsız icra takibine',
      }
      for (const c of formData.claims) {
        if (claimMap[c]) claims.push(claimMap[c])
      }
    }
    if (claims.length === 0) {
      claims.push('İlgili taleplerin kabulüne') // fallback
    }

    // Build court name
    const courtMap: Record<string, string> = {
      is: '... İŞ MAHKEMESİ\'NE',
      bosanma: '... AİLE MAHKEMESİ\'NE',
      idare: '... NÖBETÇİ İDARE MAHKEMESİ\'NE',
      tuketici: '... TÜKETİCİ MAHKEMESİ\'NE',
      kira: '... SULH HUKUK MAHKEMESİ\'NE',
      alacak: '... ASLİYE HUKUK MAHKEMESİ\'NE',
      tazminat: '... ASLİYE HUKUK MAHKEMESİ\'NE',
      ceza: '... CEZA MAHKEMESİ\'NE',
      vergi: '... VERGİ MAHKEMESİ\'NE',
      miras: '... SULH HUKUK MAHKEMESİ\'NE',
    }

    brief = {
      track: track.id,
      trackLabel: track.label,
      court: formData.court || courtMap[track.id] || '... MAHKEMESİ\'NE',
      parties: {
        petitioner: {
          name: formData.petitioner_name || '[BİLGİ EKSİK - Davacı adı]',
          tckn: formData.petitioner_tckn,
          address: formData.petitioner_address || '[BİLGİ EKSİK - Davacı adresi]',
        },
        defendant: {
          name: formData.defendant_name || '[BİLGİ EKSİK - Davalı adı]',
          address: formData.defendant_address || '[BİLGİ EKSİK - Davalı adresi]',
        },
      },
      facts: formData.facts ? formData.facts.split('\n').filter(Boolean) : ['[BİLGİ EKSİK - Olay anlatımı]'],
      claims,
      evidence: formData.evidence ? formData.evidence.split('\n').filter(Boolean) : ['[BİLGİ EKSİK - Delil listesi]'],
      legalBasis: [], // populated by track prompt rules + AI
      promptRules: track.promptRules,
      procedure: track.procedure || [],
    }

    stage1.status = 'completed'
    stage1.durationMs = Date.now() - t1Start
    stage1.output = { track: brief.track, claims: brief.claims.length, court: brief.court }
    onProgress?.(stage1)
  } catch (e: any) {
    stage1.status = 'failed'
    stage1.error = e.message
    stage1.durationMs = Date.now() - t1Start
    onProgress?.(stage1)
    throw new Error(`EXTRACT stage failed: ${e.message}`)
  }

  // ════════════════════════════════════════════════════════════
  // STAGE 2: GENERATE — case brief → petition text (via Z.ai)
  // ════════════════════════════════════════════════════════════
  const stage2: PipelineStage = { name: 'generate', status: 'running' }
  stages.push(stage2)
  onProgress?.(stage2)
  const t2Start = Date.now()

  let bodyText: string
  try {
    const userPrompt = `Aşağıdaki bilgilerden ${brief.trackLabel} davası için resmi bir dilekçe üret:

MAHKEME: ${brief.court}
DAVACI: ${brief.parties.petitioner.name}${brief.parties.petitioner.tckn ? ` (T.C. No: ${brief.parties.petitioner.tckn})` : ''}${brief.parties.petitioner.address ? ` — ${brief.parties.petitioner.address}` : ''}
DAVALI: ${brief.parties.defendant.name}${brief.parties.defendant.address ? ` — ${brief.parties.defendant.address}` : ''}

OLAY ANLATIMI:
${brief.facts.map((f, i) => `${i + 1}. ${f}`).join('\n')}

DELİLLER:
${brief.evidence.map((e, i) => `${i + 1}. ${e}`).join('\n')}

İSTENEN TALEPLER:
${brief.claims.map((c, i) => `${i + 1}. ${c}`).join('\n')}

UYGULANACAK HUKUKİ ESASLAR (bunlara atıf yap):
${brief.promptRules.map((r) => `- ${r}`).join('\n')}${brief.procedure.length > 0 ? `\n\nUSUL ÖN ŞARTLARI: ${brief.procedure.join(', ')}` : ''}

Format: ${brief.court} başlığı ile başla, numaralı açıklamalar yap, hukuki nedenleri madde madde sırala, sonuç ve istem bölümünde numaralı talep listesi yaz. Sadece dilekçe metni üret, başka açıklama yapma.`

    try {
      const zai = await ZAI.create()
      const completion = await zai.chat.completions.create({
        messages: [
          { role: 'system', content: SYSTEM_PROMPT },
          { role: 'user', content: userPrompt },
        ],
        temperature: 0.4,
        max_tokens: 2500,
      })
      bodyText = completion.choices[0]?.message?.content || ''
    } catch (zaiErr) {
      console.error('Z.ai error, falling back to template:', zaiErr)
      // Fallback: template-based generation
      bodyText = generateTemplatePetition(brief)
    }

    stage2.status = 'completed'
    stage2.durationMs = Date.now() - t2Start
    stage2.output = { length: bodyText.length, sections: (bodyText.match(/^\w+[\s:]/gm) || []).length }
    onProgress?.(stage2)
  } catch (e: any) {
    stage2.status = 'failed'
    stage2.error = e.message
    stage2.durationMs = Date.now() - t2Start
    onProgress?.(stage2)
    // Fallback to template
    bodyText = generateTemplatePetition(brief)
  }

  // ════════════════════════════════════════════════════════════
  // STAGE 3: CHECK — run quality checks
  // ════════════════════════════════════════════════════════════
  const stage3: PipelineStage = { name: 'check', status: 'running' }
  stages.push(stage3)
  onProgress?.(stage3)
  const t3Start = Date.now()

  let qualityReport = analyzePetition({
    bodyText,
    formData,
    track: brief.track,
  })

  stage3.status = 'completed'
  stage3.durationMs = Date.now() - t3Start
  stage3.output = {
    score: qualityReport.overall,
    findings: qualityReport.findings.length,
    critical: qualityReport.criticalCount,
  }
  onProgress?.(stage3)

  // ════════════════════════════════════════════════════════════
  // STAGE 4: REPAIR — if score < 80, ask AI to fix
  // ════════════════════════════════════════════════════════════
  const stage4: PipelineStage = { name: 'repair', status: 'running' }
  stages.push(stage4)
  onProgress?.(stage4)
  const t4Start = Date.now()

  if (qualityReport.overall < 80 && qualityReport.criticalCount > 0) {
    try {
      const repairPrompt = `Aşağıdaki dilekçe metni kalite kontrolünden ${qualityReport.overall}/100 almıştır. Bulgular:

${qualityReport.findings.map((f) => `- [${f.severity.toUpperCase()}] ${f.code}: ${f.message}${f.hint ? ` (${f.hint})` : ''}`).join('\n')}

Dilekçe metni:
${bodyText}

Lütfen dilekçeyi yukarıdaki bulguları düzelterek yeniden yaz. Sadece düzeltilmiş dilekçe metnini üret.`

      const zai = await ZAI.create()
      const completion = await zai.chat.completions.create({
        messages: [
          { role: 'system', content: SYSTEM_PROMPT },
          { role: 'user', content: repairPrompt },
        ],
        temperature: 0.3,
        max_tokens: 2500,
      })
      const repairedText = completion.choices[0]?.message?.content || bodyText
      // Re-check
      const repairedReport = analyzePetition({
        bodyText: repairedText,
        formData,
        track: brief.track,
      })
      // Keep repaired if better
      if (repairedReport.overall >= qualityReport.overall) {
        bodyText = repairedText
        qualityReport = repairedReport
      }
      stage4.status = 'completed'
      stage4.output = { repaired: true, newScore: qualityReport.overall }
    } catch (e: any) {
      stage4.status = 'failed'
      stage4.error = e.message
      stage4.output = { repaired: false, keptOriginal: true }
    }
  } else {
    stage4.status = 'completed'
    stage4.output = { repaired: false, reason: 'Score already >= 80 or no critical issues' }
  }
  stage4.durationMs = Date.now() - t4Start
  onProgress?.(stage4)

  // ════════════════════════════════════════════════════════════
  // Save to database
  // ════════════════════════════════════════════════════════════
  if (params.petitionId) {
    // Get current max version
    const existingVersions = await db.petitionVersion.findMany({
      where: { petitionId: params.petitionId },
      select: { versionNo: true },
    })
    const nextVersionNo = existingVersions.length > 0
      ? Math.max(...existingVersions.map((v) => v.versionNo)) + 1
      : 1

    const newVersion = await db.petitionVersion.create({
      data: {
        petitionId: params.petitionId,
        versionNo: nextVersionNo,
        bodyText,
        formData: JSON.stringify(formData),
        qualityScore: qualityReport.overall,
        qualityReport: JSON.stringify(qualityReport),
        createdById: userId,
      },
    })

    await db.petition.update({
      where: { id: params.petitionId },
      data: {
        currentVersionId: newVersion.id,
        status: qualityReport.overall >= 80 ? 'reviewed' : 'draft',
      },
    })

    // Create research trace
    await db.researchSession.create({
      data: {
        userId,
        orgId: params.orgId,
        petitionId: params.petitionId,
        caseId: params.caseId,
        query: `Dilekçe üretim pipeline (track: ${brief.track})`,
        track: brief.track,
        status: 'completed',
        completedAt: new Date(),
        traces: {
          create: stages.map((s, i) => ({
            stepOrder: i + 1,
            stepType: s.name,
            stepName: s.name === 'extract' ? 'Olgu çıkarımı' :
                      s.name === 'generate' ? 'AI dilekçe üretimi' :
                      s.name === 'check' ? 'Kalite kontrol' :
                      s.name === 'repair' ? 'AI düzeltme' : s.name,
            input: s.input ? JSON.stringify(s.input) : null,
            output: s.output ? JSON.stringify(s.output) : null,
            durationMs: s.durationMs || 0,
            startedAt: new Date(Date.now() - (stages.length - i) * 1000),
            completedAt: new Date(),
          })),
        },
      },
    })
  }

  return {
    bodyText,
    brief,
    qualityReport,
    stages,
    totalDurationMs: Date.now() - startTime,
  }
}

function generateTemplatePetition(brief: CaseBrief): string {
  return `${brief.court}

DAVACI: ${brief.parties.petitioner.name}${brief.parties.petitioner.tckn ? `\nT.C. No: ${brief.parties.petitioner.tckn}` : ''}${brief.parties.petitioner.address ? `\nAdres: ${brief.parties.petitioner.address}` : ''}

DAVALI: ${brief.parties.defendant.name}${brief.parties.defendant.address ? `\nAdres: ${brief.parties.defendant.address}` : ''}

KONU: ${brief.trackLabel} kapsamında ${brief.claims[0]} talepli dilekçemizdir.

AÇIKLAMALAR:
${brief.facts.map((f, i) => `${i + 1}. ${f}`).join('\n')}

DELİLLER:
${brief.evidence.map((e, i) => `${i + 1}. ${e}`).join('\n')}

HUKUKİ NEDENLER:
${brief.promptRules.map((r) => `- ${r}`).join('\n')}

SONUÇ VE İSTEM:
${brief.claims.map((c, i) => `${i + 1}. ${c}`).join('\n')}
${brief.claims.length + 1}. Yargılama giderleri ve vekalet ücretinin davalıya yükletilmesine

Karar verilmesini talep ederiz.

Davacı`
}
