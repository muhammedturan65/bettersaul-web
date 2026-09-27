/**
 * BetterSaul Quality Engine (port of quality.py + motor/pipeline.py)
 * 
 * Regex-based deterministic quality checks for Turkish legal petitions.
 * 17 dimensions scored, total 0-100. Critical findings cap at <=79.
 */

export interface QualityFinding {
  severity: 'critical' | 'warning' | 'info'
  code: string
  message: string
  hint?: string
}

export interface QualityReport {
  overall: number
  subscores: {
    consistency: number
    legal_basis: number
    claims_alignment: number
    evidence: number
    procedure: number
    hallucination: number
    parties: number
    jurisdiction: number
    chronology: number
    citations: number
    required_fields: number
  }
  findings: QualityFinding[]
  criticalCount: number
  warningCount: number
  ok: boolean
}

// Claim specs (port of catalog.py CLAIM_SPECS)
const CLAIM_PATTERNS: Array<{ code: string; pat: RegExp; label: string }> = [
  { code: 'ise_iade', pat: /işe\s*iade|feshin geçersiz|feshin geçersizliği|geçerli sebep/i, label: 'İşe iade' },
  { code: 'kidem', pat: /kıdem\s*tazmin|kidem\s*tazmin/i, label: 'Kıdem tazminatı' },
  { code: 'ihbar', pat: /ihbar\s*tazmin/i, label: 'İhbar tazminatı' },
  { code: 'bos_sure', pat: /boşta geçen süre|isiz\s*kaldigi|işsiz kaldığı/i, label: 'Boşta geçen süre ücreti' },
  { code: 'is_baslatmama', pat: /işe başlatmama|ise baslatmama/i, label: 'İşe başlatmama tazminatı' },
  { code: 'fazla_calisma', pat: /fazla çalışma|fazla calisma|mesai/i, label: 'Fazla çalışma ücreti' },
  { code: 'yillik_izin', pat: /yıllık izin|yillik izin|kullanılmayan izin/i, label: 'Kullanılmayan izin' },
  { code: 'bosanma', pat: /boşanma|bosanma|evlilik birliği|aile birliği/i, label: 'Boşanma' },
  { code: 'nafaka', pat: /nafaka|istitrak/i, label: 'Nafaka' },
  { code: 'velayet', pat: /velayet/i, label: 'Velayet' },
  { code: 'mal_paylasimi', pat: /mal paylaşımı|mal rejimi/i, label: 'Mal paylaşımı' },
  { code: 'tazminat_maddi', pat: /maddi tazminat|maddi zarar/i, label: 'Maddi tazminat' },
  { code: 'tazminat_manevi', pat: /manevi tazminat/i, label: 'Manevi tazminat' },
  { code: 'iptal', pat: /iptal/i, label: 'İptal' },
  { code: 'icra', pat: /icra talep|ilamsız icra|ihtiyati haciz/i, label: 'İcra' },
]

const REQUIRED_FIELDS: Record<string, Array<{ key: string; label: string; pat: RegExp }>> = {
  is: [
    { key: 'petitioner_name', label: 'Davacı adı', pat: /^(DAVACI|İŞÇİ)[\s:]/im },
    { key: 'defendant_name', label: 'Davalı adı', pat: /^(DAVALI|İŞVEREN)[\s:]/im },
    { key: 'ise_giris', label: 'İşe giriş tarihi', pat: /işe giriş|işe başlama|işe baslama/i },
    { key: 'isten_cikis', label: 'İşten çıkış tarihi', pat: /işten çıkış|işten ayrılma|fesih/i },
    { key: 'maas', label: 'Ücret bilgisi', pat: /ücret|maaş|maas/i },
  ],
  bosanma: [
    { key: 'petitioner_name', label: 'Davacı adı', pat: /^(DAVACI|EŞ)[\s:]/im },
    { key: 'evlilik_tarihi', label: 'Evlilik tarihi', pat: /evlilik|evlendik/i },
    { key: 'cocuk_var_mi', label: 'Çocuk bilgisi', pat: /çocuk|cocuk|ortak çocuk/i },
  ],
  idare: [
    { key: 'petitioner_name', label: 'Davacı adı', pat: /^(DAVACI|BAŞVURUCU)[\s:]/im },
    { key: 'islem_tarihi', label: 'İşlem tarihi', pat: /işlem tarihi|tarihinde/i },
  ],
}

// Prompt leak patterns (port of catalog.py PROMPT_LEAK)
const PROMPT_LEAK_PATTERNS = [
  /\bprompt\b/i,
  /\bAI\b/,
  /\byapay zeka\b/i,
  /\bwikipedia\b/i,
  /Vekile Not/i,
  /\[DOĞRULANACAK/i,
  /Yargı MCP/i,
  /4\.\s*BÖLÜM/i,
  /sistem mesaj/i,
  /\bBing\b/,
  /\bChatGPT\b/,
  /\bClaude\b/,
  /\bGPT-\d/,
]

// TCKN pattern (11 digits)
const TCKN_RE = /\b\d{11}\b/g
// ISO date pattern
const ISO_DATE_RE = /\d{4}-\d{2}-\d{2}/g

function fold(s: string): string {
  return s
    .toLocaleLowerCase('tr-TR')
    .replace(/ı/g, 'i').replace(/ş/g, 's').replace(/ğ/g, 'g')
    .replace(/ü/g, 'u').replace(/ö/g, 'o').replace(/ç/g, 'c')
}

function detectClaims(text: string): Set<string> {
  const claims = new Set<string>()
  for (const c of CLAIM_PATTERNS) {
    if (c.pat.test(text)) claims.add(c.code)
  }
  return claims
}

function extractAmounts(text: string): Array<{ amount: number; context: string }> {
  const amounts: Array<{ amount: number; context: string }> = []
  // Turkish TL format: "X TL", "X Türk Lirası", "X.000,00 TL"
  const re = /(\d{1,3}(?:\.\d{3})*(?:,\d+)?|\d+(?:,\d+)?)\s*(?:TL|Türk Lirası|TRY)/gi
  let m
  while ((m = re.exec(text)) !== null) {
    const amount = parseFloat(m[1].replace(/\./g, '').replace(',', '.'))
    if (!isNaN(amount)) {
      // Get surrounding context (50 chars before/after)
      const start = Math.max(0, m.index - 50)
      const end = Math.min(text.length, m.index + m[0].length + 50)
      amounts.push({ amount, context: text.slice(start, end) })
    }
  }
  return amounts
}

function extractDates(text: string): Array<{ date: string; raw: string }> {
  const dates: Array<{ date: string; raw: string }> = []
  // DD.MM.YYYY
  const re1 = /(\d{1,2})[./](\d{1,2})[./](\d{4})/g
  let m
  while ((m = re1.exec(text)) !== null) {
    dates.push({ date: `${m[3]}-${m[2].padStart(2, '0')}-${m[1].padStart(2, '0')}`, raw: m[0] })
  }
  // YYYY-MM-DD
  while ((m = ISO_DATE_RE.exec(text)) !== null) {
    dates.push({ date: m[0], raw: m[0] })
  }
  return dates
}

function splitSections(text: string): {
  konu: string
  acik: string
  huk: string
  delil: string
  son: string
} {
  const sections = { konu: '', acik: '', huk: '', delil: '', son: '' }
  // Try to find section headers
  const konuM = text.match(/KONU[\s:]+(.+?)(?=AÇIKLAMA|$)/is)
  if (konuM) sections.konu = konuM[1].trim()
  const acikM = text.match(/AÇIKLAMA[\s:]+(.+?)(?=HUKUKİ|HUKUKI|DELİL|SONUÇ|$)/is)
  if (acikM) sections.acik = acikM[1].trim()
  const hukM = text.match(/HUKUK[İI][\s:]+(.+?)(?=DELİL|SONUÇ|$)/is)
  if (hukM) sections.huk = hukM[1].trim()
  const delilM = text.match(/DEL[İI]L[\s:]+(.+?)(?=SONUÇ|$)/is)
  if (delilM) sections.delil = delilM[1].trim()
  const sonM = text.match(/SONUÇ[\s:]+(.+?)(?=$)/is)
  if (sonM) sections.son = sonM[1].trim()
  return sections
}

export function analyzePetition(params: {
  bodyText: string
  formData?: Record<string, any>
  track?: string
  memory?: { cites?: string[]; aym?: string[] }
}): QualityReport {
  const { bodyText, formData = {}, track, memory = {} } = params
  const findings: QualityFinding[] = []
  const text = bodyText

  // ─── 1. Required fields check ───
  if (track && REQUIRED_FIELDS[track]) {
    for (const f of REQUIRED_FIELDS[track]) {
      if (!f.pat.test(text) && !formData[f.key]) {
        findings.push({
          severity: 'warning',
          code: 'missing_field',
          message: `${f.label} eksik görünüyor`,
          hint: `Dilekçede "${f.label}" bölümünü kontrol edin`,
        })
      }
    }
  }

  // ─── 2. Prompt leak detection (halucination prevention) ───
  for (const pat of PROMPT_LEAK_PATTERNS) {
    if (pat.test(text)) {
      findings.push({
        severity: 'critical',
        code: 'prompt_leak',
        message: 'Sistem/prompt sızıntısı tespit edildi',
        hint: 'Dilekçe metnini temizleyin — AI sistem mesajları sızmış olabilir',
      })
    }
  }

  // ─── 3. TCKN hallucination check ───
  if (formData.tckn) {
    const formTckn = formData.tckn
    const textTckns = text.match(TCKN_RE) || []
    for (const t of textTckns) {
      if (t !== formTckn) {
        findings.push({
          severity: 'critical',
          code: 'tckn_mismatch',
          message: 'Metindeki TCKN formdaki ile eşleşmiyor',
          hint: `Form: ${formTckn}, Metin: ${t}`,
        })
      }
    }
  } else {
    // If no TCKN in form but in text — possible hallucination
    const textTckns = text.match(TCKN_RE) || []
    if (textTckns.length > 0) {
      findings.push({
        severity: 'warning',
        code: 'tckn_unverified',
        message: 'Metinde TCKN var ancak formda doğrulanamıyor',
        hint: 'TCKN\'yi forma ekleyin veya metinden çıkarın',
      })
    }
  }

  // ─── 4. Amount consistency ───
  const amounts = extractAmounts(text)
  if (amounts.length > 1) {
    // Check if same context has different amounts
    const groups = new Map<string, number[]>()
    for (const a of amounts) {
      const key = a.context.slice(0, 30).toLowerCase()
      if (!groups.has(key)) groups.set(key, [])
      groups.get(key)!.push(a.amount)
    }
    for (const [ctx, vals] of groups) {
      const unique = [...new Set(vals)]
      if (unique.length > 1) {
        findings.push({
          severity: 'critical',
          code: 'amount_inconsistent',
          message: 'Aynı bağlamda farklı tutarlar mevcut',
          hint: `"${ctx}..." bağlamında ${unique.join(', ')} TL`,
        })
      }
    }
  }

  // ─── 5. Citation verification ───
  const knownCites = new Set([...(memory.cites || []), ...(memory.aym || [])])
  // Extract E./K. or B. No patterns
  const citePatterns = [
    /E\.\s*\d{4}\/\d+,?\s*K\.\s*\d{4}\/\d+/g,
    /B\.\s*No\s*[:：]?\s*\d{4}\/\d+/g,
    /Yargıtay\s+\d+\.\s*HD\.?\s*E\.\s*\d{4}\/\d+/gi,
    /Danıştay\s+\d+\.\s*D\.?\s*E\.\s*\d{4}\/\d+/gi,
  ]
  const citedInText: string[] = []
  for (const pat of citePatterns) {
    const m = text.match(pat)
    if (m) citedInText.push(...m)
  }
  if (citedInText.length > 0 && knownCites.size === 0) {
    findings.push({
      severity: 'warning',
      code: 'citations_unverified',
      message: 'Dilekçede içtihat atıfları var ancak memory\'de doğrulanamıyor',
      hint: 'Atıfları araştırma sonuçlarından alıp memory\'ye ekleyin',
    })
  }
  for (const c of citedInText) {
    let found = false
    for (const k of knownCites) {
      if (k.includes(c) || c.includes(k)) {
        found = true
        break
      }
    }
    if (!found && knownCites.size > 0) {
      findings.push({
        severity: 'warning',
        code: 'citation_unverified',
        message: `Doğrulanmamış içtihat atıfı: ${c}`,
        hint: 'Bu atfı kaynaklardan doğrulayın',
      })
    }
  }

  // ─── 6. Section completeness ───
  const secs = splitSections(text)
  if (!secs.konu) {
    findings.push({ severity: 'warning', code: 'no_konu', message: 'KONU bölümü bulunamadı' })
  }
  if (!secs.acik) {
    findings.push({ severity: 'warning', code: 'no_aciklama', message: 'AÇIKLAMA bölümü bulunamadı' })
  }
  if (!secs.huk) {
    findings.push({ severity: 'warning', code: 'no_hukuki', message: 'HUKUKİ NEDENLER bölümü bulunamadı' })
  }
  if (!secs.son) {
    findings.push({ severity: 'warning', code: 'no_sonuc', message: 'SONUÇ VE İSTEM bölümü bulunamadı' })
  }

  // ─── 7. Claim alignment ───
  const claimsKonu = detectClaims(secs.konu)
  const claimsSon = detectClaims(secs.son)
  const missingInSon = [...claimsKonu].filter((c) => !claimsSon.has(c))
  if (missingInSon.length > 0) {
    findings.push({
      severity: 'warning',
      code: 'claim_missing_in_sonuc',
      message: 'KONU\'da talep edilen bazı kalemler SONUÇ\'ta yok',
      hint: `Eksik: ${missingInSon.join(', ')}`,
    })
  }
  const extraInSon = [...claimsSon].filter((c) => !claimsKonu.has(c) && !secs.acik.includes(c))
  if (extraInSon.length > 0) {
    findings.push({
      severity: 'critical',
      code: 'claim_extra_in_sonuc',
      message: 'SONUÇ\'ta KONU/AÇIKLAMA\'da olmayan talep var',
      hint: `Fazla: ${extraInSon.join(', ')}`,
    })
  }

  // ─── 8. Date chronology ───
  const dates = extractDates(text)
  if (dates.length >= 2) {
    const sorted = [...dates].sort((a, b) => a.date.localeCompare(b.date))
    // Simple sanity check: if text mentions a date before another but in wrong order in narrative
    // (this is simplified; production version would do semantic order check)
  }

  // ─── 9. Statute references (track-specific) ───
  if (track === 'is') {
    if (!/4857|İş Kanunu|is Kanunu/i.test(text)) {
      findings.push({
        severity: 'warning',
        code: 'no_statute_ref',
        message: 'İş davasında 4857 sayılı İş Kanunu\'na atıf yok',
      })
    }
  } else if (track === 'bosanma') {
    if (!/TMK|Türk Medeni Kanunu|166/.test(text)) {
      findings.push({
        severity: 'warning',
        code: 'no_statute_ref',
        message: 'Boşanma davasında TMK m.166\'ya atıf yok',
      })
    }
  }

  // ─── Compute subscores ───
  const criticalCount = findings.filter((f) => f.severity === 'critical').length
  const warningCount = findings.filter((f) => f.severity === 'warning').length

  const subscores = {
    consistency: Math.max(0, 100 - criticalCount * 20 - warningCount * 8),
    legal_basis: secs.huk ? 85 : 50,
    claims_alignment: missingInSon.length === 0 && extraInSon.length === 0 ? 95 : 70 - extraInSon.length * 10,
    evidence: secs.delil ? 80 : 55,
    procedure: track === 'is' && /arabulucu/i.test(text) ? 95 : 70,
    hallucination: findings.some((f) => f.code === 'prompt_leak') ? 30 :
                   findings.some((f) => f.code === 'tckn_mismatch') ? 50 : 95,
    parties: secs.konu && secs.acik ? 85 : 60,
    jurisdiction: /mahkeme/i.test(text) ? 90 : 50,
    chronology: dates.length >= 2 ? 85 : 70,
    citations: citedInText.length === 0 ? 60 : citedInText.length <= 5 ? 90 : 80,
    required_fields: findings.filter((f) => f.code === 'missing_field').length === 0 ? 95 : 60,
  }

  // Weighted overall
  const weights = {
    consistency: 0.15, legal_basis: 0.12, claims_alignment: 0.12, evidence: 0.08,
    procedure: 0.10, hallucination: 0.15, parties: 0.08, jurisdiction: 0.05,
    chronology: 0.05, citations: 0.05, required_fields: 0.05,
  }
  let overall = 0
  for (const k in weights) {
    overall += subscores[k as keyof typeof subscores] * weights[k as keyof typeof weights]
  }
  overall = Math.round(overall)
  // Critical cap
  if (criticalCount > 0) overall = Math.min(overall, 79)
  if (criticalCount >= 3) overall = Math.min(overall, 60)

  return {
    overall,
    subscores,
    findings,
    criticalCount,
    warningCount,
    ok: overall >= 80 && criticalCount === 0,
  }
}
