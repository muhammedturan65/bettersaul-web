"""Dava türü + talep kataloğu. Madde uydurmaz; eşleştirme ve eksik-alan matrisidir."""
from __future__ import annotations

CLAIM_SPECS: tuple[tuple[str, str, str], ...] = (
    # İş
    ("ise_iade", r"işe\s*iade|ise\s*iade|feshin geçersiz", "işe iade"),
    ("baslatmama", r"işe\s*başlatmama|baslatmama tazmin", "işe başlatmama tazminatı"),
    ("bos_sure", r"boşta\s*geçen|bosta\s*gecen", "boşta geçen süre ücreti"),
    ("kidem", r"kıdem\s*tazmin|kidem\s*tazmin", "kıdem tazminatı"),
    ("ihbar", r"ihbar\s*tazmin", "ihbar tazminatı"),
    ("fazla", r"fazla\s*(çalış|calis|mesai)", "fazla çalışma ücreti"),
    ("ubgt", r"ulusal\s*bayram|genel\s*tatil\s*ücret|ubgt", "UBGT ücreti"),
    ("hafta", r"hafta\s*tatili", "hafta tatili ücreti"),
    ("izin", r"yıllık\s*izin|yillik\s*izin", "yıllık izin ücreti"),
    ("ucret", r"ödenmeyen\s*ücret|odenmeyen\s*ucret|eksik\s*/?\s*ödenmeyen|ücret\s*alaca|ucret\s*alaca", "ücret alacağı"),
    ("kotu_niyet", r"kötü\s*niyet\s*tazmin|kotu\s*niyet\s*tazmin", "kötü niyet tazminatı"),
    ("ayrimcilik", r"ayrımcılık\s*tazmin|ayrimcilik", "ayrımcılık tazminatı"),
    ("is_kazasi", r"iş\s*kazas|meslek\s*hastal", "iş kazası / meslek hastalığı"),
    ("hizmet_tespit", r"hizmet\s*tespit", "hizmet tespiti"),
    ("sendika", r"sendikal\s*tazmin", "sendikal tazminat"),
    ("isveren_alacak", r"işveren\s*alaca", "işveren alacağı"),
    # Aile
    ("tmk166", r"TMK\s*m?\.?\s*166|temelinden sarsıl|temelinden sarsil|çekişmeli boşan|cekismeli bosan", "TMK 166 boşanma"),
    ("tmk164", r"TMK\s*m?\.?\s*164|terke dayalı|terke dayali|terk nedeniyle", "TMK 164 terk"),
    ("anlasmali", r"anlaşmalı boşan|anlasmali bosan|TMK\s*m?\.?\s*166/3", "anlaşmalı boşanma"),
    ("tedbir_nafaka", r"tedbir\s*nafaka", "tedbir nafakası"),
    ("istirak", r"iştirak\s*nafaka|istirak\s*nafaka", "iştirak nafakası"),
    ("yoksulluk", r"yoksulluk\s*nafaka", "yoksulluk nafakası"),
    ("nafaka_artirim", r"nafaka\s*artır|nafaka\s*artir", "nafaka artırımı"),
    ("nafaka_azalt", r"nafaka\s*azalt", "nafaka azaltılması"),
    ("nafaka_kaldir", r"nafaka\s*kaldır|nafaka\s*kaldir", "nafaka kaldırılması"),
    ("nafaka", r"(?<!tedbir\s)(?<!iştirak\s)(?<!istirak\s)(?<!yoksulluk\s)nafaka", "nafaka"),
    ("maddi_tz", r"maddi\s*tazminat", "maddi tazminat"),
    ("manevi_tz", r"manevi\s*tazminat", "manevi tazminat"),
    ("velayet_degis", r"velayetin\s*değiştir|velayetin\s*degistir", "velayetin değiştirilmesi"),
    ("kisisel_iliski", r"kişisel\s*ilişki|kisisel\s*iliski", "kişisel ilişki"),
    ("velayet", r"velayet", "velayet"),
    ("mal_rejimi", r"mal\s*rejimi|tasfiye", "mal rejiminin tasfiyesi"),
    ("katilma", r"katılma\s*alaca|katilma\s*alaca", "katılma alacağı"),
    ("deger_artis", r"değer\s*artış\s*pay|deger\s*artis\s*pay", "değer artış payı"),
    ("ziynet", r"ziynet", "ziynet"),
    ("aile_konutu", r"aile\s*konutu", "aile konutu"),
    ("babalik", r"babalık|babalik|soybağı|soybaji", "soybağı / babalık"),
    # Borçlar / alacak
    ("donme", r"sözleşmeden\s*dön|sozlesmeden\s*don", "sözleşmeden dönme"),
    ("sozlesme_fesih", r"sözleşmenin\s*feshi|sozlesmenin\s*feshi", "sözleşmenin feshi"),
    ("sozlesme_iptal", r"sözleşmenin\s*iptali|sozlesmenin\s*iptali", "sözleşmenin iptali"),
    ("haksiz_fiil", r"haksız\s*fiil|haksiz\s*fiil", "haksız fiil"),
    ("sebepsiz", r"sebepsiz\s*zengin", "sebepsiz zenginleşme"),
    ("temerrut", r"temerrüt|temerrut", "temerrüt"),
    ("bedel_indirim", r"bedel\s*indirim", "bedel indirimi"),
    ("menfi_zarar", r"menfi\s*zarar", "menfi zarar"),
    ("musbet_zarar", r"müsbet\s*zarar|musbet\s*zarar", "müsbet zarar"),
    ("para_alacak", r"para\s*alaca|alacak\s*davas", "para / alacak"),
    # Kira
    ("kira_alacak", r"kira\s*alaca|ödenmeyen\s*kira|odenmeyen\s*kira", "kira alacağı"),
    ("tahliye", r"tahliye", "tahliye"),
    ("ihtiyac_tahliye", r"ihtiyaç\s*(nedeniyle\s*)?tahliye|ihtiyac.{0,12}tahliye", "ihtiyaç tahliyesi"),
    ("kira_tespit", r"kira\s*bedelinin\s*tespit|kira\s*tespit", "kira tespiti"),
    ("kira_uyarlama", r"kira.{0,12}uyarlama", "kira uyarlaması"),
    ("depozito", r"depozito", "depozito iadesi"),
    ("aidat", r"aidat|yan\s*gider", "aidat / yan gider"),
    # Tüketici
    ("ayipli_mal", r"ayıplı\s*mal|ayipli\s*mal", "ayıplı mal"),
    ("ayipli_hizmet", r"ayıplı\s*hizmet|ayipli\s*hizmet", "ayıplı hizmet"),
    ("bedel_iade", r"bedel\s*iade", "bedel iadesi"),
    ("onarim", r"ücretsiz\s*onarım|ucretsiz\s*onarim", "ücretsiz onarım"),
    ("degisim", r"malın\s*değişim|degisim\s*talebi", "değişim"),
    ("mesafeli", r"mesafeli\s*sözleşme|mesafeli\s*sozlesme", "mesafeli sözleşme"),
    ("devre_tatil", r"devre\s*tatil", "devre tatil"),
    ("on_odemeli", r"ön\s*ödemeli\s*konut|on\s*odemeli\s*konut", "ön ödemeli konut"),
    ("abonelik", r"abonelik", "abonelik"),
    # Ticaret / kıymetli evrak
    ("ticari_alacak", r"ticari\s*alacak|cari\s*hesap", "ticari / cari alacak"),
    ("fatura_alacak", r"fatura\s*alaca", "fatura alacağı"),
    ("haksiz_rekabet", r"haksız\s*rekabet|haksiz\s*rekabet", "haksız rekabet"),
    ("gk_iptal", r"genel\s*kurul.{0,20}iptal", "genel kurul kararının iptali"),
    ("cek", r"\bçek\b|\bsenet\b|kambiyo", "çek / senet"),
    # İcra
    ("menfi_tespit", r"menfi\s*tespit", "menfi tespit"),
    ("istirdat", r"istirdat", "istirdat"),
    ("itiraz_iptal", r"itirazın\s*iptali|itirazin\s*iptali", "itirazın iptali"),
    ("borctan_kurtulma", r"borçtan\s*kurtul|borctan\s*kurtul", "borçtan kurtulma"),
    # Taşınmaz
    ("tapu_iptal", r"tapu\s*iptal", "tapu iptali ve tescil"),
    ("muvazaa", r"muvazaa", "muvazaa"),
    ("ortaklik_giderme", r"ortaklığın\s*gider|ortakligin\s*gider|izale", "ortaklığın giderilmesi"),
    ("elatma", r"elatmanın\s*önlen|elatmanin\s*onlen", "elatmanın önlenmesi"),
    ("ecrimisil", r"ecrimisil|haksız\s*işgal|haksiz\s*isgal", "ecrimisil"),
    ("gecit", r"geçit\s*hakkı|gecit\s*hakki", "geçit hakkı"),
    ("zilyetlik", r"zilyetlik", "zilyetlik"),
    # Miras
    ("mirascilik", r"mirasçılık\s*belge|mirascilik\s*belge|veraset", "mirasçılık belgesi"),
    ("vasiyet_iptal", r"vasiyetnamenin\s*iptali|vasiyet.{0,12}iptal", "vasiyetnamenin iptali"),
    ("tenkis", r"tenkis", "tenkis"),
    ("miras_paylasim", r"mirasın\s*paylaş|mirasin\s*paylas|miras\s*ortaklığ", "mirasın paylaşılması"),
    ("muris_muvazaa", r"muris\s*muvazaa", "muris muvazaası"),
    # İdare / vergi
    ("iptal", r"iptal\s*davası|işlemin iptali|islemin iptali", "iptal"),
    ("tam_yargi", r"tam\s*yargı|tam\s*yargi", "tam yargı"),
    ("yd", r"yürütmenin durdurulması|yurutmenin durdurulmasi", "yürütmenin durdurulması"),
    ("disiplin", r"disiplin\s*(ceza|islem)", "disiplin işlemi"),
    ("atama", r"(?<!atama uygunluk )atama\s*(işlem|karar)|görevden\s*alma|gorevden\s*alma", "atama / görevden alma"),
    ("imar", r"\bimar\b|ruhsat", "imar / ruhsat"),
    ("idari_ceza", r"idari\s*para\s*ceza", "idari para cezası"),
    ("tarhiyat", r"vergi\s*tarhiyat|vergi\s*ziya|özel\s*usulsüzlük|ozel\s*usulsuzluk", "vergi tarhiyat / ceza"),
    ("vergi_iade", r"vergi\s*iade", "vergi iadesi"),
    # Fikri / banka / sigorta / dernek
    ("marka", r"marka\s*(tecavüz|ihlal)|patent|faydalı\s*model|telif|tasarım\s*tecavüz", "fikri / sınai hak"),
    ("kredi", r"kredi\s*kart|ihtiyaç\s*kredi|tuketici\s*kredi", "kredi / kart"),
    ("sigorta", r"sigorta\s*tazmin|kasko|trafik\s*sigorta|poliçe|police", "sigorta"),
    ("uyelik", r"üyelikten\s*çıkar|uyelikten\s*cikar|dernek.{0,16}üye", "üyelik / dernek"),
)

LABOR_CLAIMS = {
    "ucret", "fazla", "ubgt", "hafta", "izin", "kidem", "ihbar",
    "ise_iade", "bos_sure", "baslatmama", "kotu_niyet", "ayrimcilik",
    "is_kazasi", "hizmet_tespit", "sendika", "isveren_alacak",
}
FAMILY_CLAIMS = {
    "tmk166", "tmk164", "anlasmali", "nafaka", "tedbir_nafaka", "istirak",
    "yoksulluk", "nafaka_artirim", "nafaka_azalt", "nafaka_kaldir",
    "maddi_tz", "manevi_tz", "velayet", "velayet_degis", "kisisel_iliski",
    "mal_rejimi", "katilma", "deger_artis", "ziynet", "aile_konutu", "babalik",
}
TRACK_CLAIMS = {c for c, _, _ in CLAIM_SPECS}
ISE_IADE_FAMILY = {"ise_iade", "bos_sure", "baslatmama"}
FESHE_BAGLI = {"kidem", "ihbar", "izin"}

TRACKS = {
    "is": {
        "label": "iş ve çalışma hukuku",
        "ptype": "İş Davası",
        "court_hint": r"iş mahkeme",
        "kind": "is",
        "pat": (
            r"isveren|işveren|isci|işçi|kidem|kıdem|ihbar tazmin|fazla mesai|"
            r"ise iade|işe iade|bordro|4857|is sozles|iş sözleş"
        ),
        "procedure": ("arabuluculuk",),
        "required": (
            ("ise_giris", "İşe giriş tarihi"),
            ("isten_cikis", "Fesih / çıkış tarihi"),
            ("ucret", "Ücret"),
            ("alacak", "Alacak kalemleri"),
            ("arabuluculuk", "Arabuluculuk"),
        ),
    },
    "bosanma": {
        "label": "aile hukuku / boşanma",
        "ptype": "Boşanma Davası",
        "court_hint": r"aile mahkeme",
        "kind": "bosanma",
        "pat": r"bosan|boşan|evlilik|velayet|nafaka|ziynet|sadakat|aldat",
        "procedure": (),
        "required": (
            ("evlilik", "Evlilik bilgisi"),
            ("bosanma_sebebi", "Boşanma sebebi"),
        ),
    },
    "kira": {
        "label": "kira hukuku",
        "ptype": "Kira / Tahliye",
        "court_hint": r"sulh hukuk|kira",
        "kind": "kira",
        "pat": r"kiraci|kiracı|kiralayan|kira sozles|tahliye|depozito|kiralanan",
        "procedure": ("ihtar",),
        "required": (
            ("sozlesme", "Kira sözleşmesi"),
            ("kira_bedel", "Kira bedeli"),
            ("tasinmaz", "Taşınmaz"),
        ),
    },
    "tuketici": {
        "label": "tüketici hukuku",
        "ptype": "Tüketici Hukuku",
        "court_hint": r"tüketici mahkeme|tuketici mahkeme",
        "kind": "tuketici",
        "pat": r"tuketici|tüketici|ayipli|ayıplı|6502|mesafeli sozles|devre tatil",
        "procedure": ("arabuluculuk", "hakem"),
        "required": (("urun", "Ürün / hizmet"), ("ayip", "Ayıp")),
    },
    "alacak": {
        "label": "borçlar hukuku / alacak",
        "ptype": "Alacak Davası",
        "court_hint": r"asliye hukuk",
        "kind": "alacak",
        "pat": r"alacak davas|temerrut|temerrüt|sebepsiz zengin|sozlesmeden don|tbk",
        "procedure": ("ihtar",),
        "required": (("olaylar", "Borç ilişkisi"),),
    },
    "tazminat": {
        "label": "tazminat / haksız fiil",
        "ptype": "Tazminat Davası",
        "court_hint": r"asliye hukuk",
        "kind": "tazminat",
        "pat": r"haksiz fiil|trafik kaza|maddi tazminat|manevi tazminat",
        "procedure": (),
        "required": (("olaylar", "Olay ve kusur"),),
    },
    "icra": {
        "label": "icra hukuku",
        "ptype": "İcra Hukuku",
        "court_hint": r"icra hukuk",
        "kind": "icra",
        "pat": r"itirazın iptali|menfi tespit|istirdat|odeme emri|icra takip",
        "procedure": ("takip",),
        "required": (("takip", "Takip konusu"),),
    },
    "idare": {
        "label": "idare hukuku",
        "ptype": "İdare Hukuku",
        "court_hint": r"idare mahkeme|vergi mahkeme|danıştay",
        "kind": "idare",
        "pat": r"idari islem|iyuk|2577|iptal dav|tam yargi|7315|atama uygunluk",
        "procedure": ("sure",),
        "required": (("islem", "Dava konusu işlem"),),
    },
    "vergi": {
        "label": "vergi uyuşmazlığı",
        "ptype": "İdare Hukuku",
        "court_hint": r"vergi mahkeme",
        "kind": "idare",
        "pat": r"vergi tarhiyat|vergi ziya|ozel usulsuzluk|vergi iade|vergi ceza",
        "procedure": ("idari_basvuru", "sure"),
        "required": (("islem", "Vergi işlemi"),),
    },
    "ticaret": {
        "label": "ticaret hukuku",
        "ptype": "Alacak Davası",
        "court_hint": r"asliye ticaret|ticaret mahkeme",
        "kind": "alacak",
        "pat": r"ticari alacak|cari hesap|haksiz rekabet|genel kurul iptal|ttk|cek senet",
        "procedure": ("arabuluculuk",),
        "required": (("olaylar", "Ticari ilişki"),),
    },
    "tapu": {
        "label": "taşınmaz / eşya hukuku",
        "ptype": "Diğer",
        "court_hint": r"asliye hukuk|kadastro",
        "kind": "diger",
        "pat": r"tapu iptal|ecrimisil|elatman|ortakligin gider|muvazaa|zilyetlik|gecit hakki",
        "procedure": (),
        "required": (("tasinmaz", "Taşınmaz"),),
    },
    "miras": {
        "label": "miras hukuku",
        "ptype": "Diğer",
        "court_hint": r"sulh hukuk|asliye hukuk",
        "kind": "diger",
        "pat": r"miras|vasiyet|tenkis|muris muvazaa|veraset|mirascilik belge",
        "procedure": (),
        "required": (("olaylar", "Miras ilişkisi"),),
    },
    "fikri": {
        "label": "fikri ve sınai mülkiyet",
        "ptype": "Diğer",
        "court_hint": r"fikri ve sınai|asliye hukuk",
        "kind": "diger",
        "pat": r"marka tecavuz|patent|telif|tasarim|faydali model",
        "procedure": (),
        "required": (("olaylar", "Hak ve ihlal"),),
    },
    "sigorta": {
        "label": "sigorta / banka işlemi",
        "ptype": "Tüketici Hukuku",
        "court_hint": r"tüketici|asliye ticaret|asliye hukuk",
        "kind": "tuketici",
        "pat": r"sigorta tazmin|kasko|trafik sigorta|police|kredi kart",
        "procedure": ("arabuluculuk",),
        "required": (("olaylar", "Poliçe / işlem"),),
    },
    "dernek": {
        "label": "dernek / vakıf / tüzel kişi",
        "ptype": "Diğer",
        "court_hint": r"asliye hukuk",
        "kind": "diger",
        "pat": r"dernek|vakif|uyelikten cikar|genel kurul uye",
        "procedure": (),
        "required": (("olaylar", "Tüzel kişi işlemi"),),
    },
    "ceza": {
        "label": "ceza hukuku",
        "ptype": "Ceza Hukuku",
        "court_hint": r"ceza mahkeme|cumhuriyet",
        "kind": "ceza",
        "pat": r"katilan|sanik|supheli|kamu davasi|suc duyurusu",
        "procedure": (),
        "required": (("olaylar", "Olay anlatımı"),),
    },
}

STATUTE_FOR_CLAIM = (
    ("ise_iade", r"4857.{0,48}m\.?\s*1[81]|4857.{0,48}m\.?\s*20|4857.{0,48}m\.?\s*21"),
    ("kidem", r"1475.{0,24}m\.?\s*14"),
    ("ihbar", r"4857.{0,24}m\.?\s*17"),
    ("fazla", r"4857.{0,24}m\.?\s*41"),
    ("ubgt", r"4857.{0,24}m\.?\s*47"),
    ("hafta", r"4857.{0,24}m\.?\s*46"),
    ("izin", r"4857.{0,24}m\.?\s*5[39]"),
    ("ucret", r"4857.{0,24}m\.?\s*3[24]"),
    ("tmk166", r"TMK.{0,16}166|4721.{0,16}166"),
    ("tmk164", r"TMK.{0,16}164|4721.{0,16}164"),
    ("yd", r"İYUK.{0,16}27|2577.{0,16}27"),
    ("iptal", r"İYUK.{0,16}2|2577.{0,16}2"),
    ("ayipli_mal", r"6502|TKHK"),
    ("kira_alacak", r"TBK.{0,16}3(13|14|15)|6098.{0,16}3(13|14|15)"),
    ("tahliye", r"TBK.{0,16}3(15|50|52)|6098.{0,16}3(15|50|52)|6570"),
    ("itiraz_iptal", r"İİK.{0,16}67|2004.{0,16}67"),
)

CITE_FOR_CLAIM = (
    ("ise_iade", r"işe iade|feshin geçersiz|geçerli sebep|geçersiz fesih"),
    ("kidem", r"kıdem tazmin"),
    ("ihbar", r"ihbar tazmin"),
    ("fazla", r"fazla (çalış|mesai)"),
    ("bos_sure", r"boşta geçen"),
    ("baslatmama", r"işe başlatmama"),
    ("ziynet", r"ziynet"),
    ("tmk164", r"terk nedeniyle|TMK.{0,12}164"),
    ("tmk166", r"temelinden sars|TMK.{0,12}166"),
    ("tahliye", r"tahliye"),
    ("ayipli_mal", r"ayıplı mal|ayıplı"),
)

CLAIM_EVIDENCE = (
    ("ise_iade", r"(?i)fesih|işe iade", r"(?i)fesih bildir|arabuluculuk|sgk|sözleşme", "İşe iade"),
    ("ucret", r"(?i)ücret öden|ücret alaca", r"(?i)bordro|banka|sgk|dekont", "Ücret"),
    ("fazla", r"(?i)fazla (çalış|mesai)", r"(?i)puantaj|pdks|tanık|mesai", "Fazla çalışma"),
    ("kidem", r"(?i)kıdem tazmin", r"(?i)sgk|fesih|bordro", "Kıdem"),
    ("ziynet", r"(?i)ziynet|altın|bilezik", r"(?i)fotoğraf|fatura|kuyumcu|tanık", "Ziynet"),
    ("tmk166", r"(?i)şiddet|aldat|hakaret|sadakat", r"(?i)mesaj|tanık|rapor|6284", "Boşanma vakıası"),
    ("kira_alacak", r"(?i)kira öden|kira alaca", r"(?i)sözleşme|dekont|ihtar|hesap", "Kira alacağı"),
    ("tahliye", r"(?i)tahliye", r"(?i)ihtar|sözleşme|tapu|ödeme", "Tahliye"),
    ("ayipli_mal", r"(?i)ayıp", r"(?i)fatura|garanti|servis|tespit|fotoğraf", "Ayıp"),
    ("iptal", r"(?i)idari işlem|iptal", r"(?i)işlem|tebliğ|dilekçe|savunma", "İdari işlem"),
    ("tapu_iptal", r"(?i)tapu|muvazaa", r"(?i)tapu|banka|tanık|sözleşme", "Tapu / muvazaa"),
    ("sigorta", r"(?i)hasar|poliçe|kasko", r"(?i)poliçe|eksper|tutanak|fatura", "Sigorta"),
)

EVIDENCE_ALIASES = (
    ("sgk", r"sgk\s*(hizmet|kayıt|belge|döküm)"),
    ("bordro", r"bordro|ücret pusula"),
    ("arabuluculuk", r"arabuluculuk\s*(son\s*)?tutanak|son tutanak"),
    ("sozlesme", r"(iş|kira|satış)?\s*sözleşme"),
    ("tapu", r"tapu\s*(kayıt|sened)"),
)

QUESTION_PRIORITY = (
    ("tur", "Davanın türünü değiştirebilecek bilgi"),
    ("talep", "Talebi değiştirecek bilgi"),
    ("sure", "Süreyi etkileyen bilgi"),
    ("yetki", "Yetki / görevi etkileyen bilgi"),
    ("tutar", "Tutarı etkileyen bilgi"),
    ("delil", "Delili etkileyen bilgi"),
)

MISSING_MATRIX = {
    "is": (
        ("tur", "Fesih şekli (sözlü / yazılı) ve gerekçe"),
        ("sure", "Fesih tebliğ tarihi"),
        ("sure", "Arabuluculuk son tutanak tarihi"),
        ("talep", "İstenen işçilik kalemleri"),
        ("tutar", "Aylık ücret (net/brüt ayrımı)"),
        ("delil", "SGK / bordro / banka"),
    ),
    "ise_iade": (
        ("tur", "İşyerindeki işçi sayısı (30 işçi eşiği)"),
        ("sure", "Fesih tebliği + arabuluculuk + son tutanak tarihleri"),
        ("talep", "İşe iade ile birlikte boşta geçen süre / başlatmama isteniyor mu"),
    ),
    "bosanma": (
        ("tur", "Boşanma sebebi (166 / 164 / anlaşmalı)"),
        ("talep", "Velayet, nafaka, tazminat, ziynet isteniyor mu"),
        ("delil", "Kusur vakıasını destekleyen belge / tanık"),
    ),
    "kira": (
        ("tur", "Tahliye sebebi (temerrüt / ihtiyaç / inşa)"),
        ("sure", "İhtar tarihi"),
        ("tutar", "Aylık kira ve ödenmeyen dönem"),
        ("yetki", "Taşınmazın bulunduğu yer"),
    ),
    "idare": (
        ("sure", "İşlemin tebliğ / öğrenme tarihi"),
        ("yetki", "İşlemi tesis eden idare"),
        ("talep", "İptal / tam yargı / YD ayrımı"),
    ),
    "tuketici": (
        ("tutar", "Bedel ve ayıbın ortaya çıkış tarihi"),
        ("sure", "Ayıp bildirimi / hakem başvurusu"),
        ("delil", "Fatura / sipariş / ayıp tespiti"),
    ),
}

JOINDER_RULES = (
    (
        {"ise_iade"},
        {"kidem", "ihbar", "izin"},
        "İşe iade ile feshe bağlı kıdem / ihbar / izin aynı dilekçede karışmış olabilir. "
        "İşe başlatılmama sonrası bu kalemler için ayrı arabuluculuk gerekir.",
    ),
    (
        {"iptal"},
        {"kidem", "kira_alacak", "ziynet"},
        "İdari iptal ile özel hukuk alacağı aynı davada birleşmeyebilir.",
    ),
)

ROLE_WORDS = (
    ("isci", r"işçi|davacı işçi"),
    ("isveren", r"işveren|davalı şirket"),
    ("kiraci", r"kiracı"),
    ("kiralayan", r"kiraya veren|kiralayan"),
    ("es", r"eş|davacı eş"),
    ("mirasci", r"mirasçı"),
    ("mirasbirakan", r"miras bırakan|muris"),
    ("tuketici", r"tüketici"),
    ("satici", r"satıcı|sağlayıcı"),
)

PROMPT_LEAK = (
    r"\bprompt\b", r"\bAI\b", r"\bmodel\b", r"kullanıcı metn", r"formda yoksa",
    r"bilgi eksikse sor", r"görev:", r"aşağıdaki talimat", r"yazılım",
    r"otomatik olarak", r"veri alanı", r"4\.\s*BÖLÜM", r"Vekile Not",
    r"wikipedia", r"\[DOĞRULANACAK", r"Yargı MCP",
)
