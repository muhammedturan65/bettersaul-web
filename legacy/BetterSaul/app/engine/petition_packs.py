"""Türe özel dilekçe iskeleti — HMK m.119 sırası, yasal dayanak varsayılanları."""

PACKS: dict[str, dict] = {
    "Boşanma Davası": {
        "court": "… Aile Mahkemesi'ne",
        "konu": (
            "Türk Medeni Kanunu m. 166 uyarınca evlilik birliğinin temelinden sarsılması nedeniyle "
            "boşanma, fer'i sonuçlar (velayet, nafaka, tazminat, ziynet) talepli dava dilekçesidir."
        ),
        "statutes": [
            "TMK m. 166", "TMK m. 174", "TMK m. 175", "TMK m. 182", "TMK m. 185",
            "TMK m. 336", "TMK m. 182/2", "HMK m. 119", "HMK m. 389 vd.",
        ],
        "vakia": [
            "Davanın hukuki dayanağı",
            "Evlilik birliği ve müşterek çocuk",
            "Birliğin sarsılmasına yol açan vakıalar",
            "Hukuki nitelendirme",
            "Velayet ve kişisel ilişki",
            "Nafaka, tazminat ve ziynet",
        ],
        "evidence": [
            "Nüfus kayıt örneği ve evlilik cüzdanı fotokopisi",
            "Tanık beyanları (isim ve tebliğ adresi dilekçede)",
            "Varsa sağlık / adli rapor, uzaklaştırma kararı",
            "Gelir belgesi, bordro, SGK hizmet dökümü",
            "Ziynet / banka / tapu kayıtları",
        ],
        "vakia_delil": [
            "Nüfus kayıt örneği ve evlilik cüzdanı fotokopisi",
            "Nüfus kayıt örneği",
            "Tanık beyanları (isim ve tebliğ adresi dilekçede)",
            "Tanık beyanları, yazışma ve görüntüler",
            "Varsa sağlık / adli rapor, uzaklaştırma kararı",
            "Gelir belgesi, bordro, SGK hizmet dökümü",
            "Nüfus kaydı, okul/sağlık belgesi, tanık",
            "Ziynet / banka / tapu kayıtları",
        ],
        "requests": [
            "Tarafların TMK m. 166 uyarınca boşanmalarına",
            "Ortak çocuğun velayetinin müvekkile bırakılmasına",
            "Yargılama süresince davacı yararına aylık ........................ TL tedbir nafakasına",
            "Davacı yararına aylık ........................ TL yoksulluk nafakasına",
            "........................ TL maddi tazminata (TMK m. 174)",
            "........................ TL manevi tazminata (TMK m. 174)",
            "Ziynet ve kişisel eşyaların iadesine",
            "Yargılama giderleri ve vekâlet ücretinin davalıya yükletilmesine",
        ],
    },
    "İş Davası": {
        "court": "… İş Mahkemesi'ne",
        "konu": "İş ilişkisinden doğan ücret ve işçilik alacakları talepli dava dilekçesidir.",
        "statutes": [
            "4857 s. İş K. m. 32", "4857 s. İş K. m. 34",
            "HMK m. 107", "HMK m. 119",
            "7036 s. İş Mahkemeleri K. m. 3", "7036 s. İş Mahkemeleri K. m. 5",
        ],
        "vakia": [
            "İş ilişkisinin başlangıcı, görevi, ücreti ve işyeri.",
            "Ödenmeyen ücret dönemi (çalışma süresi ile karıştırılmaz).",
            "Varsa fesih tarihi ve şekli (yazılmamışsa uydurulmaz).",
            "Arabuluculuk başvurusu ve son tutanak (7036 m. 3).",
        ],
        "evidence": [
            "SGK hizmet dökümü ve işe giriş bildirgesi",
            "Bordro, banka hesap özeti, PUANTAJ",
            "Varsa fesih bildirimi / ibraname",
            "Arabuluculuk son tutanağı (7036 m. 3)",
            "Tanık beyanları (isim ve tebliğ adresi listede)",
        ],
        "requests": [
            "Ödenmeyen ücret alacağının HMK m. 107 uyarınca belirsiz alacak olarak "
            "4857 s. K. m. 34 uyarınca mevduata uygulanan en yüksek faiziyle tahsiline",
        ],
    },
    "Alacak Davası": {
        "court": "… Asliye Hukuk Mahkemesi'ne",
        "konu": "Sözleşme / haksız fiil / sebepsiz zenginleşmeye dayalı alacak ve fer'ileri talepli dava dilekçesidir.",
        "statutes": ["TBK m. 83", "TBK m. 117", "TBK m. 49", "TBK m. 77", "HMK m. 119", "HMK m. 107"],
        "vakia": [
            "Borç ilişkisinin kuruluşu (sözleşme / fatura / icap-kabul).",
            "Edimin ifa edilmemesi veya ayıplı ifa.",
            "Muacceliyet, ihtar ve temerrüt tarihi.",
            "Alacak tutarının hesabı ve dava değeri.",
        ],
        "evidence": ["Sözleşme / fatura / dekont", "İhtarname ve tebliğ belgesi", "Yazışmalar", "Tanık"],
        "requests": [
            "Asıl alacağın tahsiline",
            "Temerrüt faizine",
            "Yargılama gideri ve vekâlet ücretine",
        ],
    },
    "İcra Hukuku": {
        "court": "… İcra Hukuk Mahkemesi'ne",
        "konu": "İcra takibine ilişkin itirazın iptali / kaldırılması / şikâyet talepli dilekçedir.",
        "statutes": ["İİK m. 67", "İİK m. 68", "İİK m. 72", "İİK m. 16", "HMK m. 119", "TBK m. 117"],
        "vakia": [
            "Takip dosyası (icra dairesi, esas no) ve ödeme emri tebliği.",
            "Borcun dayanağı ve itirazın kapsamı.",
            "İtirazın haksızlığı / belgelere dayalı gerçek alacak.",
            "İnkâr tazminatı koşulları varsa ayrıca.",
        ],
        "evidence": ["İcra dosyası örneği", "Ödeme emri ve tebliğ", "Dayanak belgeler", "İtiraz dilekçesi"],
        "requests": [
            "İtirazın iptaline / kaldırılmasına",
            "Takiğin devamına",
            "Varsa icra inkâr tazminatına",
        ],
    },
    "İdare Hukuku": {
        "court": "… İdare Mahkemesi Başkanlığı'na",
        "konu": "İdari işlemin iptali talepli dilekçedir.",
        "statutes": ["İYUK m. 2", "İYUK m. 7", "2577 s. K."],
        "vakia": [
            "İptali istenen idari işlem, tarih ve tebliğ",
            "Başvuru, kadro ve müvekkilin hukuki durumu",
            "Sebep unsuru ve gerekçenin somutluğu",
            "Yetki, şekil, konu ve amaç yönünden hukuka aykırılık",
            "Varsa ceza olgusunun sebep unsurundaki yeri",
            "İdareye başvuru, yanıt ve süre (İYUK m. 7 / m. 11)",
            "Yürütmenin durdurulması koşulları (yalnızca talep varsa)",
        ],
        "evidence": ["İşlem evrakı ve tebliğ", "İdari başvuru evrakı"],
        "requests": [
            "İşlemin iptaline",
            "Yargılama giderine",
        ],
    },
    "Tazminat Davası": {
        "court": "… Asliye Hukuk Mahkemesi'ne",
        "konu": "Haksız fiil / sözleşmeye aykırılık nedeniyle maddi ve manevi tazminat talepli dava dilekçesidir.",
        "statutes": ["TBK m. 49", "TBK m. 50", "TBK m. 51", "TBK m. 56", "TBK m. 58", "HMK m. 119"],
        "vakia": [
            "Fiil, zarar, illiyet ve kusur olguları.",
            "Zararın kalemleri (tedavi, yoksun kalınan kazanç, değer kaybı).",
            "Manevi zararın somut gerekçesi.",
            "Varsa ceza soruşturması / kaza tutanağı.",
        ],
        "evidence": ["Kaza / olay tutanağı", "Sağlık raporları", "Fatura ve gelir belgesi", "Tanık"],
        "requests": ["Maddi tazminata", "Manevi tazminata", "Faiz ve yargılama giderine"],
    },
    "Ceza Hukuku": {
        "court": "… Ağır Ceza / Asliye Ceza Mahkemesi'ne",
        "konu": "Katılan sıfatıyla müdahale, kamu davasına katılma ve tazminat / tedbir talepli dilekçedir.",
        "statutes": ["CMK m. 237", "CMK m. 238", "CMK m. 141", "TCK ilgili maddeler", "HMK m. 119 (hukuk fer'ileri)"],
        "vakia": [
            "Suç tarihi, yeri ve fail.",
            "Olayın oluş şekli ve zarar.",
            "Delil durumu (beyan, görüntü, rapor).",
            "Katılma ve talep edilen fer'iler.",
        ],
        "evidence": ["Şikâyet / ihbar", "Adli rapor", "Görüntü ve tanık", "Soruşturma evrakı"],
        "requests": ["Kamu davasına katılmaya", "Cezalandırmaya", "Tazminat / tedbire"],
    },
    "Kira / Tahliye": {
        "court": "… Sulh Hukuk Mahkemesi'ne",
        "konu": "Kira ilişkisinden kaynaklanan tahliye, alacak ve temerrüt talepli dava dilekçesidir.",
        "statutes": ["TBK m. 299", "TBK m. 315", "TBK m. 350", "TBK m. 352", "6098 s. K.", "HMK m. 119"],
        "vakia": [
            "Kira sözleşmesi, taşınmaz ve bedel.",
            "Temerrüt / ihtiyaç / taahhüt olgusu.",
            "İhtar ve süreler.",
            "Birikmiş kira / aidat hesabı.",
        ],
        "evidence": ["Kira sözleşmesi", "İhtarname ve tebliğ", "Ödeme dekontları", "Tahliye taahhüdü"],
        "requests": ["Tahliyeye", "Birikmiş kira ve fer'ilerine", "Yargılama giderine"],
    },
    "Tüketici Hukuku": {
        "court": "… Tüketici Mahkemesi'ne",
        "konu": "Ayıplı mal/hizmet nedeniyle seçimlik haklar ve tazminat talepli dava dilekçesidir.",
        "statutes": ["6502 s. TKHK m. 8", "TKHK m. 11", "TKHK m. 73", "TBK m. 219 vd.", "HMK m. 119"],
        "vakia": [
            "Tüketici işlemi (fatura, sipariş, teslim).",
            "Ayıbın ortaya çıkışı ve satıcıya bildirim.",
            "Seçimlik hak (iade, indirim, onarım, değişim).",
            "Varsa hakem heyeti kararı.",
        ],
        "evidence": ["Fatura / sipariş", "Ayıp bildirimi", "Ekspertiz / servis raporu", "Hakem kararı"],
        "requests": ["Seçimlik hakkın kabulüne", "Bedel iadesi / tazminata", "Yargılama giderine"],
    },
    "Diğer": {
        "court": "… Mahkemesi'ne",
        "konu": "Aşağıda açıklanan vakıalara dayalı talep dilekçesidir.",
        "statutes": ["HMK m. 119", "HMK m. 114", "TMK / TBK ilgili maddeler"],
        "vakia": [
            "Uyuşmazlığın konusu ve taraflar arası ilişki.",
            "Kronolojik vakıalar.",
            "Hukuki nitelendirme ve zarar / talep.",
        ],
        "evidence": ["Dayanak belgeler", "Yazışmalar", "Tanık"],
        "requests": ["Taleplerin kabulüne", "Yargılama gideri ve vekâlet ücretine"],
    },
}


def pack_for(petition_type: str) -> dict:
    return PACKS.get((petition_type or "").strip()) or PACKS["Diğer"]
