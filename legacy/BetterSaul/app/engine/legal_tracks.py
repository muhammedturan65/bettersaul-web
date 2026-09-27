"""Vakıaya göre görev, dava şartı ve nitelendirme.

Kitap metni veya telifli eser değildir. 7036 s. K. m. 3 ve m. 5, 4857 s. K.,
HMK m. 119 özet kurallarıdır. GGUF modeli yeniden eğitilmez; motor bu kurallara uyar.
"""
from __future__ import annotations

import re
from datetime import date


def _blob(form: dict) -> str:
    parts = [
        str(form.get("caseSummary") or ""),
        str(form.get("extraInstructions") or ""),
        str(form.get("requests") or ""),
        str(form.get("parties") or ""),
        str(form.get("title") or ""),
        str(form.get("petitionType") or ""),
        str(form.get("userPrompt") or ""),
    ]
    return " ".join(parts)


def _fold(s: str) -> str:
    t = (s or "").replace("İ", "i").replace("I", "i").replace("ı", "i")
    return t.lower()


def _has(blob: str, pat: str) -> bool:
    return bool(re.search(pat, _fold(blob), re.I))


def detect_track(form: dict) -> str:
    blob = _blob(form)
    ptype = str(form.get("petitionType") or "")
    if "İdare" in ptype or _has(
        blob,
        r"idari islem|iyuk|2577|danistay|7315|guvenlik sorustur|"
        r"arsiv arastir|iptal dav|tam yargi|degerlendirme komisyon|"
        r"vergi mahkeme",
    ):
        return "idare"
    family = _has(blob, r"bosan|evlilik|velayet|yoksulluk|istirak nafaka|ziynet|sadakat")
    labor = _has(
        blob,
        r"(?<![a-z])(is\s*yeri|isyeri|isci|isveren)(?![a-z])|kidem|ihbar tazmin|fazla mesai|"
        r"is sozles|4857|is kanunu|(?<![a-z])maas(?![a-z])|ucret(imi|ini| alaca)|"
        r"odememi alamad|alamadigim|calistigim is|bordro|ise iade|"
        r"ulusal bayram|hafta tatili ucret",
    )
    if "Boşanma" in ptype or (family and not labor):
        return "bosanma"
    if labor and not family:
        return "is"
    if _has(blob, r"kira|tahliye|kiracı|kiralayan"):
        return "kira"
    if _has(blob, r"tüketici|ayıplı|garanti"):
        return "tuketici"
    if _has(blob, r"icra|ödeme emri|itirazın iptali"):
        return "icra"
    if _has(blob, r"katılan|sanık|şüpheli|kamu davası"):
        return "ceza"
    if _has(blob, r"haksız fiil|trafik kaza|darp|manevi zarar") and not labor:
        return "tazminat"
    if _has(blob, r"vergi tarhiyat|vergi ziya|vergi mahkeme"):
        return "idare"
    if _has(blob, r"tapu iptal|ecrimisil|elatman|muris muvazaa|mirasçılık belge|veraset"):
        return "diger"
    if _has(blob, r"ticari alacak|cari hesap|haksiz rekabet|asliye ticaret"):
        return "alacak"
    if _has(blob, r"marka tecavuz|patent|telif hak"):
        return "diger"
    if "İş" in ptype:
        return "is"
    if "Tazminat" in ptype:
        return "tazminat"
    if "Alacak" in ptype:
        return "alacak"
    return "diger"


def resolved_type(form: dict) -> str:
    track = detect_track(form)
    return {
        "bosanma": "Boşanma Davası",
        "is": "İş Davası",
        "alacak": "Alacak Davası",
        "icra": "İcra Hukuku",
        "idare": "İdare Hukuku",
        "tazminat": "Tazminat Davası",
        "ceza": "Ceza Hukuku",
        "kira": "Kira / Tahliye",
        "tuketici": "Tüketici Hukuku",
        "diger": str(form.get("petitionType") or "Diğer") or "Diğer",
    }[track]


def align_form(form: dict) -> dict:
    f = dict(form or {})
    track = detect_track(f)
    f["_track"] = track
    try:
        from bettersaul_mcp.motor.pipeline import classify

        f["_on_degerlendirme"] = classify(f)
    except Exception:
        f["_on_degerlendirme"] = {"track": track, "note": ""}
    f["petitionType"] = resolved_type(f)
    return f


def is_labor(form: dict) -> bool:
    return detect_track(form) == "is"


def is_work_accident(form: dict) -> bool:
    return _has(_blob(form), r"iş kazas|meslek hastal")


def needs_mediation(form: dict) -> bool:
    track = detect_track(form)
    if track == "is" and not is_work_accident(form):
        return True
    if track == "tuketici":
        return True
    return False


def wants_tazminat(form: dict) -> bool:
    if is_labor(form) and not is_work_accident(form):
        return False
    cv = form.get("claimValues")
    if isinstance(cv, str) and cv.strip():
        try:
            import json

            cv = json.loads(cv)
        except Exception:
            cv = {}
    if isinstance(cv, dict):
        if str(cv.get("maddi") or "").strip() or str(cv.get("manevi") or "").strip():
            return True
    return _has(_blob(form), r"maddi tazminat|manevi tazminat")


def court_override(form: dict) -> str:
    """Görev vakıaya göredir; kullanıcı mahkemesi türü şaşırsa düzeltilir."""
    raw = str(form.get("court") or "")
    track = detect_track(form)
    if track == "idare":
        if re.search(r"idare mahkeme|vergi mahkeme|danıştay", raw, re.I):
            return raw
        return "İdare Mahkemesi Başkanlığı'na"
    if track == "is":
        if re.search(r"iş mahkeme", raw, re.I):
            return raw
        return "İş Mahkemesi'ne"
    if track == "bosanma":
        if re.search(r"aile mahkeme", raw, re.I):
            return raw
        return ""
    return ""


def labor_wage_claim(form: dict) -> str:
    if not is_labor(form):
        return ""
    return (
        "Ödenmeyen ücret alacağının HMK m. 107 uyarınca belirsiz alacak olarak "
        "(miktar formda yoksa uydurulmaz; ıslah / artırma hakkı saklıdır) "
        "4857 sayılı Kanun m. 34 uyarınca mevduata uygulanan en yüksek faiziyle tahsiline"
    )


def labor_toxic(text: str) -> bool:
    return bool(
        re.search(
            r"TBK\s*m\.\s*4[89]|TBK\s*m\.\s*5[0-8]|4\.\s*(Hukuk|HD)|"
            r"haks[ıi]z\s*fiil|manevi tazminat|ziynet|evlilik birli|"
            r"TMK\s*m\.\s*16[46]|kaza\s*/\s*olay tutana",
            text or "",
            re.I,
        )
    )


def mediation_bits(form: dict) -> tuple[str, str]:
    blob = _blob(form)
    buro = re.search(
        r"(?:b[uü]ro|arabuluculuk)\s*(?:no|numara[sş][ıi]?)?\s*[:.]?\s*(\d[\d/\-]*)",
        blob,
        re.I,
    )
    tarih = re.search(
        r"son tutanak[^\d]{0,24}(\d{1,2}[./]\d{1,2}[./]\d{4})",
        blob,
        re.I,
    )
    return (buro.group(1) if buro else "", tarih.group(1) if tarih else "")


def mediation_header(form: dict) -> str:
    if is_work_accident(form):
        return (
            "İş kazası / meslek hastalığı tazminatı — 7036 m. 3/3 istisnası "
            "(arabuluculuk bu kalemde dava şartı değildir)."
        )
    buro, tarih = mediation_bits(form)
    bits = []
    if buro:
        bits.append(f"Büro No: {buro}")
    if tarih:
        bits.append(f"Son tutanak tarihi: {tarih}")
    if bits:
        return "Arabuluculuk (7036 m. 3) — " + " / ".join(bits)
    return (
        "Arabuluculuk (7036 m. 3) — büro numarası ve son tutanak tarihi formda "
        "bildirilmemiştir; tutanak aslı eklenir, numara uydurulmaz."
    )


def mediation_vakia(form: dict) -> tuple[str, str]:
    extra = _blob(form)
    if is_work_accident(form):
        return (
            "Arabuluculuk istisnası",
            "7036 sayılı Kanun m. 3/3 uyarınca iş kazası veya meslek hastalığından "
            "kaynaklanan maddi ve manevi tazminatta arabuluculuk dava şartı değildir.",
        )
    if re.search(r"arabulucu", extra, re.I):
        return (
            "Dava şartı — arabuluculuk",
            "7036 sayılı İş Mahkemeleri Kanunu m. 3 uyarınca arabuluculuğa başvurulmuştur. "
            "Anlaşmaya varılamadığına ilişkin son tutanak dilekçe ekinde sunulur; "
            "tutanak tarihi ve sayısı bildirilmemişse uydurulmaz.",
        )
    return (
        "Dava şartı — arabuluculuk",
        "7036 sayılı Kanun m. 3 uyarınca işçi alacağı davasında arabulucuya başvuru "
        "dava şartıdır. Bu dosya formda bildirilen işçilik kalemleriyle sınırlıdır. "
        "Son tutanak aslı veya arabulucu "
        "onaylı örneği dilekçeye eklenir; eklenmezse HMK m. 115 uyarınca usulden red riski vardır. "
        "Tutanak tarihi formda yoksa uydurulmaz, tutanak sunulacaktır.",
    )


def labor_evidence() -> list[str]:
    return [
        "SGK hizmet dökümü ve işe giriş bildirgesi",
        "Ücret bordrosu, puantaj ve işyeri özlük dosyası",
        "Banka hesap hareketleri / ücret dekontları",
        "Arabuluculuk son tutanağı (7036 m. 3)",
        "Varsa iş sözleşmesi ve fesih evrakı",
        "Tanık beyanları (isim ve tebliğ adresi listede)",
    ]


def drop_unrelated_evidence(item: str, form: dict) -> bool:
    """True ise delil listesine alınmaz."""
    el = (item or "").lower()
    blob = _blob(form).lower()
    if re.search(r"kaza|olay tutana", el) and not re.search(r"kaza|iş kazas|trafik|meslek hastal", blob):
        return True
    if is_labor(form) and re.search(r"nüfus kay|evlilik cüzdan|ziynet|otel konaklama", el):
        return True
    ptype = str(form.get("petitionType") or "")
    if "İdare" in ptype:
        if re.search(r"ziynet|evlilik cüzdan|nüfus kay|otel konaklama|kira sözleşme|fotoğraf/video", el):
            return True
        if re.search(r"zarar belge", el) and not wants_tazminat(form):
            return True
        if re.search(r"sözleşme / akit|akit belgesi", el) and not re.search(r"(?<![a-zçğıöşü])sözleşme(?!li)", blob):
            return True
    if "Boşanma" not in ptype and re.search(r"ziynet|evlilik cüzdan", el):
        return True
    if "İdare" not in ptype and re.search(r"7315|atama uygunluk|idari işlem evrak|arşiv araştırm", el):
        return True
    if "Boşanma" in ptype and re.search(r"idari işlem evrak|7315|arşiv araştırm", el):
        return True
    if "İş" in ptype and re.search(r"idari işlem evrak|atama uygunluk|evlilik cüzdan|ziynet", el):
        return True
    if "İcra" in ptype and re.search(r"ziynet|nüfus kay|evlilik|7315|atama uygunluk", el):
        return True
    if "Kira" in ptype and re.search(r"ziynet|7315|atama uygunluk|nüfus kay", el):
        return True
    if "Tüketici" in ptype and re.search(r"ziynet|7315|atama uygunluk|evlilik", el):
        return True
    return False


def reconcile_date_span(text: str) -> str:
    """İki tarih ile 'N aylık' çelişirse N uydurulmaz; dönem tarihlerle anlatılır."""
    dates = re.findall(r"(\d{1,2})[./](\d{1,2})[./](\d{4})", text or "")
    m = re.search(r"(\d{1,2})\s*ayl[ıi]k", text or "", re.I)
    if len(dates) < 2 or not m:
        return text
    try:
        d1 = date(int(dates[0][2]), int(dates[0][1]), int(dates[0][0]))
        d2 = date(int(dates[1][2]), int(dates[1][1]), int(dates[1][0]))
    except ValueError:
        return text
    if d2 < d1:
        d1, d2 = d2, d1
    months = (d2.year - d1.year) * 12 + (d2.month - d1.month)
    if d2.day < d1.day:
        months -= 1
    said = int(m.group(1))
    if months >= 1 and abs(said - months) >= 2:
        return re.sub(
            r"\d{1,2}\s*ayl[ıi]k",
            "anılan tarihler arasındaki dönemdeki",
            text,
            count=1,
            flags=re.I,
        )
    return text


def strip_template_notes(text: str) -> str:
    t = text or ""
    t = re.sub(r"\s*\(Baro ili[^)]+\)", "", t)
    t = re.sub(r"\s*—\s*\[Cadde/[^\]]+\]", "", t)
    t = re.sub(r"\[Açık Büro[^\]]*\]", "........................", t)
    t = re.sub(r"\[Sokak/Cadde\][^\n]*", "........................", t)
    t = re.sub(r"\[Cadde/Sokak/No/İlçe/İl\]", "", t)
    return t


def _labor_claim_set(form: dict | None) -> set[str]:
    try:
        from bettersaul_mcp.quality import LABOR_CLAIMS, form_claims

        return form_claims(form or {}) & LABOR_CLAIMS
    except Exception:
        return {"ucret"}


ISE_IADE_LIKE = {"ise_iade", "bos_sure", "baslatmama"}


def labor_konu(form: dict | None = None) -> str:
    claims = _labor_claim_set(form) if form else {"ucret"}
    if not claims:
        claims = {"ucret"}
    if claims <= {"ucret"}:
        return (
            "Eksik / ödenmeyen ücret alacağının (işçilik alacağı) mevduata uygulanan "
            "en yüksek faiziyle tahsili talebidir."
        )
    bits: list[str] = []
    if "ise_iade" in claims:
        bits.append("feshin geçersizliğinin tespiti ile işe iade")
        if "bos_sure" in claims:
            bits.append("boşta geçen süre ücreti")
        if "baslatmama" in claims:
            bits.append("işe başlatmama tazminatı")
    order = (
        ("ucret", "ödenmeyen ücret alacağı"),
        ("fazla", "fazla çalışma ücreti"),
        ("izin", "yıllık izin ücreti"),
        ("kidem", "kıdem tazminatı"),
        ("ihbar", "ihbar tazminatı"),
    )
    for code, lab in order:
        if code in claims:
            bits.append(lab)
    if not bits:
        bits.append("ödenmeyen ücret alacağı")
    if len(bits) == 1:
        core = bits[0]
    elif len(bits) == 2:
        core = f"{bits[0]} ile {bits[1]}"
    else:
        core = ", ".join(bits[:-1]) + " ve " + bits[-1]
    return core[:1].upper() + core[1:] + " talebidir."


def labor_hukuk(form: dict | None = None) -> str:
    claims = _labor_claim_set(form) if form else {"ucret"}
    if not claims:
        claims = {"ucret"}
    bits: list[str] = []
    if "ucret" in claims:
        bits.append("4857 sayılı İş Kanunu m. 32 (ücret), m. 34 (ücretin gününde ödenmemesi)")
    if "fazla" in claims:
        bits.append("4857 sayılı Kanun m. 41 (fazla çalışma)")
    if "izin" in claims:
        bits.append("4857 sayılı Kanun m. 53 ve m. 59 (yıllık izin)")
    if "ihbar" in claims:
        bits.append("4857 sayılı Kanun m. 17 (süreli fesih / ihbar)")
    if "kidem" in claims:
        bits.append("1475 sayılı Kanun m. 14 (kıdem tazminatı; 4857 geçici m. 6)")
    if claims & ISE_IADE_LIKE:
        bits.append("4857 sayılı Kanun m. 18, m. 20 ve m. 21 (geçerli fesih / işe iade)")
    bits.append(
        "7036 sayılı İş Mahkemeleri Kanunu m. 3 (arabuluculuk dava şartı) ve m. 5 (görev)"
    )
    if "ucret" in claims or "fazla" in claims:
        bits.append("HMK m. 107 (belirsiz alacak)")
    bits.append("HMK m. 119 (dava dilekçesinin içeriği)")
    return "; ".join(bits) + "."


PROMPT_RULES = """
Görev vakıaya göredir (kamu düzeni). İşçi-işveren ücret/kıdem/ihbar/mesai: 7036 m. 5 İş Mahkemesi
(iş mahkemesi yoksa iş mahkemesi sıfatıyla asliye hukuk). Asliye hukuk + TBK haksız fiil yazılmaz.
İşçilik alacağı haksız fiil maddi/manevi tazminatı değildir; manevi tazminat istenmediyse eklenmez.
KONU, AÇIKLAMALAR, HUKUKİ SEBEPLER ve SONUÇ aynı kalem kümesi olmalı. Kullanıcı yalnızca ücret
istediyse işe iade / kıdem / ihbar / boşta geçen süre / işe başlatmama / fazla çalışma yazılmaz.
İşe iade istenirse 4857 m. 21: iade + boşta geçen süre + işe başlatmama. Kıdem/ihbar/izin, işe
başlatılmama sonrası ayrı arabuluculuk ister; aynı dilekçeye dökülmez.
7036 m. 3: talep edilen her kalem son tutanakta olmalı; tutanak no uydurma.
İstisna: iş kazası / meslek hastalığı tazminatı (m. 3/3).
Delil vakıaya uyar: ücret davasında kaza tutanağı yok; SGK, bordro, banka, özlük, arabuluculuk var.
Tazminat kutusu boşsa maddi/manevi metin yazılmaz.
Şablon uyarı notu (baro çelişkisi, [Cadde/Sokak]) dilekçeye yazılmaz.
Şekil: T.C. → makam → DAVA DİLEKÇESİ → taraflar → konu → harç → numaralı vakıa → hukuki sebepler → delil listesi → maddeli istem → imza/EK.
Her vakıanın altında Delil : / Hukuki dayanak : / Hukuki sonuç : yaz. Tür karıştırma. “Arz ederim” yok.
"""
