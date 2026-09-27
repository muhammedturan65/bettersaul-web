/* eslint-disable @typescript-eslint/no-require-imports */
/**
 * BetterSaul Seed Script
 * Populates database with sample legal decisions, statutes, and a demo user.
 */
const { PrismaClient } = require('@prisma/client')

const db = new PrismaClient()

async function main() {
  console.log('🌱 Seeding BetterSaul database...')

  // Clean
  await db.documentChunk.deleteMany()
  await db.document.deleteMany()
  await db.researchTrace.deleteMany()
  await db.researchSession.deleteMany()
  await db.aiRun.deleteMany()
  await db.chatMessage.deleteMany()
  await db.chatSession.deleteMany()
  await db.citation.deleteMany()
  await db.petitionReview.deleteMany()
  await db.petitionVersion.deleteMany()
  await db.petition.deleteMany()
  await db.statuteArticle.deleteMany()
  await db.statute.deleteMany()
  await db.legalDecision.deleteMany()
  await db.legalSource.deleteMany()
  await db.caseParty.deleteMany()
  await db.case.deleteMany()
  await db.auditLog.deleteMany()
  await db.apiKey.deleteMany()
  await db.organizationMember.deleteMany()
  await db.organization.deleteMany()
  await db.user.deleteMany()

  // ─── Demo User ───
  const user = await db.user.create({
    data: {
      email: 'demo@bettersaul.legal',
      name: 'Av. Mehmet Demir',
      passwordHash: '$2a$10$placeholder.hash.for.demo.user.bettersaul.2026',
      role: 'lawyer',
      barNo: 'ANK-12345',
      emailVerified: new Date(),
      lastLoginAt: new Date(),
    },
  })

  const org = await db.organization.create({
    data: {
      name: 'Demir & Partners Hukuk Bürosu',
      slug: 'demir-partners',
      plan: 'pro',
      seatCount: 5,
    },
  })

  await db.organizationMember.create({
    data: {
      userId: user.id,
      orgId: org.id,
      role: 'org_admin',
    },
  })

  // ─── Legal Sources ───
  const sources = await Promise.all([
    db.legalSource.create({ data: { name: 'yargitay', label: 'Yargıtay', baseUrl: 'https://karararama.yargitay.gov.tr', enabled: true } }),
    db.legalSource.create({ data: { name: 'danistay', label: 'Danıştay', baseUrl: 'https://danistaydergiler.adalet.gov.tr', enabled: true } }),
    db.legalSource.create({ data: { name: 'emsal', label: 'Emsal (UYAP)', baseUrl: 'https://emsal.uyap.gov.tr', enabled: true } }),
    db.legalSource.create({ data: { name: 'aym', label: 'Anayasa Mahkemesi', baseUrl: 'https://anayasa.gov.tr', enabled: true } }),
    db.legalSource.create({ data: { name: 'resmi_gazete', label: 'Resmî Gazete', baseUrl: 'https://resmigazete.gov.tr', enabled: true } }),
    db.legalSource.create({ data: { name: 'mevzuat', label: 'Mevzuat', baseUrl: 'https://mevzuat.gov.tr', enabled: true } }),
  ])
  const [yargitay, danistay, emsal, aym, , mevzuat] = sources

  // ─── Statutes ───
  const isKanunu = await db.statute.create({
    data: {
      name: '4857 sayılı İş Kanunu',
      statuteNo: '4857',
      sourceId: mevzuat.id,
      sourceUrl: 'https://www.mevzuat.gov.tr/mevzuatmetin/1.5.4857.pdf',
    },
  })

  const statuteArticles = [
    { articleNo: '17', title: 'İşçinin korunması', bodyText: 'İşveren, iş sözleşmesiyle veya işin niteliğine bağlı olarak, işçinin bilmesi gereken hususları işçiye bildirmekle yükümlüdür.' },
    { articleNo: '18', title: 'Feshin geçerli sebebe dayanması', bodyText: 'İşveren, işçinin en az altı aylık kıdemi olan işçiyi; ilgili kanunda veya iş sözleşmesinde gösterilen nedenler dışında iş ilişkisini feshedemez.' },
    { articleNo: '20', title: 'Feshin bildirimi', bodyText: 'İşveren, iş sözleşmesini feshederken, feshin en az bir ay önceden bildirim yapması gerekir.' },
    { articleNo: '21', title: 'Bildirimsiz fesih', bodyText: 'İşveren, sözleşmeyi bildirim süresine uymadan feshetmek isterse, bildirim süresine ait ücreti işçiye ödemek zorundadır.' },
    { articleNo: '32', title: 'Ücret', bodyText: 'Ücret, işveren tarafından işçiye iş karşılığında ödenen para ve para ile ölçülebilen şeylerdir.' },
    { articleNo: '41', title: 'Fazla çalışma', bodyText: 'Fazla çalışma, kanunda belirtilen haftalık çalışma süresinin dışında yapılan çalışmalardır.' },
  ]
  for (const a of statuteArticles) {
    await db.statuteArticle.create({
      data: {
        statuteId: isKanunu.id,
        articleNo: a.articleNo,
        version: 1,
        title: a.title,
        bodyText: a.bodyText,
        effectiveFrom: new Date('2003-06-10'),
      },
    })
  }

  // ─── Sample Legal Decisions (mock) ───
  const decisions = [
    {
      sourceId: yargitay.id,
      sourceDocId: 'YARG-2024-12345',
      court: 'Yargıtay',
      courtChamber: '9. Hukuk Dairesi',
      decisionNumber: 'E. 2024/12345, K. 2024/6789',
      caseNumber: 'İş Mahkemesi 2023/456',
      decisionDate: new Date('2024-03-15'),
      documentType: 'decision',
      title: 'İşe İade Davası — Feshin Geçerli Sebep İçermemesi',
      summary: 'Davacının iş sözleşmesinin feshedilmesi sırasında 4857 sayılı İş Kanunu madde 18 gereği geçerli sebebin gösterilmemesi nedeniyle işe iadeye hükmedilmiştir.',
      fullText: `Temyiz Eden: ... Davacı
Karşı Taraf: ... Davalı işveren
Dava: İşe iade
Karar: Feshin geçerli sebebe dayanmadığı tespit edilerek davacının işe iadesine
Dosya: ... mahkemesinden gelen iş davasıdır. Davacı, iş sözleşmesinin haksız olarak feshedildiğini ileri sürerek feshin geçersizliğine ve işe iadeye karar verilmesini talep etmiştir. Mahkeme, davayı kabul etmiştir. Davalı işveren, temyiz kanunu yoluna başvurmuştur.
4857 sayılı İş Kanunu'nun 18. maddesi gereği, işverenin feshin geçerli bir sebebe dayandığını ispat yükümlülüğü vardır. Somut olayda, davalı işveren fesih bildiriminde herhangi bir geçerli sebep belirtmemiştir. Feshin son çare olarak kullanılmadığı anlaşılmaktadır.
Hüküm: Davalı işverenin temyiz itirazlarının reddiyle, mahkeme kararının onanmasına.`,
      keywords: JSON.stringify(['işe iade', 'fesih', 'geçerli sebep', '4857/18', 'kıdem']),
      topics: JSON.stringify(['iş_hukuku', 'işe_iade']),
      similarityScore: 0.94,
    },
    {
      sourceId: yargitay.id,
      sourceDocId: 'YARG-2023-88765',
      court: 'Yargıtay',
      courtChamber: '2. Hukuk Dairesi',
      decisionNumber: 'E. 2023/88765, K. 2023/44321',
      caseNumber: 'Aile Mahkemesi 2023/1234',
      decisionDate: new Date('2023-11-22'),
      documentType: 'decision',
      title: 'Anlaşmalı Boşanma — Sözleşmenin İncelenmesi',
      summary: 'Anlaşmalı boşanma davasında, taraflar arasında akdedilen boşanma protokolünün Türk Medeni Kanunu madde 166/3 kapsamında geçerlilik şartlarını taşıdığı tespit edilmiştir.',
      fullText: `Temyiz Eden: ... Davacı eş
Karşı Taraf: ... Davalı eş
Dava: Anlaşmalı boşanma
Türk Medeni Kanunu madde 166/3 gereği, eşlerin boşanma konusunda anlaşmış olmaları ve mahkemeye birlikte başvurmaları ya da eşlerden birinin diğerinin boşanma davasını kabul etmesi halinde, boşanmaya karar verilir.
Somut olayda, taraflar arasında akdedilen protokolde velayet, nafaka ve mal paylaşımı düzenlemesi yapılmıştır. Mahkeme, 1 yıllık bekleme süresinin dolduğunu tespit ederek boşanmaya karar vermiştir.
Hüküm: Onama.`,
      keywords: JSON.stringify(['anlaşmalı boşanma', 'TMK 166', 'protokol', 'velayet']),
      topics: JSON.stringify(['aile_hukuku', 'boşanma']),
      similarityScore: 0.87,
    },
    {
      sourceId: danistay.id,
      sourceDocId: 'DAN-2024-5544',
      court: 'Danıştay',
      courtChamber: '5. Dairesi',
      decisionNumber: 'E. 2024/5544, K. 2024/2211',
      caseNumber: 'İdare Mahkemesi 2023/987',
      decisionDate: new Date('2024-06-08'),
      documentType: 'decision',
      title: 'Güvenlik Soruşturması Nedeniyle Kamu Görevine Atanmama',
      summary: 'Güvenlik soruşturması sonucu olumsuz rapor verilmesi nedeniyle kamu görevine atanmama işleminin, ölçülülük ve gereklilik ilkeleri gözetilerek iptaline karar verilmiştir.',
      fullText: `Davacı: ...
Davalı: ... Bakanlığı
Dava: İptal
Davacı, güvenlik soruşturması sonucu verilen olumsuz rapor nedeniyle kamu görevine atanmama işleminin iptalini istemiştir.
Danıştay 5. Dairesi, güvenlik soruşturması sonucu verilen olumsuz raporun ayrıntılı gerekçe içermemesi ve atama işleminin ölçülülük ilkesine uygun olmadığı gerekçesiyle iptaline karar vermiştir.
Güvenlik soruşturması ve arşiv araştırması sonucu düzenlenen raporun, ilgilinin kamu hizmetine girmesine engel oluşturacak nitelikte somut tespitler içermesi gerekir. Soyut ve belirsiz ifadelerle atama işleminin iptali mümkün değildir.`,
      keywords: JSON.stringify(['güvenlik soruşturması', 'arşiv araştırması', 'kamu görevi', 'atanmama', 'ölçülülük']),
      topics: JSON.stringify(['idare_hukuku', 'kamu_görevi']),
      similarityScore: 0.92,
    },
    {
      sourceId: aym.id,
      sourceDocId: 'AYM-2023-1234',
      court: 'Anayasa Mahkemesi',
      courtChamber: '',
      decisionNumber: 'B. No: 2023/1234',
      caseNumber: '',
      decisionDate: new Date('2023-09-12'),
      documentType: 'decision',
      title: 'İfade Özgürlüğü — Cezaevinde Yazarın Kitap Yasakları',
      summary: 'Cezaevinde bulunan bir yazarın belirli kitaplara erişiminin engellenmesinin ifade özgürlüğünün özüne müdahale teşkil ettiği tespit edilmiştir.',
      fullText: `Başvuru No: 2023/1234
Başvurucu: ...
İhlal İddia Edilen Hak: İfade özgürlüğü (Anayasa madde 26)
İnceleme: Anayasa Mahkemesi, cezaevi idaresinin başvurucunun belirli kitaplara erişimini kısıtlamasının Anayasa madde 26 ile güvence altına alınan ifade özgürlüğünün özüne yönelik bir müdahale olduğunu tespit etmiştir.
Hüküm: İhlal kararı.`,
      keywords: JSON.stringify(['ifade özgürlüğü', 'cezaevi', 'kitap yasak', 'Anayasa 26']),
      topics: JSON.stringify(['anayasa_hukuku', 'temel_haklar']),
      similarityScore: 0.78,
    },
    {
      sourceId: yargitay.id,
      sourceDocId: 'YARG-2024-44556',
      court: 'Yargıtay',
      courtChamber: '3. Hukuk Dairesi',
      decisionNumber: 'E. 2024/44556, K. 2024/22998',
      caseNumber: 'Tüketici Mahkemesi 2023/789',
      decisionDate: new Date('2024-01-30'),
      documentType: 'decision',
      title: 'Tüketici Kredisi — Sözleşmesel Eksiklik',
      summary: 'Tüketici kredisi sözleşmesinde yıllık faiz oranının net olarak belirtilmemesi nedeniyle 6502 sayılı Tüketicinin Korunması Hakkında Kanun ihlali tespit edilmiştir.',
      fullText: `Temyiz Eden: ... Davacı tüketici
Karşı Taraf: ... Davalı banka
Dava: Sözleşmenin iptali
6502 sayılı Kanun madde 51 gereği, tüketici kredisi sözleşmesinde yıllık faiz oranı, akdi faiz, gecikme faizi ve masraflar net olarak belirtilmelidir.
Somut olayda, sözleşmede yalnızca aylık faiz oranı gösterilmiş, yıllık eşdeğer oran hesaplanmamıştır. Bu durum, tüketicinin aydınlatılma yükümlülüğünün ihlali anlamına gelir.`,
      keywords: JSON.stringify(['tüketici kredisi', '6502/51', 'faiz oranı', 'sözleşme']),
      topics: JSON.stringify(['tüketici_hukuku', 'kredi']),
      similarityScore: 0.81,
    },
    {
      sourceId: yargitay.id,
      sourceDocId: 'YARG-2024-77889',
      court: 'Yargıtay',
      courtChamber: '1. Hukuk Dairesi',
      decisionNumber: 'E. 2024/77889, K. 2024/33456',
      caseNumber: 'Asliye Hukuk 2023/1234',
      decisionDate: new Date('2024-08-19'),
      documentType: 'decision',
      title: 'Kira Sözleşmesinde Tahliye — Yenilenen Sözleşme',
      summary: 'Kiralananın yeniden kiraya verme amacıyla tahliyesi talebinde, kiralayanın ihtiyaçını samimi olarak kanıtlaması gerektiği vurgulanmıştır.',
      fullText: `Temyiz Eden: ... Davalı kiralayan
Karşı Taraf: ... Davacı kiracı
Dava: Tahliye
Türk Borçlar Kanunu madde 350 gereği, kiralayanan, kiralananı kendisi, eşi, altsoyu, üstsoyu veya bakmakla yükümlü olduğu diğer kişiler için konut ya da işyeri gereksinimi sebebiyle kullanma zorunluluğu varsa, kullanma gereksiniminin somut olaylarla kanıtlanması gerekir.`,
      keywords: JSON.stringify(['kira', 'tahliye', 'TBK 350', 'ihtiyaç', 'konut']),
      topics: JSON.stringify(['eşya_hukuku', 'kira']),
      similarityScore: 0.86,
    },
    {
      sourceId: danistay.id,
      sourceDocId: 'DAN-2024-9900',
      court: 'Danıştay',
      courtChamber: '7. Dairesi',
      decisionNumber: 'E. 2024/9900, K. 2024/4455',
      caseNumber: 'Vergi Mahkemesi 2023/654',
      decisionDate: new Date('2024-05-03'),
      documentType: 'decision',
      title: 'Vergi İncelemesinde Süre Aşımı',
      summary: "Vergi incelemesi sırasında re'sen tarhiyat yapılması için öngörülen sürelerin aşılması nedeniyle tahakkuk iptal edilmiştir.",
      fullText: `Davacı: ... Limited Şirketi
Davalı: ... Vergi Dairesi
Dava: Tahakkukun iptali
213 sayılı Vergi Usul Kanunu madde 114/1 gereği, vergi incelemesinin belli sürelerde tamamlanması esastır. Süre aşımı nedeniyle re-sen tarhiyat yapılamaz.`,
      keywords: JSON.stringify(['vergi', 're\'sen tarhiyat', 'süre aşımı', 'VUK 114']),
      topics: JSON.stringify(['vergi_hukuku']),
      similarityScore: 0.79,
    },
    {
      sourceId: yargitay.id,
      sourceDocId: 'YARG-2023-22334',
      court: 'Yargıtay',
      courtChamber: '13. Hukuk Dairesi',
      decisionNumber: 'E. 2023/22334, K. 2023/14567',
      caseNumber: 'İcra Hukuk 2023/456',
      decisionDate: new Date('2023-07-25'),
      documentType: 'decision',
      title: 'Kıymetli Evrakta İmza İkrarı',
      summary: 'Bonoda imza inkarı, ancak yazılı belge ile çürütülebilir. İmzayı ikrar etmeyen borçlunun borçtan kurtulması mümkün değildir.',
      fullText: `İcra Mahkemesi 2023/456
Davacı: ...
Davalı: ...
Dava: İtirazın iptali
2004 sayılı İcra ve İflas Kanunu ve 6762 sayılı Türk Ticaret Kanunu kapsamında kıymetli evrak niteliğindeki bonoda imza, yazılı belge ile çürütülebilir.`,
      keywords: JSON.stringify(['bono', 'imza', 'kıymetli evrak', 'icra']),
      topics: JSON.stringify(['ticaret_hukuku', 'kıymetli_evrak']),
      similarityScore: 0.83,
    },
  ]

  for (const d of decisions) {
    await db.legalDecision.create({ data: d })
  }

  // ─── Demo Cases & Petitions ───
  const case1 = await db.case.create({
    data: {
      orgId: org.id,
      title: 'Mustafa Y. v. ABC Teknoloji A.Ş.',
      caseNo: 'İş Mahkemesi 2026/123',
      court: 'Ankara 3. İş Mahkemesi',
      track: 'is',
      status: 'open',
      createdById: user.id,
    },
  })

  await db.caseParty.create({
    data: {
      caseId: case1.id,
      role: 'plaintiff',
      name: 'Mustafa Y.',
      tckn: '12345678901',
      address: 'Çankaya / Ankara',
    },
  })

  await db.caseParty.create({
    data: {
      caseId: case1.id,
      role: 'defendant',
      name: 'ABC Teknoloji A.Ş.',
      address: 'Odtü Teknokent / Ankara',
    },
  })

  const petition1 = await db.petition.create({
    data: {
      orgId: org.id,
      caseId: case1.id,
      userId: user.id,
      petitionType: 'is',
      track: 'is',
      status: 'draft',
    },
  })

  await db.petitionVersion.create({
    data: {
      petitionId: petition1.id,
      versionNo: 1,
      bodyText: `ANKARA 3. İŞ MAHKEMESİ'NE

İŞÇİ (DAVACI): Mustafa Y.
T.C. No: 12345678901
Adres: Çankaya / Ankara

İŞVEREN (DAVALI): ABC Teknoloji A.Ş.
Adres: Odtü Teknokent / Ankara

KONU: İşe iade ve sonuçları talepli dilekçemizdir.

AÇIKLAMALAR:
1. Davacı, davalı işyerinde 15.01.2022 tarihinden itibaren yazılım mühendisi olarak çalışmaktadır.
2. Davalı işveren, 10.03.2026 tarihinde herhangi bir geçerli sebep göstermeksizin iş sözleşmesini feshetmiştir.
3. 4857 sayılı İş Kanunu madde 18 gereği feshin geçerli sebebe dayanması gerekmektedir.

HUKUKİ NEDENLER:
4857 sayılı İş Kanunu m. 17, 18, 20, 21, 32; 1475 sayılı İş Kanunu m. 14; HMK m. 107 ve ilgili yargı kararları.

SONUÇ VE İSTEM:
1. Feshin geçersizliğine,
2. Davacının işe iadesine,
3. Boşta geçen süre ücreti (4 ay) ile işe başlatmama tazminatına,
4. Kıdem ve ihbar tazminatına,
5. Yargılama giderleri ve vekalet ücretinin davalıya yükletilmesine karar verilmesini talep ederiz.

Davacı
Mustafa Y.`,
      formData: JSON.stringify({
        petitioner_name: 'Mustafa Y.',
        petitioner_tckn: '12345678901',
        defendant_name: 'ABC Teknoloji A.Ş.',
        court: 'Ankara 3. İş Mahkemesi',
        case_no: 'İş Mahkemesi 2026/123',
        petition_type: 'is',
        facts: '15.01.2022 tarihinden beri yazılım mühendisi olarak çalışmaktayım. 10.03.2026 tarihinde sebepsiz feshiyat yapıldı.',
        claims: ['ise_iade', 'bos_sure', 'is_baslatmama', 'kidem', 'ihbar'],
      }),
      qualityScore: 82,
      qualityReport: JSON.stringify({
        overall: 82,
        subscores: {
          consistency: 88,
          legal_basis: 80,
          claims_alignment: 85,
          evidence: 70,
          procedure: 90,
          hallucination: 95,
          parties: 78,
        },
        findings: [
          { severity: 'warning', code: 'evidence_missing', message: 'İhtarname gönderildiğine dair delil eklenmemiş.' },
          { severity: 'info', code: 'arabulucu_required', message: 'İş davalarında arabuluculuk ön şartı gereklidir.' },
        ],
      }),
      createdById: user.id,
    },
  })
  await db.petition.update({
    where: { id: petition1.id },
    data: { currentVersionId: petition1.id, status: 'reviewed' },
  })

  // Second petition - simplified sample
  const case2 = await db.case.create({
    data: {
      orgId: org.id,
      title: 'Ayşe K. v. Bay K. — Boşanma',
      caseNo: 'Aile Mahkemesi 2026/456',
      court: 'Ankara 2. Aile Mahkemesi',
      track: 'bosanma',
      status: 'open',
      createdById: user.id,
    },
  })

  const petition2 = await db.petition.create({
    data: {
      orgId: org.id,
      caseId: case2.id,
      userId: user.id,
      petitionType: 'bosanma',
      track: 'bosanma',
      status: 'draft',
    },
  })

  await db.petitionVersion.create({
    data: {
      petitionId: petition2.id,
      versionNo: 1,
      bodyText: `ANKARA 2. AİLE MAHKEMESİ'NE

DAVACI: Ayşe K.
DAVALI: Bay K.

KONU: Anlaşmalı boşanma davasıdır.

AÇIKLAMALAR: Taraflar 15.06.2019 tarihinde evlenmiş, ortak yaşam 06.2025 tarihinden itibaren sürdürülememekte olup, boşanma konusunda anlaşmaya varılmıştır.

HUKUKİ NEDENLER: TMK m. 166/3, 174 ve ilgili yargı kararları.

SONUÇ VE İSTEM: Anlaşmalı olarak boşanmaya karar verilmesini talep ederiz.

Davacı vekili`,
      formData: JSON.stringify({ petition_type: 'bosanma' }),
      qualityScore: 65,
      qualityReport: JSON.stringify({
        overall: 65,
        subscores: { consistency: 70, legal_basis: 60, claims_alignment: 65, evidence: 50, procedure: 80, hallucination: 90, parties: 60 },
        findings: [
          { severity: 'critical', code: 'protocol_missing', message: 'Boşanma protokolü eklenmemiş.' },
          { severity: 'warning', code: 'mal_sharing', message: 'Mal paylaşım düzenlemesi yok.' },
        ],
      }),
      createdById: user.id,
    },
  })
  await db.petition.update({
    where: { id: petition2.id },
    data: { currentVersionId: petition2.id, status: 'draft' },
  })

  // ─── Chat sessions ───
  await db.chatSession.create({
    data: {
      userId: user.id,
      title: 'İşe iade süresi',
      track: 'is',
      messages: {
        create: [
          {
            role: 'user',
            content: 'İş sözleşmem 3 yıllık kıdemimle sebepsiz feshedildi. Ne yapmalıyım?',
          },
          {
            role: 'assistant',
            content: 'İş Kanunu madde 18 kapsamında, 6 aylık kıdemi aşan işçinin sözleşmesinin feshi için geçerli sebep gereklidir. Somut olayınızda feshin geçerli sebebe dayanmadığı tespit edilirse:\n\n1. **İşe iade** davası açabilirsiniz (fesihten itibaren 1 ay içinde)\n2. **Boşta geçen süre ücreti** (en fazla 4 ay)\n3. **İşe başlatmama tazminatı** (4 aylık ücret)\n4. **Kıdem ve ihbar tazminatı**\n\nÖnemli: İş davalarında **arabuluculuk** ön şarttır. Dava açmadan önce arabulucuya başvurmanız gerekir.\n\n[1] 4857 sayılı İş Kanunu m. 18\n[2] 7036 sayılı İş Mahkemeleri Kanunu m. 3',
            citations: JSON.stringify([
              { source: 'statute', ref: '4857 sayılı İş Kanunu m. 18', verified: true },
              { source: 'statute', ref: '7036 sayılı İş Mahkemeleri Kanunu m. 3', verified: true },
            ]),
          },
        ],
      },
    },
  })

  // ─── Research session ───
  await db.researchSession.create({
    data: {
      userId: user.id,
      orgId: org.id,
      query: 'İş sözleşmesinin sebepsiz feshi — işe iade',
      track: 'is',
      status: 'completed',
      completedAt: new Date(),
      startedAt: new Date(Date.now() - 1000 * 60 * 3),
      traces: {
        create: [
          { stepOrder: 1, stepType: 'intent_detect', stepName: 'Niyet tespiti', input: JSON.stringify({ query: 'iş sözleşmesinin sebepsiz feshi' }), output: JSON.stringify({ intent: 'legal_research', track: 'is' }), durationMs: 240, startedAt: new Date(Date.now() - 1000 * 60 * 3), completedAt: new Date(Date.now() - 1000 * 60 * 3 + 240) },
          { stepOrder: 2, stepType: 'query_gen', stepName: 'Arama sorgusu üretimi', output: JSON.stringify({ queries: ['işe iade feshin geçersizliği', '4857 sayılı kanun madde 18', 'iş sözleşmesi feshi geçerli sebep'] }), durationMs: 680, startedAt: new Date(Date.now() - 1000 * 60 * 3 + 240), completedAt: new Date(Date.now() - 1000 * 60 * 3 + 920) },
          { stepOrder: 3, stepType: 'search', stepName: 'Mevzuat taraması', output: JSON.stringify({ count: 4, sources: ['4857/18', '4857/20', '4857/21', '7036/3'] }), durationMs: 1240, startedAt: new Date(Date.now() - 1000 * 60 * 3 + 920), completedAt: new Date(Date.now() - 1000 * 60 * 3 + 2160) },
          { stepOrder: 4, stepType: 'search', stepName: 'İçtihat taraması (Yargıtay)', output: JSON.stringify({ count: 38, relevant: 12 }), durationMs: 2380, startedAt: new Date(Date.now() - 1000 * 60 * 3 + 2160), completedAt: new Date(Date.now() - 1000 * 60 * 3 + 4540) },
          { stepOrder: 5, stepType: 'semantic_search', stepName: 'Semantic arama (pgvector)', output: JSON.stringify({ count: 12, top_score: 0.94 }), durationMs: 680, startedAt: new Date(Date.now() - 1000 * 60 * 3 + 4540), completedAt: new Date(Date.now() - 1000 * 60 * 3 + 5220) },
          { stepOrder: 6, stepType: 'rerank', stepName: 'Cross-encoder reranking', output: JSON.stringify({ final_count: 7 }), durationMs: 410, startedAt: new Date(Date.now() - 1000 * 60 * 3 + 5220), completedAt: new Date(Date.now() - 1000 * 60 * 3 + 5630) },
          { stepOrder: 7, stepType: 'verify', stepName: 'Kaynak doğrulama', output: JSON.stringify({ verified: 7, unverified: 0 }), durationMs: 320, startedAt: new Date(Date.now() - 1000 * 60 * 3 + 5630), completedAt: new Date(Date.now() - 1000 * 60 * 3 + 5950) },
          { stepOrder: 8, stepType: 'synthesize', stepName: 'AI sentez', output: JSON.stringify({ answer_length: 1240 }), durationMs: 3450, startedAt: new Date(Date.now() - 1000 * 60 * 3 + 5950), completedAt: new Date(Date.now() - 1000 * 60 * 3 + 9400) },
        ],
      },
    },
  })

  console.log('✅ Seed complete:')
  console.log(`   - User: ${user.email} (${user.name})`)
  console.log(`   - Org: ${org.name}`)
  console.log(`   - Legal sources: ${sources.length}`)
  console.log(`   - Legal decisions: ${decisions.length}`)
  console.log(`   - Statutes: 1, Articles: ${statuteArticles.length}`)
  console.log(`   - Cases: 2`)
  console.log(`   - Petitions: 2`)
  console.log(`   - Chat sessions: 1`)
  console.log(`   - Research sessions: 1 (8 traces)`)
}

main()
  .catch((e) => {
    console.error(e)
    process.exit(1)
  })
  .finally(async () => {
    await db.$disconnect()
  })
