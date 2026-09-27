/**
 * BetterSaul Legal Tracks (port of legal_tracks.py)
 * 
 * Regex-based legal track detection for Turkish petitions.
 * Each track has prompt rules embedded to AI during generation.
 */

export interface LegalTrack {
  id: string
  label: string
  ptype: string
  courtHint: string
  pat: string
  procedure?: string[]
  required?: Array<[string, string]>
  promptRules: string[]
}

export const LEGAL_TRACKS: LegalTrack[] = [
  {
    id: 'is',
    label: 'İş ve Çalışma Hukuku',
    ptype: 'İş Davası',
    courtHint: 'iş mahkeme',
    pat: 'isveren|işveren|isci|işçi|kidem|kıdem|ihbar|ise iade|feshin geçersiz|fesih|maas|maaş|ucret|ücret|fazla calisma|fazla çalışma',
    procedure: ['arabuluculuk'],
    required: [
      ['ise_giris', 'İşe giriş tarihi'],
      ['isten_cikis', 'İşten çıkış tarihi'],
      ['maas', 'Aylık ücret'],
    ],
    promptRules: [
      '7036 m.3/5: Arabuluculuk ön şartı',
      '4857 m.32/34/41: Ücret, fazla çalışma, yıllık izin',
      '4857 m.17/18/20/21: Fesih bildirimi, geçerli sebep, işe iade',
      '1475 m.14: Kıdem tazminatı (yürürlükteki maddesi)',
      'HMK m.107: İş davalarında görevli mahkeme',
    ],
  },
  {
    id: 'bosanma',
    label: 'Aile Hukuku',
    ptype: 'Boşanma Davası',
    courtHint: 'aile mahkeme',
    pat: 'bosanma|boşanma|es|eş|evlilik|nikah|nafaka|velayet|istitrak|çocuk|TMK 166|anlaşmalı',
    required: [
      ['evlilik_tarihi', 'Evlilik tarihi'],
      ['cocuk_var_mi', 'Çocuk var mı'],
    ],
    promptRules: [
      'TMK m.166: Boşanma sebepleri (anlaşmalı 166/3, çekişmeli 166/1-2)',
      'TMK m.174: Maddi ve manevi tazminat',
      'TMK m.169: Geçici tedbirler',
    ],
  },
  {
    id: 'idare',
    label: 'İdare Hukuku',
    ptype: 'İdari Dava',
    courtHint: 'idare mahkeme',
    pat: 'idari|idare|iptal|tam yargi|tam yargı|kamu|memur|memuriyet|atama|atanma|vergi|dilekçe',
    procedure: ['idari_basvuru'],
    required: [
      ['islem_tarihi', 'İşlem tarihi'],
      ['idari_basvuru', 'İdari başvuru yapıldı mı'],
    ],
    promptRules: [
      'İYUK m.2: İptal davası süresi 60 gün',
      'İYUK m.3: Yürütmenin durdurulması',
      '657 DMK m.48: Kamu personeli atanma şartları',
    ],
  },
  {
    id: 'tuketici',
    label: 'Tüketici Hukuku',
    ptype: 'Tüketici Davası',
    courtHint: 'tüketici mahkeme',
    pat: 'tuketici|tüketici|satici|satıcı|ayipli|ayıplı|kredi|banka|garanti|6502',
    required: [
      ['satin_alma_tarihi', 'Satın alma tarihi'],
      ['satici', 'Satıcı bilgisi'],
    ],
    promptRules: [
      '6502 m.51: Tüketici kredisi sözleşmesi şartları',
      '6502 m.68: Tüketici mahkemeleri görev alanı',
      '6502 m.18: Ayıplı ifa',
    ],
  },
  {
    id: 'kira',
    label: 'Eşya Hukuku (Kira)',
    ptype: 'Kira Davası',
    courtHint: 'sulh hukuk',
    pat: 'kira|kiraci|kiracı|kiralayan|tahliye|konut|isyeri|işyeri|TBK 350',
    required: [
      ['kira_sozlesmesi', 'Kira sözleşmesi tarihi'],
      ['kira_bedeli', 'Kira bedeli'],
    ],
    promptRules: [
      'TBK m.350: Kiralayanda kullanma gereksinimi (tahliye)',
      'TBK m.315: Kira sözleşmesi şekli',
      'TBK m.342: Kira tespit davası',
    ],
  },
  {
    id: 'alacak',
    label: 'Alacak Hukuku',
    ptype: 'Alacak Davası',
    courtHint: 'asliye hukuk',
    pat: 'alacak|senet|bono|cek|çek|icra|İcra|İİK|ilamsız|borç|borc',
    required: [
      ['alacak_miktari', 'Alacak miktarı'],
      ['borclu', 'Borçlu bilgisi'],
    ],
    promptRules: [
      'İİK m.50: İlamsız icra',
      'TBK m.123: Borcun ifası',
      'HMK m.200: Senetle istihkak davası',
    ],
  },
  {
    id: 'tazminat',
    label: 'Tazminat Hukuku',
    ptype: 'Tazminat Davası',
    courtHint: 'asliye hukuk',
    pat: 'tazminat|maddi|manevi|zarar|kusur|haksiz fiil|TBK 49',
    required: [
      ['zarar_miktari', 'Zarar miktarı'],
      ['zarar_veren', 'Zarar veren taraf'],
    ],
    promptRules: [
      'TBK m.49: Haksız fiil sorumluluğu',
      'TBK m.51: Maddi tazminat',
      'TBK m.58: Manevi tazminat',
    ],
  },
  {
    id: 'ceza',
    label: 'Ceza Hukuku',
    ptype: 'Ceza Davası',
    courtHint: 'ceza mahkeme',
    pat: 'ceza|suç|suc|sanik|şanik|sanık|mağdur|müdahil|TCK|CMK|şikayet|sikayet',
    required: [
      ['suç_tarihi', 'Suç tarihi'],
      ['suç_konusu', 'Suç konusu'],
    ],
    promptRules: [
      'TCK m.43: Zincirleme suç',
      'TCK m.51: Adli para cezası',
      'CMK m.236: Şikayete tabi suçlarda süre',
    ],
  },
  {
    id: 'vergi',
    label: 'Vergi Hukuku',
    ptype: 'Vergi Davası',
    courtHint: 'vergi mahkeme',
    pat: 'vergi|vergisi|tarhiyat|VUK|VUK 114|re\'sen|resen',
    required: [
      ['tarhiyat_tarihi', 'Tarhiyat tarihi'],
      ['vergi_dairesi', 'Vergi dairesi'],
    ],
    promptRules: [
      'VUK m.114: Re\'sen tarhiyat süresi',
      'VUK m.376: Düzeltme zamanaşımı',
      '6183 m.21: Vergi davalarında süre',
    ],
  },
  {
    id: 'miras',
    label: 'Miras Hukuku',
    ptype: 'Miras Davası',
    courtHint: 'sulh hukuk',
    pat: 'miras|muris|veraset|taksim|elbirliği|TMK 599|mirasçı',
    required: [
      ['vefat_tarihi', 'Vefat tarihi'],
      ['muris', 'Muris bilgisi'],
    ],
    promptRules: [
      'TMK m.599: Mirasın geçişi',
      'TMK m.611: Mirasın taksimi',
    ],
  },
]

export function detectTrack(text: string): LegalTrack | null {
  const normalized = text
    .toLocaleLowerCase('tr-TR')
    .replace(/ı/g, 'i').replace(/ş/g, 's').replace(/ğ/g, 'g')
    .replace(/ü/g, 'u').replace(/ö/g, 'o').replace(/ç/g, 'c')
  
  let best: LegalTrack | null = null
  let bestScore = 0
  for (const track of LEGAL_TRACKS) {
    const pat = track.pat.split('|')
    let score = 0
    for (const p of pat) {
      if (normalized.includes(p.toLocaleLowerCase('tr-TR'))) score++
    }
    if (score > bestScore) {
      bestScore = score
      best = track
    }
  }
  return bestScore > 0 ? best : null
}

export function getTrackById(id: string): LegalTrack | undefined {
  return LEGAL_TRACKS.find((t) => t.id === id)
}
