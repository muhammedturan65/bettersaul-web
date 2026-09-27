"""Dilekçe veri modeli + tutarlılık / hukuki uyum / uydurma katmanı.

Mevcut şablonu değiştirmez. Formda olmayanı uydurmaz; 'kesinlikle yanlış'
demez, doğrulanmasını ister. Flutter/PHP/MySQL gerektirmez.
"""
from __future__ import annotations

import json
import re
from typing import Any

from .templates import resolve_kind
from .motor.catalog import (
    CLAIM_SPECS,
    CITE_FOR_CLAIM as _CITE_FOR_CLAIM,
    FESHE_BAGLI,
    ISE_IADE_FAMILY,
    LABOR_CLAIMS,
    STATUTE_FOR_CLAIM as _STATUTE_FOR_CLAIM,
    TRACK_CLAIMS,
)
from .motor.pipeline import (
    analyze as _motor_analyze,
    claim_labels,
    cite_fits_claims,
    detect_claims,
    form_claims,
    format_preflight as _motor_preflight,
    format_quality_report as _motor_report,
    intent_text,
    is_kalem_dump,
)

KRITIK = "kritik"
YUKSEK = "yuksek"
ORTA = "orta"
DUSUK = "dusuk"

_SEV_MARK = {KRITIK: "KIRMIZI", YUKSEK: "TURUNCU", ORTA: "SARI", DUSUK: "YESIL"}

_NAME_RE = re.compile(
    r"\b([A-ZÇĞİÖŞÜ][a-zçğıöşü]+(?:\s+[A-ZÇĞİÖŞÜ][a-zçğıöşü]+){1,2})\b"
)
_NAME_UP_RE = re.compile(
    r"\b([A-ZÇĞİÖŞÜ][a-zçğıöşü]+\s+[A-ZÇĞİÖŞÜ]{2,})\b"
)
_TL_RE = re.compile(
    r"(?i)(\d{1,3}(?:\.\d{3})+|\d+)(?:\s*,\d{1,2})?\s*(?:TL|₺)"
)
_CITE_EK_RE = re.compile(
    r"(?i)(?:Yargıtay|Danıştay|AYM|Anayasa Mahkemesi)?[^\n]{0,40}"
    r"E\.\s*(\d{4}/\d+)\s*,?\s*K\.\s*(\d{4}/\d+)"
)
_CITE_BNO_RE = re.compile(r"(?i)B\.\s*No\s*[:：]?\s*(\d{4}/\d+)")
_TCKN_RE = re.compile(r"\b([1-9]\d{10})\b")
_ISO_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")

_STOP = {
    "türkiye", "ankara", "istanbul", "uşak", "usak", "erzurum",
    "mahkeme", "bakanlık", "bakanligi", "müdürlük", "mudurlugu",
    "anayasa", "yargıtay", "yargitay", "danıştay", "danistay",
    "müvekkil", "muvekkil", "davacı", "davaci", "davalı", "davali",
    "avukat", "vekili", "kanun", "madde", "karar", "dilekçe", "dilekce",
}

REQUIRED: dict[str, tuple[tuple[str, str], ...]] = {
    "bosanma": (
        ("mahkeme", "Mahkeme"),
        ("davaci", "Davacı"),
        ("davali", "Davalı"),
        ("vekil", "Vekil"),
        ("evlilik", "Evlilik bilgisi"),
        ("bosanma_sebebi", "Boşanma sebebi"),
        ("olaylar", "Olaylar"),
        ("deliller", "Deliller"),
        ("hukuki", "Hukuki sebepler"),
        ("sonuc", "Sonuç ve istem"),
    ),
    "is": (
        ("mahkeme", "İş mahkemesi"),
        ("davaci", "İşçi"),
        ("davali", "İşveren"),
        ("ise_giris", "İşe giriş"),
        ("isten_cikis", "İşten ayrılış"),
        ("ucret", "Ücret"),
        ("alacak", "Alacak kalemleri"),
        ("arabuluculuk", "Arabuluculuk"),
        ("deliller", "Deliller"),
        ("sonuc", "Sonuç ve istem"),
    ),
    "tuketici": (
        ("davaci", "Tüketici"),
        ("davali", "Satıcı / sağlayıcı"),
        ("urun", "Ürün / hizmet"),
        ("sozlesme", "Sözleşme"),
        ("bedel", "Bedel"),
        ("ayip", "Ayıp / uyuşmazlık"),
        ("sonuc", "Talep"),
    ),
    "idare": (
        ("mahkeme", "Mahkeme"),
        ("davaci", "Davacı"),
        ("davali", "Davalı idare"),
        ("islem", "Dava konusu işlem"),
        ("olaylar", "Olaylar"),
        ("deliller", "Deliller"),
        ("hukuki", "Hukuki dayanak"),
        ("sonuc", "Sonuç ve istem"),
    ),
    "icra": (
        ("davaci", "Alacaklı / şikâyetçi"),
        ("davali", "Borçlu / karşı taraf"),
        ("takip", "Takip konusu"),
        ("sonuc", "Talep"),
    ),
    "kira": (
        ("davaci", "Kiraya veren / kiracı"),
        ("davali", "Karşı taraf"),
        ("sozlesme", "Kira sözleşmesi"),
        ("sonuc", "Talep"),
    ),
    "tazminat": (
        ("davaci", "Davacı"),
        ("davali", "Davalı"),
        ("olaylar", "Olay ve kusur"),
        ("sonuc", "Tazminat talebi"),
    ),
    "ceza": (
        ("davaci", "Müşteki / sanık"),
        ("olaylar", "Olay anlatımı"),
        ("sonuc", "Talep"),
    ),
    "alacak": (
        ("davaci", "Alacaklı"),
        ("davali", "Borçlu"),
        ("olaylar", "Borç ilişkisi"),
        ("sonuc", "Talep"),
    ),
    "diger": (
        ("davaci", "Davacı"),
        ("davali", "Davalı"),
        ("olaylar", "Vakıa"),
        ("sonuc", "Talep"),
    ),
}

_CLAIM_EVIDENCE = (
    (r"(?i)fiziksel şiddet|darp|yaralama|sağlık rapor", r"(?i)sağlık rapor|adli rapor|hastane|epikriz", "Fiziksel şiddet"),
    (r"(?i)kumar", r"(?i)banka|hesap hareket|dekont", "Kumar harcaması"),
    (r"(?i)hakaret|tehdit", r"(?i)mesaj|whatsapp|tanık|ses kayd", "Hakaret / tehdit"),
    (r"(?i)ziynet|altın|bilezik|küpe", r"(?i)fotoğraf|fatura|kuyumcu|tanık", "Ziynet"),
    (r"(?i)ücret|kıdem|ihbar|fazla mesai", r"(?i)bordro|sgk|banka|özlük|arabuluculuk", "İşçilik alacağı"),
    (r"(?i)ayıp|ayıplı", r"(?i)fatura|garanti|servis|tespit", "Ayıp"),
)

_LAW_GRAPH = {
    "bosanma": ("TMK", "4721"),
    "velayet": ("TMK", "4721"),
    "nafaka": ("TMK", "4721"),
    "ziynet": ("TMK", "4721"),
    "tazminat_aile": ("TMK", "4721"),
    "adli": ("HMK", "6100"),
    "is": ("İş Kanunu", "4857"),
    "arabuluculuk": ("7036", "7036"),
    "idare": ("İYUK", "2577"),
    "gs": ("7315", "7315"),
    "tuketici": ("TKHK", "6502"),
}

def _fold(s: str) -> str:
    t = (s or "").replace("İ", "i").replace("I", "i").replace("ı", "i").lower()
    return (
        t.replace("ğ", "g").replace("ş", "s").replace("ö", "o")
        .replace("ü", "u").replace("ç", "c")
    )


def _norm_name(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip()).casefold()


def _blob(form: dict) -> str:
    bits = [
        str(form.get(k) or "")
        for k in (
            "petitionType", "title", "court", "parties", "caseSummary",
            "requests", "extraInstructions", "userPrompt", "lawyerName",
        )
    ]
    cv = form.get("claimValues")
    if cv:
        bits.append(cv if isinstance(cv, str) else json.dumps(cv, ensure_ascii=False))
    return "\n".join(bits)


def _heading_pat(label: str) -> str:
    parts: list[str] = []
    for ch in label:
        if ch in "İIıi":
            parts.append("[İIıi]")
        elif ch in "Şş":
            parts.append("[ŞşSs]")
        elif ch in "Çç":
            parts.append("[ÇçCc]")
        elif ch in "Ğğ":
            parts.append("[ĞğGg]")
        elif ch in "Üü":
            parts.append("[ÜüUu]")
        elif ch in "Öö":
            parts.append("[ÖöOo]")
        elif ch in r"\^$.|?*+()[]{}":
            parts.append("\\" + ch)
        else:
            parts.append(ch)
    return "".join(parts)


def _section(text: str, start: str, end: str = "") -> str:
    t = text or ""
    m = re.search(rf"(?im)^{_heading_pat(start)}\s*:?\s*$", t)
    if not m:
        return ""
    rest = t[m.end() :]
    if end:
        n = re.search(rf"(?im)^{_heading_pat(end)}\s*:?\s*$", rest)
        if n:
            return rest[: n.start()].strip()
    return rest.strip()


def _tl(raw: str) -> int | None:
    d = re.sub(r"[^\d]", "", raw or "")
    if not d:
        return None
    try:
        return int(d)
    except ValueError:
        return None


_AMOUNT_LABELS = (
    ("istirak", r"iştirak|istirak"),
    ("yoksulluk", r"yoksulluk"),
    ("ziynet", r"ziynet|alt[ıi]n|tak[ıi]"),
    ("manevi", r"manevi"),
    ("tazminat", r"maddi|tazminat"),
    ("ucret", r"ücret|ucret|k[ıi]dem|ihbar"),
    ("nafaka", r"nafaka"),
)


def _nearest_amount_label(text: str, start: int, end: int) -> str:
    line_start = (text or "").rfind("\n", 0, start) + 1
    line_end = (text or "").find("\n", start)
    if line_end < 0:
        line_end = len(text or "")
    line = (text or "")[line_start:line_end]
    loc_s = start - line_start
    loc_e = max(loc_s, end - line_start)
    after = line[loc_e:]
    nxt = _TL_RE.search(after)
    chunk = after[: nxt.start()] if nxt else after
    for lab, pat in _AMOUNT_LABELS:
        if re.search(pat, chunk, re.I):
            return lab
    before = line[:loc_s]
    for lab, pat in reversed(list(_AMOUNT_LABELS)):
        if re.search(pat, before, re.I):
            return lab
    return "diger"


def _amount_hits(text: str, section: str) -> list[dict]:
    out: list[dict] = []
    for m in _TL_RE.finditer(text or ""):
        val = _tl(m.group(1))
        if val is None or val < 50:
            continue
        out.append(
            {
                "label": _nearest_amount_label(text, m.start(), m.end()),
                "value": val,
                "section": section,
                "raw": m.group(0),
            }
        )
    return out


def _people(text: str) -> list[str]:
    found: list[str] = []
    extra = re.compile(
        r"(?i)m[uü]vekkil(?:im)?\s+([A-ZÇĞİÖŞÜ][A-Za-zÇĞİÖŞÜçğıöşü]+(?:\s+[A-ZÇĞİÖŞÜ][A-Za-zÇĞİÖŞÜçğıöşü]+){1,2})"
    )
    for rx in (extra, _NAME_UP_RE, _NAME_RE):
        for m in rx.finditer(text or ""):
            name = re.sub(r"\s+", " ", m.group(1)).strip()
            low = _fold(name)
            if any(w in _STOP for w in low.split()):
                continue
            if len(name.split()) < 2:
                continue
            if name not in found:
                found.append(name)
    return found


def _line_val(text: str, *labels: str) -> str:
    for lab in labels:
        m = re.search(rf"(?im)^{re.escape(lab)}\s*[:：]\s*(.+)$", text or "")
        if m and m.group(1).strip():
            return m.group(1).strip()
    return ""


def _header_name(text: str, label: str) -> str:
    block = _section(text, label, "DAVALI" if label == "DAVACI" else "DAVACI VEKİLİ")
    if label == "DAVACI":
        block = _section(text, "DAVACI", "DAVALI") or block
    return _line_val(block, "Ad Soyad", "Unvan") or _line_val(text, label)


def extract_model(form: dict, text: str = "") -> dict[str, Any]:
    """Yapılandırılmış dilekçe kartı. Eksik alanı uydurmaz."""
    kind = resolve_kind(str(form.get("petitionType") or ""))
    src = _blob(form)
    t = text or ""
    davaci = _line_val(src, "DAVACI", "Davacı") or _header_name(t, "DAVACI")
    davali = _line_val(src, "DAVALI", "Davalı") or _header_name(t, "DAVALI")
    vekil = str(form.get("lawyerName") or "") or _line_val(src, "VEKİL", "Vekil")
    fold = _fold(src)
    ground = ""
    if re.search(r"tmk\s*(?:m\.?\s*)?164|terke dayali|terk davasi", fold):
        ground = "164"
    elif re.search(r"tmk\s*(?:m\.?\s*)?166|temelinden sars|siddetli gecimsiz", fold):
        ground = "166"
    evlilik = ""
    em = re.search(
        r"(?i)(?:evl[ie]n|nik[aâ]h|evlilik).{0,24}(\d{1,2}[./]\d{1,2}[./]\d{4})",
        src + "\n" + t,
    )
    if em:
        evlilik = em.group(1)
    children = []
    for m in re.finditer(
        r"(?i)(?:müşterek çocuk|çocuk(?:ları)?|velayet)\s*[:：]?\s*([A-ZÇĞİÖŞÜ][A-Za-zÇĞİÖŞÜçğıöşü]+(?:\s+[A-ZÇĞİÖŞÜ][A-Za-zÇĞİÖŞÜçğıöşü]+){1,2})",
        src + "\n" + t,
    ):
        children.append(re.sub(r"\s+", " ", m.group(1)).strip())
    acik = (
        _section(t, "AÇIKLAMALAR", "HUKUKİ SEBEPLER")
        or _section(t, "AÇIKLAMALAR", "DELİLLER")
        or _section(t, "AÇIKLAMALAR", "HUKUKİ DAYANAKLAR")
    )
    son = _section(t, "SONUÇ VE İSTEM", "EKLER")
    delil = (
        _section(t, "DELİLLER", "SONUÇ VE İSTEM")
        or _section(t, "DELİLLER", "HUKUKİ DAYANAKLAR")
        or _section(t, "DELİLLER", "HUKUKİ NEDENLER")
        or _section(t, "DELİLLER", "HUKUKİ SEBEPLER")
    )
    huk = (
        _section(t, "HUKUKİ SEBEPLER", "DELİLLER")
        or _section(t, "HUKUKİ SEBEPLER", "SONUÇ VE İSTEM")
        or _section(t, "HUKUKİ DAYANAKLAR", "SONUÇ VE İSTEM")
        or _section(t, "HUKUKİ NEDENLER", "SONUÇ VE İSTEM")
    )
    amounts = (
        _amount_hits(src, "form")
        + _amount_hits(acik, "aciklama")
        + _amount_hits(son, "sonuc")
        + _amount_hits(_section(t, "KONU", "AÇIKLAMALAR"), "konu")
    )
    return {
        "kind": kind,
        "dava_turu": str(form.get("petitionType") or ""),
        "mahkeme": str(form.get("court") or ""),
        "davaci": davaci,
        "davali": davali,
        "vekil": vekil,
        "cocuklar": children,
        "evlilik": evlilik,
        "bosanma_sebebi": ground,
        "olaylar": (str(form.get("caseSummary") or "") or acik)[:800],
        "talepler": str(form.get("requests") or ""),
        "deliller": delil,
        "hukuki": huk,
        "sonuc": son or str(form.get("requests") or ""),
        "ekler": _section(t, "EKLER"),
        "amounts": amounts,
        "people_header": {
            "davaci": [davaci] if davaci else [],
            "davali": [davali] if davali else [],
        },
        "people_body": _people(acik),
        "people_sonuc": _people(son),
        "cites_text": [m.group(0).strip() for m in _CITE_EK_RE.finditer(t)]
        + [m.group(0).strip() for m in _CITE_BNO_RE.finditer(t)],
        "source": src,
        "has_text": bool(t.strip()),
    }


def _finding(sev: str, code: str, msg: str, hint: str = "") -> dict:
    return {"sev": sev, "code": code, "msg": msg, "hint": hint}


def _has_field(model: dict, key: str) -> bool:
    t = (model.get("source") or "") + "\n" + (model.get("olaylar") or "") + "\n" + (model.get("sonuc") or "")
    fold = _fold(t + "\n" + str(model.get("mahkeme") or ""))
    checks = {
        "mahkeme": bool(model.get("mahkeme")) or "mahkeme" in fold,
        "davaci": bool(model.get("davaci")),
        "davali": bool(model.get("davali")),
        "vekil": bool(model.get("vekil")) or "av." in fold,
        "evlilik": bool(model.get("evlilik")) or "evlilik" in fold or "nikah" in fold,
        "bosanma_sebebi": bool(model.get("bosanma_sebebi")),
        "olaylar": len(str(model.get("olaylar") or "")) > 40,
        "deliller": bool(model.get("deliller")) or "delil" in fold,
        "hukuki": bool(model.get("hukuki")) or "tmk" in fold or "iyuk" in fold or "hmk" in fold,
        "sonuc": bool(str(model.get("sonuc") or "").strip()) or bool(model.get("talepler")),
        "ise_giris": bool(re.search(r"ise giris|ise basl|işe giriş|işe başl", fold)),
        "isten_cikis": bool(re.search(r"isten cik|fesih|işten ayr|isten ayr", fold)),
        "ucret": bool(re.search(r"ucret|ücret|asgari|net ", fold)) or any(
            a["label"] == "ucret" for a in model.get("amounts") or []
        ),
        "alacak": bool(re.search(r"kidem|ihbar|fazla mesai|yillik izin|alacak", fold)),
        "arabuluculuk": "arabuluculuk" in fold,
        "urun": bool(re.search(r"urun|ürün|hizmet|mal ", fold)),
        "sozlesme": "sozlesme" in fold or "sözleşme" in fold,
        "bedel": bool(model.get("amounts")) or "bedel" in fold,
        "ayip": bool(re.search(r"ayip|ayıp|aykiri", fold)),
        "islem": bool(re.search(r"idari islem|atama|islem|iptal", fold)),
        "takip": bool(re.search(r"icra|takip|haciz", fold)),
    }
    return bool(checks.get(key))


def _party_findings(model: dict, text: str) -> list[dict]:
    out: list[dict] = []
    davaci = _norm_name(model.get("davaci") or "")
    acik_people = [_norm_name(x) for x in model.get("people_body") or []]
    if davaci and model.get("has_text") and acik_people:
        first = davaci.split()[0] if davaci.split() else ""
        if first and len(first) > 2 and not any(first in p for p in acik_people):
            foreign = [x for x in (model.get("people_body") or []) if _norm_name(x) != davaci]
            if foreign:
                out.append(
                    _finding(
                        KRITIK,
                        "taraf",
                        f"DAVACI bilgisi tutarsız: başlıkta {model.get('davaci')}, "
                        f"açıklamalarda {foreign[0]} geçiyor.",
                        "Başlık ve gövde aynı müvekkili kullanmalı.",
                    )
                )
    davali = _norm_name(model.get("davali") or "")
    if davali and model.get("has_text"):
        body = _fold(text or "")
        last = davali.split()[-1] if davali.split() else ""
        if last and len(last) > 3 and last not in body and "emniyet" not in davali:
            others = [x for x in (model.get("people_body") or []) if _norm_name(x) != davaci]
            if others:
                out.append(
                    _finding(
                        YUKSEK,
                        "taraf",
                        f"DAVALI adı gövdeyle örtüşmeyebilir: başlıkta {model.get('davali')}.",
                        "Husumet ve gövde aynı davalıyı göstermelidir.",
                    )
                )
    kids = model.get("cocuklar") or []
    if len({_norm_name(k) for k in kids}) > 1 and len(kids) >= 2:
        uniq = []
        for k in kids:
            if _norm_name(k) not in {_norm_name(u) for u in uniq}:
                uniq.append(k)
        if len(uniq) > 1:
            out.append(
                _finding(
                    KRITIK,
                    "cocuk",
                    "Müşterek çocuk adı farklı bölümlerde farklı: " + " / ".join(uniq[:3]) + ".",
                    "Tek çocuk için tek isim kullanın; kullanıcı vermediyse uydurmayın.",
                )
            )
    return out


def _amount_findings(model: dict) -> list[dict]:
    out: list[dict] = []
    by: dict[str, set[int]] = {}
    for a in model.get("amounts") or []:
        by.setdefault(a["label"], set()).add(int(a["value"]))
    labels = {
        "istirak": "iştirak nafakası",
        "yoksulluk": "yoksulluk nafakası",
        "nafaka": "nafaka",
        "ziynet": "ziynet bedeli",
        "tazminat": "tazminat",
        "manevi": "manevi tazminat",
        "ucret": "ücret / işçilik",
    }
    for key, vals in by.items():
        if key == "diger" or len(vals) < 2:
            continue
        shown = " / ".join(f"{v:,}".replace(",", ".") + " TL" for v in sorted(vals)[:5])
        out.append(
            _finding(
                KRITIK,
                "tutar",
                f"{labels.get(key, key)} için birden fazla tutar: {shown}.",
                "Açıklama, talep ve sonuç aynı rakamı kullanmalı.",
            )
        )
    ac = {a["value"] for a in model.get("amounts") or [] if a["section"] == "aciklama" and a["label"] in ("istirak", "nafaka", "yoksulluk", "ziynet", "tazminat")}
    so = {a["value"] for a in model.get("amounts") or [] if a["section"] == "sonuc" and a["label"] in ("istirak", "nafaka", "yoksulluk", "ziynet", "tazminat")}
    if ac and so and ac != so:
        out.append(
            _finding(
                KRITIK,
                "talep_capraz",
                "AÇIKLAMALAR ile SONUÇ VE İSTEM tutarları örtüşmüyor.",
                "Açıklama → talepler → sonuç çapraz kontrol edilmeli.",
            )
        )
    return out


def _law_findings(model: dict, text: str) -> list[dict]:
    out: list[dict] = []
    kind = model.get("kind") or ""
    t = text or ""
    huk = (model.get("hukuki") or "") + "\n" + t
    ground = model.get("bosanma_sebebi") or ""
    if kind == "bosanma":
        if ground == "166" and re.search(r"(?i)TMK.{0,16}164", huk):
            out.append(
                _finding(
                    KRITIK,
                    "madde",
                    "Boşanma sebebi evlilik birliğinin temelinden sarsılması (TMK 166) "
                    "iken dayanakta TMK 164 geçiyor.",
                    "İlgili hukuki dayanağı doğrulayın; 164 ile 166 aynı davada karışmamalı.",
                )
            )
        if ground == "164" and re.search(r"(?i)TMK.{0,16}166", huk) and not re.search(r"(?i)TMK.{0,16}164", huk):
            out.append(
                _finding(
                    YUKSEK,
                    "madde",
                    "Form terke dayalı (TMK 164); dayanakta 166 yazılmış.",
                    "İlgili hukuki dayanağı doğrulayın.",
                )
            )
        if re.search(r"(?i)nafaka|velayet|ziynet|tazminat", t) and not re.search(r"TMK|4721", huk + t[:800]):
            out.append(
                _finding(
                    ORTA,
                    "mevzuat_graf",
                    "Aile hukuku talebi var; TMK dayanağı zayıf görünüyor.",
                    "Nafaka / velayet / ziynet / tazminat → TMK; adli yardım → HMK.",
                )
            )
    if kind != "idare" and re.search(r"(?i)7315 sayılı|Atama Uygunluk", t):
        out.append(
            _finding(
                KRITIK,
                "madde",
                "Bu dava türünde 7315 / atama uygunluk metni var.",
                "İdare paketi başka türe taşınmamalı.",
            )
        )
    if kind == "idare" and re.search(r"(?i)ziynet|TMK\s*m\.\s*16[46]", t):
        out.append(
            _finding(
                KRITIK,
                "madde",
                "İdare dilekçesinde boşanma / ziynet sızıntısı.",
                "Dava türü ile mevzuat grafı uyumlu olmalı.",
            )
        )
    if re.search(r"(?i)HAGB|hükmün açıklanmasının geri", model.get("source") or "") and re.search(
        r"(?i)(?:HAGB|hükmün açıklanmasının geri).{0,60}mahk[ûu]miyet",
        t,
    ):
        out.append(
            _finding(
                KRITIK,
                "hagb",
                "HAGB mahkûmiyet gibi yazılmış.",
                "HAGB mahkûmiyet / sabıka değildir; dayanağı CMK m. 231 ile doğrulayın.",
            )
        )
    return out


def _fmt_claims(codes: set[str]) -> str:
    labs = claim_labels(codes)
    return ", ".join(labs) if labs else "—"


def _claim_scan_text(text: str) -> str:
    """7036 m. 3 genel cümlesindeki 'işe iade' usul gürültüsünü kalem saymaz."""
    t = text or ""
    t = re.sub(
        r"(?i)(?:7036[^\n.]{0,140}|arabulucu[^\n.]{0,80})işe iade[^\n.]{0,80}",
        " ",
        t,
    )
    t = re.sub(
        r"(?i)işçi(?:\s+veya\s+işveren)?\s+alacağı,?\s+tazminat ve işe iade",
        "işçi alacağı",
        t,
    )
    return t


def _claim_alignment_findings(model: dict, text: str, form: dict) -> list[dict]:
    """KONU ≠ gövde/görev ≠ SONUÇ — 48 puanlık iş dilekçesinin ana hatası."""
    out: list[dict] = []
    t = text or ""
    if not (t.strip()):
        return out
    konu = _section(t, "KONU", "AÇIKLAMALAR") or _section(t, "DAVA KONUSU", "AÇIKLAMALAR")
    acik = (
        _section(t, "AÇIKLAMALAR", "HUKUKİ SEBEPLER")
        or _section(t, "AÇIKLAMALAR", "DELİLLER")
        or model.get("olaylar")
        or ""
    )
    son = model.get("sonuc") or _section(t, "SONUÇ VE İSTEM", "EKLER")
    head = "\n".join((t or "").splitlines()[:18])
    k = detect_claims(_claim_scan_text(konu)) & TRACK_CLAIMS
    a = detect_claims(_claim_scan_text(acik)) & TRACK_CLAIMS
    s = detect_claims(_claim_scan_text(son)) & TRACK_CLAIMS
    ti = detect_claims(_claim_scan_text(head)) & TRACK_CLAIMS
    wanted = form_claims(form) & TRACK_CLAIMS
    if k and s and k != s:
        out.append(
            _finding(
                KRITIK,
                "konu_sonuc",
                f"KONU ile SONUÇ VE İSTEM çelişiyor: KONU=[{_fmt_claims(k)}] "
                f"SONUÇ=[{_fmt_claims(s)}].",
                "HMK m. 119: konu, açıklama ve sonuç aynı talep kümesini göstermeli.",
            )
        )
    ghost_body = ((a | ti) - s) & TRACK_CLAIMS
    if ghost_body:
        out.append(
            _finding(
                KRITIK,
                "talep_tur",
                "Açıklama / görev satırında SONUÇ'ta olmayan dava türü var: "
                + _fmt_claims(ghost_body)
                + ".",
                "İşe iade + kıdem + ihbar + fazla çalışma dökümü, yalnızca ücret istenen davaya yazılmaz.",
            )
        )
    missing_son = (wanted - s) & TRACK_CLAIMS
    if missing_son and s:
        out.append(
            _finding(
                YUKSEK,
                "talep_tur",
                "Kullanıcı kalemi formda var; SONUÇ'ta yok: " + _fmt_claims(missing_son) + ".",
                "İstenen kalem sonuç fıkrasına alınır; miktar yoksa uydurulmaz.",
            )
        )
    if "ise_iade" in (k | a | s | wanted) and (FESHE_BAGLI & (k | a | s)):
        out.append(
            _finding(
                YUKSEK,
                "talep_tur",
                "İşe iade ile feshe bağlı kıdem / ihbar / yıllık izin aynı dilekçede karışmış.",
                "İşe iade hükmünde 4857 m. 21 boşta geçen süre ve işe başlatmama tazminatı "
                "belirlenir. İşe başlatılmama sonrası kıdem-ihbar-izin için ayrı arabuluculuk "
                "gerekir; önceki işe iade tutanağı bu kalemler için dava şartını karşılamaz.",
            )
        )
    if "ise_iade" in (s | wanted) and not ({"bos_sure", "baslatmama"} & (s | wanted)):
        out.append(
            _finding(
                ORTA,
                "talep_tur",
                "İşe iade istenmiş; 4857 m. 21 üçlüsü (boşta geçen süre / işe başlatmama) zayıf.",
                "İşe iade dilekçesinde iade + boşta geçen süre ücreti + işe başlatmama tazminatı birlikte yazılır; tutar yoksa uydurulmaz.",
            )
        )
    return out


def _dayanak_statute_findings(model: dict, text: str, form: dict) -> list[dict]:
    out: list[dict] = []
    huk = (model.get("hukuki") or "") + "\n" + (text or "")
    son = model.get("sonuc") or ""
    wanted = form_claims(form)
    active = (detect_claims(son) | wanted) & TRACK_CLAIMS
    for code, pat in _STATUTE_FOR_CLAIM:
        if code in active:
            continue
        if re.search(pat, huk, re.I):
            out.append(
                _finding(
                    KRITIK if code in LABOR_CLAIMS or code in {"tmk164", "tmk166"} else YUKSEK,
                    "dayanak_kalem",
                    f"Dayanakta {claim_labels({code})[0] if claim_labels({code}) else code} "
                    "maddesi var; bu kalem talep edilmiyor.",
                    "İstemediğiniz kalemin maddesi ve içtihadı dayanağa eklenmez.",
                )
            )
    kind = model.get("kind") or ""
    if kind == "is" and re.search(r"(?i)TMK\s*m?\.?\s*16[46]|ziynet|7315 sayılı", huk):
        out.append(
            _finding(
                KRITIK,
                "dayanak_kalem",
                "İş dilekçesinin dayanağına aile / 7315 metni girmiş.",
                "İşçilik alacağı 4857 + 7036 + HMK ile sınırlıdır.",
            )
        )
    return out


def _evidence_findings(model: dict, text: str) -> list[dict]:
    out: list[dict] = []
    delil = (model.get("deliller") or "") + "\n" + (text or "")
    acik = model.get("olaylar") or ""
    blob = acik + "\n" + (text or "")
    for claim_re, ev_re, title in _CLAIM_EVIDENCE:
        if re.search(claim_re, blob) and not re.search(ev_re, delil):
            out.append(
                _finding(
                    ORTA,
                    "delil",
                    f"{title} iddiası var; bunu destekleyen delil satırı yok.",
                    "İddia ile DELİLLER arasında bağ kurulmalı; olmayan belge uydurulmaz.",
                )
            )
    return out


def _invent_findings(model: dict, text: str) -> list[dict]:
    out: list[dict] = []
    src = model.get("source") or ""
    src_fold = _fold(src)
    for m in _TCKN_RE.finditer(text or ""):
        if m.group(1) not in src:
            out.append(
                _finding(
                    KRITIK,
                    "uydurma",
                    "Metinde TCKN var; kullanıcı kaynağında yok.",
                    "Kullanıcı vermediyse üretmeyin; [BİLGİ EKSİK] bırakın.",
                )
            )
            break
    if _ISO_RE.search(text or ""):
        out.append(_finding(ORTA, "bicim", "ISO tarih var; gg.aa.yyyy yazılmalı.", ""))
    for m in re.finditer(r"(?i)tanık\s+([A-ZÇĞİÖŞÜ][A-Za-zÇĞİÖŞÜçğıöşü]+(?:\s+[A-ZÇĞİÖŞÜ][A-Za-zÇĞİÖŞÜçğıöşü]+)+)", text or ""):
        name = m.group(1).strip()
        if _fold(name) not in src_fold:
            out.append(
                _finding(
                    YUKSEK,
                    "uydurma",
                    f"Tanık adı ({name}) kullanıcı metninde yok.",
                    "Tanık, tarih, esas/karar no, tutar kullanıcı vermediyse yazılmaz.",
                )
            )
            break
    form_vals = {a["value"] for a in model.get("amounts") or [] if a["section"] == "form"}
    text_vals = {a["value"] for a in model.get("amounts") or [] if a["section"] != "form"}
    if form_vals and text_vals - form_vals:
        extra = sorted(text_vals - form_vals)
        out.append(
            _finding(
                YUKSEK,
                "uydurma",
                "Formda olmayan tutar metne girmiş: "
                + ", ".join(f"{v:,}".replace(",", ".") + " TL" for v in extra[:4])
                + ".",
                "Kullanıcı vermediyse para miktarı üretilmez.",
            )
        )
    return out


def _cite_findings(model: dict, memory: dict | None) -> list[dict]:
    out: list[dict] = []
    mem = memory or {}
    known: list[str] = []
    for c in mem.get("cites") or []:
        known.append(str(c))
    for row in mem.get("aym") or []:
        if isinstance(row, dict):
            known.append(str(row.get("kunye") or row.get("baslik") or ""))
    known_s = " ".join(known)
    unverified = 0
    for raw in model.get("cites_text") or []:
        ek = _CITE_EK_RE.search(raw)
        bno = _CITE_BNO_RE.search(raw)
        key = ""
        if ek:
            key = ek.group(1)
        elif bno:
            key = bno.group(1)
        if key and key not in known_s:
            unverified += 1
    if unverified:
        out.append(
            _finding(
                YUKSEK,
                "ictihat",
                f"{unverified} içtihat künyesi tarama hafızasında yok — doğrulanmamış içtihat.",
                "Esas/karar/tarih/daire eşleşmezse 'bu karar vardır' denmez; künye uydurulmaz.",
            )
        )
    return out


def _cite_claim_findings(model: dict, text: str, form: dict) -> list[dict]:
    if (model.get("kind") or "") != "is":
        return []
    claims = form_claims(form)
    huk = (
        model.get("hukuki")
        or _section(text or "", "HUKUKİ SEBEPLER", "DELİLLER")
        or _section(text or "", "HUKUKİ SEBEPLER", "SONUÇ VE İSTEM")
        or _section(text or "", "HUKUKİ DAYANAKLAR", "SONUÇ VE İSTEM")
    )
    for ln in (huk or "").splitlines():
        if not re.search(r"(?i)Yargıtay|Danıştay|AYM|E\.\s*\d{4}|B\.\s*No", ln):
            continue
        if not cite_fits_claims(ln, claims):
            return [
                _finding(
                    KRITIK,
                    "dayanak_kalem",
                    "HUKUKİ DAYANAKLAR’da istenmeyen kaleme ait içtihat satırı var.",
                    "Ücret davasına işe iade / kıdem / ihbar kararı yapıştırılmaz.",
                )
            ]
    return []


def _required_findings(model: dict) -> list[dict]:
    out: list[dict] = []
    kind = model.get("kind") or "diger"
    for key, label in REQUIRED.get(kind, REQUIRED["diger"]):
        if not _has_field(model, key):
            sev = YUKSEK if key in ("davaci", "davali", "sonuc", "bosanma_sebebi") else ORTA
            out.append(
                _finding(
                    sev,
                    "zorunlu",
                    f"Zorunlu alan eksik ({kind}): {label}.",
                    "Mahkeme → dava türü → zorunlu alan. Yoksa [BİLGİ EKSİK]; uydurmayın.",
                )
            )
    return out


def _subscores(findings: list[dict], model: dict, text: str) -> dict[str, int]:
    def hit(*codes: str, sev: str | None = None) -> int:
        n = 0
        for f in findings:
            if f["code"] in codes and (sev is None or f["sev"] == sev):
                n += 1
        return n

    bicim = 100
    if not model.get("has_text"):
        bicim = 40
    if not re.search(r"(?im)^DAVACI\b", text or ""):
        bicim -= 20
    if not re.search(r"(?im)^SONUÇ VE İSTEM\b", text or ""):
        bicim -= 15
    if any(f["code"] == "bicim" for f in findings):
        bicim -= 10
    veri = 100 - 22 * hit("taraf", "cocuk", "tutar", sev=KRITIK) - 12 * hit("taraf", "cocuk", "tutar")
    hukuk = (
        100
        - 20 * hit("madde", "hagb", "mevzuat_graf", "dayanak_kalem", sev=KRITIK)
        - 10 * hit("madde", "hagb", "mevzuat_graf", "dayanak_kalem")
    )
    talep = (
        100
        - 25 * hit("talep_capraz", "tutar", "konu_sonuc", "talep_tur", sev=KRITIK)
        - 10 * hit("talep_capraz", "konu_sonuc", "talep_tur")
    )
    delil = 100 - 12 * hit("delil")
    dil = 90 if re.search(r"(?i)müvekkil", text or "") else 70
    if re.search(r"(?i)wikipedia|Vekile Not|formda 164|4\.\s*BÖLÜM", text or ""):
        dil -= 25
    ictihat = 100 - 18 * hit("ictihat")
    if model.get("has_text") and not (model.get("cites_text") or []):
        ictihat = 70
    clip = lambda n: max(0, min(100, n))
    return {
        "Biçimsel uygunluk": clip(bicim),
        "Veri tutarlılığı": clip(veri),
        "Hukuki dayanak": clip(hukuk),
        "Talep tutarlılığı": clip(talep),
        "Delil yeterliliği": clip(delil),
        "Dil ve üslup": clip(dil),
        "İçtihat doğrulama": clip(ictihat),
    }


def _overall(sub: dict[str, int]) -> int:
    w = {
        "Biçimsel uygunluk": 10,
        "Veri tutarlılığı": 25,
        "Hukuki dayanak": 15,
        "Talep tutarlılığı": 15,
        "Delil yeterliliği": 10,
        "Dil ve üslup": 10,
        "İçtihat doğrulama": 15,
    }
    s = sum(sub.get(k, 0) * w[k] for k in w)
    return int(round(s / 100))


def _load_memory(memory: dict | None) -> dict:
    if memory:
        return memory
    try:
        import os
        import sys
        from pathlib import Path
        if sys.platform == "darwin":
            p = Path.home() / "Library" / "Application Support" / "BetterSaul" / "case_memory.json"
        else:
            p = Path(os.environ.get("LOCALAPPDATA") or "") / "BetterSaul" / "case_memory.json"
        if p.is_file():
            data = json.loads(p.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
    except Exception:
        pass
    return {}


def review(form: dict, text: str = "", memory: dict | None = None) -> dict:
    """İki mod: dilekçe temiz kalır; bu rapor araştırma kutusuna gider."""
    memory = _load_memory(memory)
    model = extract_model(form, text)
    findings = []
    findings.extend(_required_findings(model))
    if model.get("has_text"):
        findings.extend(_party_findings(model, text))
        findings.extend(_amount_findings(model))
        findings.extend(_law_findings(model, text))
        findings.extend(_claim_alignment_findings(model, text, form))
        findings.extend(_dayanak_statute_findings(model, text, form))
        findings.extend(_evidence_findings(model, text))
        findings.extend(_invent_findings(model, text))
        findings.extend(_cite_findings(model, memory))
        findings.extend(_cite_claim_findings(model, text, form))
    motor = _motor_analyze(form, text or "", memory=memory, extra=findings)
    uniq = motor.get("findings") or findings
    if motor.get("subscores"):
        sub = motor["subscores"]
        score = int(motor.get("score") or 0)
    else:
        sub = _subscores(uniq, model, text)
        score = _overall(sub)
    gaps = [f["msg"] for f in uniq if f["code"] in ("zorunlu", "bicim", "delil", "zincir")]
    inc = [f["msg"] for f in uniq if f["code"] not in ("zorunlu", "bicim")]
    return {
        "score": score,
        "breakdown": motor.get("breakdown") or {k: f"{v}/100" for k, v in sub.items()},
        "subscores": sub,
        "gaps": gaps,
        "inconsistencies": inc,
        "findings": uniq,
        "model": model,
        "classifier": motor.get("classifier"),
        "questions": motor.get("questions") or [],
        "adversarial": motor.get("adversarial") or [],
        "claims": motor.get("claims") or {},
        "critical": bool(motor.get("critical")),
        "ok": score >= 80 and not any(f["sev"] == KRITIK for f in uniq),
    }


def format_report(rev: dict) -> str:
    if rev.get("classifier") is not None or rev.get("adversarial") is not None:
        try:
            return _motor_report(rev)
        except Exception:
            pass
    score = int(rev.get("score") or 0)
    lines = [f"Dilekçe kalite testi: {score}/100"]
    br = rev.get("breakdown") or {}
    if br:
        lines.append(" · ".join(f"{k} {v}" for k, v in br.items()))
    by: dict[str, list[dict]] = {KRITIK: [], YUKSEK: [], ORTA: [], DUSUK: []}
    for f in rev.get("findings") or []:
        by.setdefault(f.get("sev") or ORTA, []).append(f)
    titles = (
        (KRITIK, "Kritik — mahkemeye sunulmadan düzeltilmeli"),
        (YUKSEK, "Yüksek"),
        (ORTA, "Orta"),
        (DUSUK, "Düşük"),
    )
    any_bad = False
    for sev, title in titles:
        items = by.get(sev) or []
        if not items:
            continue
        any_bad = True
        lines.append(f"{_SEV_MARK[sev]} {title}:")
        for f in items[:8]:
            lines.append(f"- {f['msg']}")
            if f.get("hint"):
                lines.append(f"  ({f['hint']})")
    if not any_bad:
        lines.append("YESIL Sorun bulunmayanlar: zorunlu alan, taraf, tutar, madde, içtihat.")
    elif score >= 80 and not by.get(KRITIK):
        lines.append("Kritik yok; yüksek/orta notlar araştırma kutusunda.")
    return "\n".join(lines)


def preflight(form: dict) -> str:
    """AI yazmadan önce kart + ön değerlendirme. Eksik alanı doldurmaz."""
    rev = review(form, text="", memory=None)
    model = rev.get("model") or {}
    extra = [
        f"Davacı: {model.get('davaci') or '[BİLGİ GİRİLMEDİ]'}",
        f"Davalı: {model.get('davali') or '[BİLGİ GİRİLMEDİ]'}",
    ]
    if (model.get("kind") or "") == "bosanma":
        extra.append(f"Boşanma sebebi: TMK {model.get('bosanma_sebebi') or '[BİLGİ GİRİLMEDİ]'}")
        extra.append(f"Evlilik: {model.get('evlilik') or '[BİLGİ GİRİLMEDİ]'}")
    miss = [f["msg"] for f in rev.get("findings") or [] if f["code"] == "zorunlu"]
    if miss:
        extra.append("Zorunlu alanlar (üretilmeyecek):")
        extra.extend(f"- {m}" for m in miss[:8])
    try:
        return _motor_preflight(form, extra)
    except Exception:
        return "\n".join(["Yazmadan önce veri kartı."] + extra)


def review_text(text: str, petition_type: str = "", source: str = "", memory: dict | None = None) -> str:
    form = {"petitionType": petition_type, "caseSummary": source, "userPrompt": source}
    return format_report(review(form, text, memory=memory))
