"""Mahkeme dilekçe şablonu — T.C., DAVA DİLEKÇESİ, numaralı vakıa + Delil/dayanak/sonuç."""
from __future__ import annotations

import re

_ROMAN = ("I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII")

KINDS = {
    "idare": {
        "mahkeme": "ANKARA NÖBETÇİ İDARE MAHKEMESİ'NE",
        "iptal": True,
        "sections": (
            ("ÖNCELİKLİ TALEP: ADLİ YARDIM", "adli"),
            ("DAVANIN KONUSU: DAVA KONUSU İŞLEMİN TESPİTİ", ""),
            ("MÜVEKKİL HAKKINDAKİ CEZA DOSYASININ HUKUKİ NİTELİĞİ", "ceza"),
            ("ŞEKİL UNSURU YÖNÜNDEN HUKUKA AYKIRILIK: GEREKÇESİZLİK", ""),
            ("SEBEP UNSURU YÖNÜNDEN HUKUKA AYKIRILIK", ""),
            ("KANUN ÇERÇEVESİNDE TAKDİR YETKİSİNİN SINIRI", ""),
            ("MASUMİYET KARİNESİ VE KAMU HİZMETİNE GİRME HAKKI", ""),
            ("ÖLÇÜLÜLÜK İLKESİ", ""),
            ("KONU VE MAKSAT UNSURLARI YÖNÜNDEN HUKUKA AYKIRILIK", ""),
            ("YÜRÜTMENİN DURDURULMASI TALEBİ", "yd"),
        ),
        "anayasa": (
            "m. 2 (hukuk devleti), m. 10 (eşitlik), m. 13 (ölçülülük), "
            "m. 20 (özel hayatın korunması), m. 36 (hak arama hürriyeti), "
            "m. 38/4 (masumiyet karinesi), m. 40 (etkili başvuru), "
            "m. 70 (kamu hizmetine girme hakkı), m. 125 (idarenin yargısal denetimi)"
        ),
        "kanun": (
            "2577 sayılı İYUK m. 2/1-a (iptal davası), m. 3 (dilekçede bulunacak hususlar), "
            "m. 7 (dava açma süresi), m. 27 (yürütmenin durdurulması), m. 31 (HMK yolları)"
        ),
        "kanun_7315": (
            "2577 sayılı İYUK m. 2/1-a (iptal davası), m. 27 (yürütmenin durdurulması), m. 31 (HMK yolları); "
            "7315 sayılı Güvenlik Soruşturması ve Arşiv Araştırması Kanunu "
            "m. 3 (soruşturma ve araştırma kapsamı), m. 4 (soruşturmanın yapılması), "
            "m. 5 (değerlendirme komisyonu), m. 7 (yasaklar), m. 9 (yürürlükten kaldırma), m. 10 (yürürlük); "
            "5271 sayılı CMK m. 231 (hükmün açıklanmasının geri bırakılması); "
            "6100 sayılı HMK m. 334 vd. (adli yardım); 657 sayılı DMK (memuriyet)"
        ),
        "ictihat_7315": (
            "AYM, E. 2021/60, K. 2024/200, 04/12/2024 (RG: 26/03/2025 – 32853) — "
            "7315 sayılı Kanun kapsamında güvencelerin belirlenmesi; § 225",
            "AYM, İhsan KILIÇ, B. No: 2019/38905, 02/10/2024 (RG: 06/03/2025 – 32833) — "
            "HAGB + kasten yaralama + emniyet teşkilatı istihdam sürecinde masumiyet karinesi ihlali",
            "AYM (GK), İdris ERTAŞ, B. No: 2018/21949, 20/05/2021 (RG: 10/09/2021 – 31594) — "
            "kamu görevine atanmamada soyut gerekçe ve belgeye erişim engelinin ihlal oluşturması",
            "AYM, Turgut DUMAN, B. No: 2014/15365, 29/05/2019 — "
            "güvenlik soruşturmasına esas alınan kişisel verinin hukuka aykırı kullanımı ve masumiyet karinesi ihlali",
            "Danıştay 2. Daire, E. 2025/2199, K. 2026/367, 04/02/2026 — "
            "kesinleşmemiş ceza kararının esas alınması, masumiyet karinesi, birlikte değerlendirme zorunluluğu",
        ),
    },
    "bosanma": {
        "mahkeme": "… AİLE MAHKEMESİ'NE",
        "iptal": False,
        "sections": (
            ("ÖNCELİKLİ TALEP: ADLİ YARDIM", "adli"),
            ("Evliliğin kuruluşu (tarih, evlenme yeri, evlilik cüzdanı)", ""),
            ("Ortak çocuklar varsa kimlik ve yaşları", "cocuk"),
            ("Birliğin sarsılmasına yol açan somut olaylar (tarih, yer, tanık)", ""),
            ("Kusur olguları ve davalının tutumu", ""),
            ("Ayrılık, terk, şiddet veya koruyucu tedbir varsa ayrı vakıa", ""),
            ("Tarafların gelir-gider durumu ve nafaka ihtiyacı", ""),
            ("Velayet ve kişisel ilişki için çocuğun üstün yararı", "cocuk"),
            ("Ziynet, ev eşyası ve varsa mal rejimi tasfiyesi", "ziynet"),
            ("İçtihat ve mevzuatın somut olaya uygulanması", ""),
            ("İHTİYATİ TEDBİR", "tedbir"),
        ),
        "anayasa": "m. 10 (kanun önünde eşitlik), m. 36 (hak arama hürriyeti), m. 41 (ailenin korunması)",
        "kanun": "4721 sayılı TMK m. 166/1 (evlilik birliğinin temelinden sarsılması); 6100 sayılı HMK",
    },
    "is": {
        "mahkeme": "… İŞ MAHKEMESİ'NE",
        "iptal": False,
        "sections": (
            ("ÖNCELİKLİ TALEP: ADLİ YARDIM", "adli"),
            ("İŞ İLİŞKİSİ VE ÜCRET", ""),
            ("FESHİN GEÇERSİZLİĞİ VE İŞE İADE", "ise_iade"),
            ("ÖDENMEYEN İŞÇİLİK ALACAKLARI", ""),
            ("KIDEM VE İHBAR TAZMİNATI", "kidem"),
            ("FAZLA ÇALIŞMA VE TATİL ÜCRETLERİ", "fazla"),
            ("ARABULUCULUK DAVA ŞARTI", "arabuluculuk"),
        ),
        "anayasa": "m. 36 (hak arama hürriyeti), m. 49 (çalışma hakkı ve ödevi)",
        "kanun": (
            "4857 sayılı İş Kanunu m. 32 (ücret), m. 34 (ücretin gününde ödenmemesi); "
            "7036 sayılı İş Mahkemeleri Kanunu m. 3 (arabuluculuk), m. 5 (görev)"
        ),
    },
    "icra": {
        "mahkeme": "… İCRA HUKUK MAHKEMESİ'NE",
        "iptal": False,
        "sections": (
            ("ÖNCELİKLİ TALEP: ADLİ YARDIM", "adli"),
            ("TAKİBİN KONUSU VE DAYANAĞI", ""),
            ("İTİRAZIN İPTALİ / ŞİKÂYET NEDENLERİ", ""),
            ("İNKÂR TAZMİNATI VE FER'İLER", ""),
            ("İHTİYATİ HACİZ", "haciz"),
        ),
        "anayasa": "m. 36 (hak arama hürriyeti)",
        "kanun": "2004 sayılı İİK (takip ve şikâyet hükümleri); 6100 sayılı HMK (yargılama usulü)",
    },
    "tuketici": {
        "mahkeme": "… TÜKETİCİ MAHKEMESİ'NE",
        "iptal": False,
        "sections": (
            ("ÖNCELİKLİ TALEP: ADLİ YARDIM", "adli"),
            ("SÖZLEŞME VE TESLİM", ""),
            ("AYIP / AYKINLIK VE İHBAR", ""),
            ("TÜKETİCİNİN SEÇİMLİK HAKLARI", ""),
        ),
        "anayasa": "m. 36 (hak arama hürriyeti), m. 172 (tüketicilerin korunması)",
        "kanun": "6502 sayılı TKHK (ayıp ve seçimlik haklar); 6100 sayılı HMK (yargılama usulü)",
    },
    "kira": {
        "mahkeme": "… SULH HUKUK MAHKEMESİ'NE",
        "iptal": False,
        "sections": (
            ("ÖNCELİKLİ TALEP: ADLİ YARDIM", "adli"),
            ("KİRA SÖZLEŞMESİ VE TARAFLAR", ""),
            ("TEMERRÜT, İHTAR VE ÖDEME", ""),
            ("TAHLİYE VE FER'İ ALACAKLAR", ""),
        ),
        "anayasa": "m. 35 (mülkiyet hakkı), m. 36 (hak arama hürriyeti)",
        "kanun": "6098 sayılı TBK kira hükümleri (temerrüt / tahliye); 6100 sayılı HMK (yargılama usulü)",
    },
    "tazminat": {
        "mahkeme": "… ASLİYE HUKUK MAHKEMESİ'NE",
        "iptal": False,
        "sections": (
            ("ÖNCELİKLİ TALEP: ADLİ YARDIM", "adli"),
            ("OLAY VE KUSUR", ""),
            ("ZARAR VE İLLİYET", ""),
            ("İHTİYATİ TEDBİR", "tedbir"),
        ),
        "anayasa": "m. 36 (hak arama hürriyeti)",
        "kanun": "6098 sayılı TBK (haksız fiil ve tazminat); 6100 sayılı HMK (yargılama usulü)",
    },
    "ceza": {
        "mahkeme": "… CUMHURİYET BAŞSAVCILIĞI'NA / … CEZA MAHKEMESİ'NE",
        "iptal": False,
        "sections": (
            ("ÖNCELİKLİ TALEP: ADLİ YARDIM", "adli"),
            ("OLAYIN ANLATIMI", ""),
            ("SUÇUN UNSURLARI VE DELİL", ""),
        ),
        "anayasa": "m. 36 (hak arama hürriyeti), m. 38 (suç ve cezalara ilişkin esaslar)",
        "kanun": "5237 sayılı TCK (suçun unsurları); 5271 sayılı CMK (soruşturma ve kovuşturma usulü)",
    },
    "alacak": {
        "mahkeme": "… ASLİYE HUKUK MAHKEMESİ'NE",
        "iptal": False,
        "sections": (
            ("ÖNCELİKLİ TALEP: ADLİ YARDIM", "adli"),
            ("BORÇ İLİŞKİSİ", ""),
            ("TEMERRÜT VE ALACAK", ""),
        ),
        "anayasa": "m. 36 (hak arama hürriyeti)",
        "kanun": "6098 sayılı TBK (borç ve temerrüt); 6100 sayılı HMK (yargılama usulü)",
    },
    "diger": {
        "mahkeme": "… MAHKEMESİ'NE",
        "iptal": False,
        "sections": (
            ("ÖNCELİKLİ TALEP: ADLİ YARDIM", "adli"),
            ("VAKIA VE TESPİT", ""),
            ("HUKUKİ NİTELENDİRME", ""),
        ),
        "anayasa": "m. 36 (hak arama hürriyeti)",
        "kanun": "6100 sayılı HMK (yargılama usulü)",
    },
    "tapu": {
        "mahkeme": "… ASLİYE HUKUK MAHKEMESİ'NE",
        "iptal": False,
        "sections": (
            ("ÖNCELİKLİ TALEP: ADLİ YARDIM", "adli"),
            ("TAPU KAYDI VE TASARRUF", ""),
            ("GEÇERSİZLİK / MUVAZAA NEDENLERİ", ""),
            ("TESCİL VE FER'İ TALEPLER", ""),
        ),
        "anayasa": "m. 35 (mülkiyet hakkı), m. 36 (hak arama hürriyeti)",
        "kanun": "4721 sayılı TMK (mülkiyet ve tapu); 6100 sayılı HMK (yargılama usulü)",
    },
    "miras": {
        "mahkeme": "… SULH HUKUK MAHKEMESİ'NE",
        "iptal": False,
        "sections": (
            ("ÖNCELİKLİ TALEP: ADLİ YARDIM", "adli"),
            ("MİRASÇILIK VE TEREKE", ""),
            ("TESPİT / TENKİS / İPTAL", ""),
        ),
        "anayasa": "m. 35 (mülkiyet hakkı), m. 36 (hak arama hürriyeti)",
        "kanun": "4721 sayılı TMK (miras); 6100 sayılı HMK (yargılama usulü)",
    },
}


def resolve_kind(petition_type: str) -> str:
    p = (petition_type or "").replace("İ", "i").replace("I", "i").replace("ı", "i").lower()
    if "idar" in p or "vergi" in p or "danistay" in p:
        return "idare"
    if "boşan" in p or "bosan" in p or "aile" in p:
        return "bosanma"
    if "iş" in p or re.search(r"\bis\b", p) or "isci" in p or "işçi" in p:
        return "is"
    if "icra" in p:
        return "icra"
    if "tüketici" in p or "tuketici" in p or "sigorta" in p:
        return "tuketici"
    if "kira" in p or "tahliye" in p:
        return "kira"
    if "tazminat" in p:
        return "tazminat"
    if "ceza" in p:
        return "ceza"
    if "alacak" in p or "ticaret" in p:
        return "alacak"
    if "tapu" in p or "muvazaa" in p:
        return "tapu"
    if "miras" in p or "tereke" in p or "tenkis" in p:
        return "miras"
    return "diger"


def _keep(flag: str, flags: dict | None, blob: str) -> bool:
    flags = flags or {}
    if not flag:
        return True
    if flag == "adli":
        return bool(flags.get("adli"))
    if flag == "yd":
        return bool(flags.get("yd"))
    if flag == "tedbir":
        return bool(flags.get("tedbir"))
    if flag == "haciz":
        return bool(flags.get("haciz"))
    if flag == "ceza":
        return bool(re.search(r"(?i)HAGB|asliye ceza|kasten|hakaret|beraat", blob or ""))
    if flag == "cocuk":
        return bool(re.search(r"(?i)çocuk|velayet|iştirak", blob or ""))
    if flag == "ziynet":
        return bool(re.search(r"(?i)ziynet|altın", blob or ""))
    if flag == "arabuluculuk":
        return True
    if flag == "ise_iade":
        return bool(re.search(r"(?i)işe\s*iade|feshin geçersiz|geçerli sebep", blob or ""))
    if flag == "kidem":
        return bool(re.search(r"(?i)kıdem|ihbar tazmin", blob or ""))
    if flag == "fazla":
        return bool(re.search(r"(?i)fazla\s*(çalış|mesai)|hafta tatili|ubgt", blob or ""))
    return True


def outline(petition_type: str, flags: dict | None = None, blob: str = "") -> list[tuple[str, str]]:
    kind = resolve_kind(petition_type)
    spec = KINDS[kind]
    out: list[tuple[str, str]] = []
    i = 0
    for title, flag in spec["sections"]:
        if not _keep(flag, flags, blob):
            continue
        out.append((_ROMAN[i], title))
        i += 1
    return out


def sort_sections(
    sections: list[tuple[str, list[str]]],
    petition_type: str,
    flags: dict | None = None,
    blob: str = "",
) -> list[tuple[str, list[str]]]:
    order = [title for _, title in outline(petition_type, flags, blob)]
    by: dict[str, list[str]] = {}
    for title, paras in sections:
        by.setdefault(title, []).extend(paras)
    out: list[tuple[str, list[str]]] = []
    seen: set[str] = set()
    for title in order:
        if title in by:
            out.append((title, by[title]))
            seen.add(title)
    for title, paras in sections:
        if title not in seen:
            out.append((title, by.get(title, paras)))
            seen.add(title)
    return out


def render_roman(sections: list[tuple[str, list[str]]]) -> str:
    out: list[str] = []
    n = 1
    for title, paras in sections:
        body = " ".join(re.sub(r"\s+", " ", p or "").strip() for p in paras if (p or "").strip())
        head = (title or "").strip().rstrip(".")
        if re.search(r"(?im)^\s*Delil\s*[:：]", body):
            out.append(f"{n}- {head}.\n{body}")
        else:
            out.append(
                f"{n}- {head}.\n"
                f"{body or '[Somut vakıa — uydurma. Gövde: müvekkil.]'}\n"
                "Delil : [formdaki belge — uydurma]\n"
                "Hukuki dayanak : [yalnızca çekilen madde]\n"
                "Hukuki sonuç : [bu olgu, aşağıda yazılı istemlerin kabulünü haklı kılar.]"
            )
        n += 1
    return "\n\n".join(out)


def outline_text(petition_type: str, flags: dict | None = None, blob: str = "") -> str:
    lines = [f"{i + 1}- {title}" for i, (_rom, title) in enumerate(outline(petition_type, flags, blob))]
    return "\n".join(lines)


def combined_banner(flags: dict | None, petition_type: str = "") -> str:
    f = flags or {}
    kind = resolve_kind(petition_type)
    bits: list[str] = []
    if f.get("adli"):
        bits.append("ADLİ YARDIM TALEBİ")
    if f.get("ivedi"):
        bits.append("İVEDİ VE ÖNCELİKLİ İNCELEME")
    if f.get("yd"):
        bits.append("YÜRÜTMENİN DURDURULMASI")
    if f.get("tedbir"):
        bits.append("İHTİYATİ TEDBİR")
    if f.get("haciz"):
        bits.append("İHTİYATİ HACİZ")
    if kind == "idare" and (f.get("yd") or f.get("adli") or f.get("ivedi")):
        if "İPTAL" not in " ".join(bits).upper():
            bits.append("İPTAL")
    if not bits:
        return ""
    if len(bits) == 1:
        return f"— {bits[0]} TALEPLİDİR —" if "TALEBİ" not in bits[0] else f"— ÖNCELİKLE {bits[0]}, TALEPLİDİR —"
    head, *rest = bits
    if f.get("adli"):
        return f"— ÖNCELİKLE {head}, AKABİNDE {' VE '.join(rest)} TALEPLİDİR —"
    return f"— {' VE '.join(bits)} TALEPLİDİR —"


def _filled(s: str) -> bool:
    t = re.sub(r"\s+", " ", (s or "")).strip()
    if not t or t in {".", "—", "-"}:
        return False
    if re.fullmatch(r"[\.…]{3,}", t):
        return False
    if re.fullmatch(r"\[.*?\]", t):
        return False
    return True


def client_block(name: str, tckn: str = "", address: str = "") -> str:
    ad = (name or "").strip()
    lines = ["DAVACI"]
    if _filled(ad):
        lines.extend(["", f"Ad Soyad : {ad}"])
    if _filled(tckn):
        lines.extend(["", f"T.C. Kimlik No : {tckn.strip()}"])
    if _filled(address):
        lines.extend(["", f"Tebligat adresi : {address.strip()}"])
    return "\n".join(lines)


def lawyer_block(lines: list[str] | str) -> str:
    if isinstance(lines, str):
        raw = [ln.strip() for ln in lines.splitlines() if ln.strip()]
    else:
        raw = [ln.strip() for ln in (lines or []) if (ln or "").strip()]
    raw = [ln for ln in raw if _filled(re.sub(r"(?i)^(adres|tel|e-posta)\s*[:：]\s*", "", ln))]
    name = raw[0] if raw else "Av."
    rest = "\n".join(raw[1:])
    out = ["VEKİLİ", "", name]
    if rest:
        out.extend(["", rest])
    return "\n".join(out)


def defendant_block(name: str, address: str = "", public: bool = False, tckn: str = "") -> str:
    ad = (name or "").strip()
    ad = re.sub(r"\s*\((?:7315|kapsamında|güvenlik soruştur).*$", "", ad, flags=re.I).strip()
    lines = ["DAVALI"]
    if _filled(ad):
        lines.extend(["", f"{'Unvan' if public else 'Ad Soyad'} : {ad}"])
    if _filled(tckn) and not public:
        lines.extend(["", f"T.C. Kimlik No : {tckn.strip()}"])
    if _filled(address):
        lines.extend(["", f"Tebligat adresi : {address.strip()}"])
    return "\n".join(lines)


def dayanak_block(anayasa: str, kanunlar: str, ictihat: list[str] | None = None) -> str:
    ay = (anayasa or "").strip() or "Anayasa ilgili maddeleri (yalnızca çekilen)"
    kn = (kanunlar or "").strip() or "İlgili kanun maddeleri (yalnızca çekilen)"
    cites = [c.strip() for c in (ictihat or []) if (c or "").strip()]
    lines = [f"Anayasa: {ay}", "", f"Kanunlar: {kn}", ""]
    if cites:
        lines.append("İçtihat:")
        lines.append("")
        for c in cites:
            lines.append(c)
            lines.append("")
    else:
        lines.append("Emsal içtihat (yalnızca resmî tarama): çekilen künye yoksa numara yazılmaz.")
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def kind_caption(petition_type: str = "") -> str:
    return {
        "idare": "İptal davası",
        "bosanma": "Boşanma davası",
        "is": "İşçilik alacakları davası",
        "icra": "İcra hukuku davası",
        "tuketici": "Tüketici davası",
        "kira": "Kira / tahliye davası",
        "tazminat": "Tazminat davası",
        "ceza": "Ceza yargılaması dilekçesi",
        "alacak": "Alacak davası",
        "tapu": "Tapu / tescil davası",
        "miras": "Miras davası",
        "diger": "Dava dilekçesi",
    }.get(resolve_kind(petition_type), "Dava dilekçesi")


def vakia_unit(n: int, title: str) -> str:
    head = (title or "").strip().rstrip(".")
    return (
        f"{n}- {head}.\n"
        "[Somut vakıa — uydurma. Gövde: müvekkil.]\n"
        "Delil : [formdaki belge — uydurma]\n"
        "Hukuki dayanak : [yalnızca çekilen madde]\n"
        "Hukuki sonuç : [bu olgu, aşağıda yazılı istemlerin kabulünü haklı kılar.]"
    )


def assemble(
    court: str,
    banner: str,
    davaci: str,
    vekil: str,
    davali: str,
    konu: str,
    acik: str,
    deliller: str,
    dayanak: str,
    sonuc: str,
    ekler: str,
    tarih: str,
    imza: str,
    sarti: str = "",
    kind_title: str = "",
) -> str:
    parts = ["T.C.", court.strip()]
    if banner.strip():
        parts.append(banner.strip())
    parts.append("DAVA DİLEKÇESİ")
    if (kind_title or "").strip():
        parts.append(kind_title.strip())
    parts.extend(
        [
            davaci.strip(),
            vekil.strip(),
            davali.strip(),
            f"KONU : {konu.strip()}" if not re.match(r"(?i)^KONU\b", konu.strip()) else konu.strip(),
        ]
    )
    if sarti.strip():
        parts.append(sarti.strip())
    parts.extend(
        [
            f"AÇIKLAMALAR :\n\n{acik.strip()}",
            f"HUKUKİ SEBEPLER :\n\n{dayanak.strip()}",
            f"DELİLLER :\n\n{deliller.strip()}",
            f"SONUÇ VE İSTEM :\n\n{sonuc.strip()}",
            f"{tarih.strip()}\n\n{imza.strip()}",
            f"EKLER :\n\n{ekler.strip()}",
        ]
    )
    return re.sub(r"\n{3,}", "\n\n", "\n\n\n".join(p for p in parts if p)).strip()


def guide(petition_type: str = "", flags: dict | None = None, blob: str = "") -> str:
    kind = resolve_kind(petition_type)
    spec = KINDS[kind]
    ol = outline_text(petition_type, flags, blob)
    usul = {
        "idare": (
            "İYUK m. 3: mahkeme, taraflar, konu, vakıa, hukuki sebepler, sonuç. "
            "İptalde yetki / şekil / sebep / konu / maksat sırasıyla yaz. AYM yalnızca çekildiyse."
        ),
        "is": (
            "HMK m. 119 + 7036 m. 3 arabuluculuk dava şartı. "
            "KONU, AÇIKLAMALAR ve SONUÇ aynı kalem kümesi; istenmeyen kıdem/ihbar/işe iade yazılmaz."
        ),
        "bosanma": "HMK m. 119; TMK 164 ile 166 karıştırılmaz. Fer'iler yalnızca formdaysa.",
        "icra": "HMK m. 119 + İİK; takip numarası yoksa uydurulmaz. İtirazın iptali İİK m. 67.",
        "tuketici": "HMK m. 119 + 6502 seçimlik haklar; fatura/teslim tarihi yoksa uydurulmaz.",
        "kira": "HMK m. 119 + TBK kira; ihtar ve temerrüt tarihleri formdan.",
        "tazminat": "HMK m. 119 + TBK haksız fiil; kusur-illiyet-zarar üçlüsü.",
        "ceza": "CMK; suç uydurulmaz. Şikâyet / katılma ayrımı korunur.",
        "alacak": "HMK m. 119 + TBK temerrüt; vade ve ihtar formdan.",
        "tapu": "HMK m. 119; tapu ada/parsel yoksa uydurulmaz.",
        "miras": "HMK m. 119 + TMK miras; veraset belgesi yoksa uydurulmaz.",
        "diger": "HMK m. 119 unsurları: mahkeme, taraf, konu, vakıa, delil, hukuki sebep, sonuç.",
    }.get(kind, "HMK m. 119 unsurları eksiksiz yazılır; künye uydurulmaz.")
    return (
        f"Tür: {kind}\n"
        "Yazı formatı (örnek dilekçe — bu sıra atlanmaz):\n"
        "T.C. / MAHKEME'NE / birleşik baner (varsa) / DAVA DİLEKÇESİ / dava türü satırı / "
        "DAVACI (Ad Soyad / TCKN / Tebligat adresi) / VEKİLİ / DAVALI / KONU / "
        "AÇIKLAMALAR : her vakıa 1- 2- 3- başlık + müvekkil gövdesi + "
        "Delil : / Hukuki dayanak : / Hukuki sonuç : satırları / "
        "HUKUKİ SEBEPLER : (çekilen maddeler + taranan emsal) / "
        "DELİLLER : / SONUÇ VE İSTEM : / tarih / Davacı Vekili / EKLER :.\n"
        "Gövde: müvekkil. Başlık: DAVACI. Adli yardım varsa baner + vakıa + sonuç.\n"
        "Kitap adı, yazar, sistem talimatı dilekçeye yazılmaz.\n"
        f"Usul: {usul}\n"
        f"Mahkeme örneği: {spec['mahkeme']}\n"
        f"Vakıa iskeleti:\n{ol}\n"
        "Atıf: yalnızca taranan künye; Yargıtay/Danıştay adı + E. / K. / T. — o kararın özeti. "
        "Çekilmediyse numara yazılmaz.\n"
    )


def skeleton(petition_type: str = "", flags: dict | None = None) -> str:
    kind = resolve_kind(petition_type)
    spec = KINDS[kind]
    flags = flags or {"adli": True, "yd": kind == "idare", "ivedi": kind == "idare"}
    ol = outline(petition_type, flags, "HAGB çocuk ziynet")
    acik = [vakia_unit(i + 1, title) for i, (_rom, title) in enumerate(ol)]
    return assemble(
        spec["mahkeme"],
        combined_banner(flags, petition_type),
        client_block("[ad soyad]"),
        lawyer_block("Av. [ad soyad]"),
        defendant_block("[karşı taraf]"),
        "[Somut talep — uydurma.]",
        "\n\n".join(acik),
        "1. [formdaki belgeler]",
        dayanak_block(spec["anayasa"], spec["kanun"], []),
        "Yukarıda açıklanan ve resen nazara alınacak nedenlerle taleplerin kabulüne karar verilmesini vekâleten talep ederim.",
        "1. Vekâletname\n2. [belgeler]",
        "[tarih]",
        "Davacı Vekili\nAv. [ad soyad]",
        kind_title=kind_caption(petition_type),
    )
