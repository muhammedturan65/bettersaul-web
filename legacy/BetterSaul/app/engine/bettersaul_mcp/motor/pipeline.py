"""Bağımsız denetim zinciri. Dilekçe metnine sistem notu yazmaz."""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from .catalog import (
    CLAIM_EVIDENCE,
    CLAIM_SPECS,
    CITE_FOR_CLAIM,
    EVIDENCE_ALIASES,
    FAMILY_CLAIMS,
    FESHE_BAGLI,
    ISE_IADE_FAMILY,
    JOINDER_RULES,
    LABOR_CLAIMS,
    MISSING_MATRIX,
    PROMPT_LEAK,
    STATUTE_FOR_CLAIM,
    TRACK_CLAIMS,
    TRACKS,
)

KRITIK = "kritik"
YUKSEK = "yuksek"
ORTA = "orta"
DUSUK = "dusuk"

_DATE_RE = re.compile(r"(\d{1,2})[./](\d{1,2})[./](\d{4})")
_TL_RE = re.compile(r"(?i)(\d{1,3}(?:\.\d{3})+|\d+)(?:\s*,\d{1,2})?\s*(?:TL|₺)")
_TCKN_RE = re.compile(r"\b([1-9]\d{10})\b")
_EK_RE = re.compile(r"(?i)E\.\s*(\d{4}/\d+)\s*,?\s*K\.\s*(\d{4}/\d+)")
_BNO_RE = re.compile(r"(?i)B\.\s*No\s*[:：]?\s*(\d{4}/\d+)")


def _fold(s: str) -> str:
    t = (s or "").replace("İ", "i").replace("I", "i").replace("ı", "i").lower()
    return (
        t.replace("ğ", "g").replace("ş", "s").replace("ö", "o")
        .replace("ü", "u").replace("ç", "c")
    )


def _f(sev: str, code: str, msg: str, hint: str = "", dim: str = "") -> dict:
    return {"sev": sev, "code": code, "msg": msg, "hint": hint, "dim": dim}


def detect_claims(text: str) -> set[str]:
    t = text or ""
    return {c for c, pat, _ in CLAIM_SPECS if re.search(pat, t, re.I)}


def claim_labels(codes: set[str]) -> list[str]:
    lab = {c: n for c, _, n in CLAIM_SPECS}
    order = [c for c, _, _ in CLAIM_SPECS]
    return [lab[c] for c in order if c in codes]


def _fmt(codes: set[str]) -> str:
    labs = claim_labels(codes)
    return ", ".join(labs) if labs else "—"


def is_kalem_dump(text: str) -> bool:
    return len(detect_claims(text) & LABOR_CLAIMS) >= 3


def intent_text(form: dict) -> str:
    bits = [
        str((form or {}).get(k) or "")
        for k in ("requests", "extraInstructions", "caseSummary", "userPrompt")
    ]
    title = str((form or {}).get("title") or "")
    if title and not is_kalem_dump(title):
        bits.append(title)
    return "\n".join(bits)


def form_claims(form: dict) -> set[str]:
    found = detect_claims(intent_text(form or {}))
    ptype = str((form or {}).get("petitionType") or "")
    kind = _kind_from_ptype(ptype)
    if kind == "is" and not (found & LABOR_CLAIMS):
        found.add("ucret")
    if kind == "bosanma" and not (found & {"tmk164", "tmk166", "anlasmali"}):
        src = _fold(intent_text(form or {}))
        if re.search(r"terke dayali|tmk\s*(?:m\.?\s*)?164", src):
            found.add("tmk164")
        elif re.search(r"anlasmali", src):
            found.add("anlasmali")
        else:
            found.add("tmk166")
    if kind == "idare" and "iptal" not in found and "tam_yargi" not in found:
        found.add("iptal")
    return found


def cite_fits_claims(text: str, claims: set[str]) -> bool:
    marked = {c for c, pat in CITE_FOR_CLAIM if re.search(pat, text or "", re.I)}
    if not marked:
        return True
    return bool(marked & (claims or set()))


def _kind_from_ptype(ptype: str) -> str:
    p = _fold(ptype)
    for code, spec in TRACKS.items():
        if spec.get("kind") and spec["kind"] != "diger" and spec["kind"] in p:
            pass
    if "idar" in p or "vergi" in p:
        return "idare"
    if "bosan" in p or "aile" in p:
        return "bosanma"
    if re.search(r"\bis\b|isci|işçi", p) or "iş " in (ptype or "").lower():
        return "is"
    if "icra" in p:
        return "icra"
    if "tuketici" in p:
        return "tuketici"
    if "kira" in p or "tahliye" in p:
        return "kira"
    if "tazminat" in p:
        return "tazminat"
    if "ceza" in p:
        return "ceza"
    if "alacak" in p or "ticaret" in p:
        return "alacak"
    return "diger"


def classify(form: dict) -> dict:
    """Kesin hüküm değil; ön değerlendirme."""
    blob = _fold(intent_text(form) + " " + str((form or {}).get("petitionType") or ""))
    scores: list[tuple[int, str]] = []
    for code, spec in TRACKS.items():
        n = len(re.findall(spec["pat"], blob, re.I))
        if n:
            scores.append((n, code))
    scores.sort(reverse=True)
    top = scores[0][1] if scores else _kind_from_ptype(str((form or {}).get("petitionType") or ""))
    if top == "diger" and str((form or {}).get("petitionType") or ""):
        mapped = _kind_from_ptype(str(form.get("petitionType") or ""))
        top = mapped if mapped != "diger" else top
    alts = [c for _, c in scores[1:3]]
    label = TRACKS.get(top, {}).get("label") or top
    note = f"Ön değerlendirme: Olaylarınız {label} davası niteliğinde olabilir. Kesin nitelendirme değildir."
    if alts:
        note += " Ayrım: " + " / ".join(TRACKS[a]["label"] for a in alts if a in TRACKS) + " da değerlendirilebilir."
    return {"track": top, "alts": alts, "note": note, "claims": sorted(form_claims(form))}


def _heading_pat(label: str) -> str:
    parts: list[str] = []
    for ch in label:
        if ch in "İIıi":
            parts.append("[İIıi]")
        elif ch in "ŞşSs":
            parts.append("[ŞşSs]")
        elif ch in "ÇçCc":
            parts.append("[ÇçCc]")
        elif ch in "ĞğGg":
            parts.append("[ĞğGg]")
        elif ch in "ÜüUu":
            parts.append("[ÜüUu]")
        elif ch in "ÖöOo":
            parts.append("[ÖöOo]")
        elif ch in r"\^$.|?*+()[]{}":
            parts.append("\\" + ch)
        else:
            parts.append(ch)
    return "".join(parts)


def section(text: str, start: str, end: str = "") -> str:
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


def split_sections(text: str) -> dict[str, str]:
    t = text or ""
    return {
        "konu": section(t, "KONU", "AÇIKLAMALAR") or section(t, "DAVA KONUSU", "AÇIKLAMALAR"),
        "acik": section(t, "AÇIKLAMALAR", "HUKUKİ SEBEPLER")
        or section(t, "AÇIKLAMALAR", "DELİLLER")
        or section(t, "AÇIKLAMALAR", "HUKUKİ DAYANAKLAR"),
        "delil": section(t, "DELİLLER", "SONUÇ VE İSTEM")
        or section(t, "DELİLLER", "HUKUKİ DAYANAKLAR")
        or section(t, "DELİLLER", "HUKUKİ NEDENLER")
        or section(t, "DELİLLER", "HUKUKİ SEBEPLER"),
        "huk": section(t, "HUKUKİ SEBEPLER", "DELİLLER")
        or section(t, "HUKUKİ SEBEPLER", "SONUÇ VE İSTEM")
        or section(t, "HUKUKİ DAYANAKLAR", "SONUÇ VE İSTEM")
        or section(t, "HUKUKİ NEDENLER", "SONUÇ VE İSTEM"),
        "son": section(t, "SONUÇ VE İSTEM", "EKLER"),
        "ek": section(t, "EKLER"),
        "head": "\n".join((t or "").splitlines()[:20]),
    }


def _claim_scan(text: str) -> str:
    t = text or ""
    t = re.sub(r"(?i)(?:7036[^\n.]{0,140}|arabulucu[^\n.]{0,80})işe iade[^\n.]{0,80}", " ", t)
    return t


def _parse_date(m: re.Match) -> datetime | None:
    try:
        return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    except ValueError:
        return None


def extract_dates(text: str) -> list[dict]:
    out: list[dict] = []
    for m in _DATE_RE.finditer(text or ""):
        dt = _parse_date(m)
        if not dt:
            continue
        start = max(0, m.start() - 40)
        ctx = _fold((text or "")[start : m.end() + 20])
        label = "diger"
        for key, pat in (
            ("fesih", r"fesih|isten cik|isten ayr"),
            ("arabulucu", r"arabulucu|son tutanak"),
            ("ihtar", r"ihtar|temerrut|ihtarnam"),
            ("sozlesme", r"sozlesme|ise giris|kira baslang"),
            ("teblig", r"teblig|ogrenme"),
            ("evlilik", r"evlilik|nikah"),
            ("islem", r"islem|atama|karar tarihi"),
        ):
            if re.search(pat, ctx):
                label = key
                break
        out.append({"label": label, "date": dt, "raw": m.group(0)})
    return out


def missing_questions(form: dict, track: str) -> list[str]:
    blob = _fold(intent_text(form))
    qs: list[str] = []
    for key in (track,):
        for prio, item in MISSING_MATRIX.get(key, ()):
            low = _fold(item)
            if any(w in blob for w in low.split()[:2]):
                continue
            qs.append(f"[{prio}] {item}")
    claims = form_claims(form)
    if "ise_iade" in claims:
        for prio, item in MISSING_MATRIX.get("ise_iade", ()):
            qs.append(f"[{prio}] {item}")
    seen: set[str] = set()
    uniq: list[str] = []
    for q in qs:
        if q in seen:
            continue
        seen.add(q)
        uniq.append(q)
    return uniq[:6]


def _alignment(form: dict, secs: dict[str, str]) -> list[dict]:
    out: list[dict] = []
    k = detect_claims(_claim_scan(secs.get("konu") or "")) & TRACK_CLAIMS
    a = detect_claims(_claim_scan(secs.get("acik") or "")) & TRACK_CLAIMS
    h = detect_claims(_claim_scan(secs.get("huk") or "")) & TRACK_CLAIMS
    s = detect_claims(_claim_scan(secs.get("son") or "")) & TRACK_CLAIMS
    d = detect_claims(_claim_scan(secs.get("delil") or "")) & TRACK_CLAIMS
    wanted = form_claims(form) & TRACK_CLAIMS
    if k and s and k != s:
        out.append(_f(
            KRITIK, "konu_sonuc",
            f"KONU ile SONUÇ çelişiyor: KONU=[{_fmt(k)}] SONUÇ=[{_fmt(s)}].",
            "HMK m. 119: konu, açıklama ve sonuç aynı talep kümesi olmalı.",
            "talep",
        ))
    ghost = (a - s) & TRACK_CLAIMS
    if ghost:
        out.append(_f(
            KRITIK, "talep_tur",
            "Açıklamada SONUÇ'ta olmayan talep var: " + _fmt(ghost) + ".",
            "Açıklamalardaki her ana talep sonuçta ayrı yazılmalı.",
            "talep",
        ))
    extra_son = (s - (a | k | wanted)) & TRACK_CLAIMS
    if extra_son:
        out.append(_f(
            KRITIK, "talep_fazla",
            "SONUÇ'ta açıklamada desteklenmeyen yeni talep var: " + _fmt(extra_son) + ".",
            "",
            "talep",
        ))
    if wanted and s and (wanted - s):
        out.append(_f(
            YUKSEK, "talep_tur",
            "Formdaki kalem SONUÇ'ta yok: " + _fmt(wanted - s) + ".",
            "Seçilen / anlatılan dava türü ile sonuç uyumlu olmalı.",
            "talep",
        ))
    leftover_h = (h - (s | wanted | k)) & (LABOR_CLAIMS | FAMILY_CLAIMS)
    if leftover_h:
        out.append(_f(
            KRITIK, "dayanak_kalem",
            "Dayanak, istenmeyen kaleme uzanıyor: " + _fmt(leftover_h) + ".",
            "",
            "dayanak",
        ))
    if a and not d and secs.get("delil"):
        pass
    for need, extra, msg in JOINDER_RULES:
        pool = k | a | s | wanted
        if (need & pool) and (extra & pool):
            out.append(_f(YUKSEK, "joinder", msg, "Taleplerin birlikte ileri sürülmesi usulen ayrıca kontrol edilmelidir.", "usul"))
    son = secs.get("son") or ""
    if s and not re.search(r"(?i)yargılama gider|yek[aâ]let ücret", son):
        out.append(_f(ORTA, "sonuc_usul", "SONUÇ'ta yargılama gideri / vekâlet ücreti yok.", "", "usul"))
    money = bool(_TL_RE.search(son)) or bool(s & LABOR_CLAIMS)
    if money and not re.search(r"(?i)faiz", son):
        out.append(_f(ORTA, "faiz", "Para alacağı var; faiz türü / başlangıcı SONUÇ'ta yok.", "Her kaleme aynı faiz otomatik yazılmaz.", "faiz"))
    if (s & {"ucret", "fazla", "kira_alacak", "para_alacak"}) and not re.search(r"(?i)belirsiz alacak|HMK\s*m\.?\s*107", son + (secs.get("huk") or "")):
        if re.search(r"(?i)belirsiz|şimdilik|islah", intent_text(form) + son):
            out.append(_f(ORTA, "belirsiz", "Belirsiz alacak ifadesi zayıf; HMK m. 107 doğrulanmalı.", "", "talep"))
    return out


def _statute_findings(form: dict, secs: dict[str, str]) -> list[dict]:
    out: list[dict] = []
    huk = secs.get("huk") or ""
    active = (detect_claims(secs.get("son") or "") | form_claims(form)) & TRACK_CLAIMS
    for code, pat in STATUTE_FOR_CLAIM:
        if code in active:
            continue
        if re.search(pat, huk, re.I):
            out.append(_f(
                KRITIK if code in LABOR_CLAIMS or code in FAMILY_CLAIMS else YUKSEK,
                "dayanak_kalem",
                f"Dayanakta {_fmt({code})} maddesi var; bu kalem talep edilmiyor.",
                "MEVZUAT DOĞRULAMASI GEREKLİ — ilgisiz madde eklenmez.",
                "mevzuat",
            ))
    return out


def _evidence_findings(form: dict, secs: dict[str, str], text: str) -> list[dict]:
    out: list[dict] = []
    delil = (secs.get("delil") or "") + "\n" + (secs.get("ek") or "")
    acik = secs.get("acik") or ""
    blob = acik + "\n" + (text or "")
    for code, claim_re, ev_re, title in CLAIM_EVIDENCE:
        if re.search(claim_re, blob) and not re.search(ev_re, delil):
            out.append(_f(YUKSEK, "delil", f"{title} iddiası var; bunu destekleyen delil satırı yok.", "Delil yoksa uydurulmaz.", "delil"))
    if re.search(r"(?i)fazla (çalış|mesai)", blob) and re.search(r"(?i)banka|dekont", delil) and not re.search(r"(?i)puantaj|pdks|tanık", delil):
        out.append(_f(ORTA, "delil_analiz", "Banka dekontu ücret için anlamlı olabilir; fazla çalışma saatlerini tek başına kanıtlamaz.", "", "delil_vakia"))
    ek = secs.get("ek") or ""
    if delil and ek:
        d_items = [ln.strip() for ln in delil.splitlines() if len(ln.strip()) > 8]
        if d_items and not any(_fold(x)[:18] in _fold(ek) for x in d_items[:6]):
            out.append(_f(ORTA, "delil_ek", "DELİL/EK UYUMSUZLUĞU: deliller ile EKLER örtüşmeyebilir.", "", "delil"))
    seen_alias: set[str] = set()
    for key, pat in EVIDENCE_ALIASES:
        hits = re.findall(pat, delil, re.I)
        if len(hits) >= 2 and key not in seen_alias:
            seen_alias.add(key)
            out.append(_f(DUSUK, "delil_tekrar", f"Aynı belge farklı adlarla tekrar: {key}.", "", "delil"))
    return out


def _date_findings(text: str, secs: dict[str, str]) -> list[dict]:
    out: list[dict] = []
    dates = extract_dates((text or "") + "\n" + "\n".join(secs.values()))
    if len(dates) >= 2:
        ordered = dates
        for i in range(1, len(ordered)):
            prev, cur = ordered[i - 1], ordered[i]
            order = {"sozlesme": 1, "evlilik": 1, "islem": 2, "fesih": 3, "ihtar": 4, "teblig": 4, "arabulucu": 5}
            if prev["label"] in order and cur["label"] in order:
                if order[prev["label"]] < order[cur["label"]] and prev["date"] > cur["date"]:
                    out.append(_f(
                        KRITIK, "kronoloji",
                        f"Tarih sırası mantıksız: {prev['label']} {prev['raw']} → {cur['label']} {cur['raw']}.",
                        "SÜRE KONTROLÜ GEREKLİ. Eksikse süre uydurulmaz.",
                        "tarih",
                    ))
                    break
    by = {d["label"]: d for d in dates}
    if "fesih" in by and "arabulucu" in by:
        delta = (by["arabulucu"]["date"] - by["fesih"]["date"]).days
        if delta < 0:
            out.append(_f(KRITIK, "sure", "Arabuluculuk tarihi fesihten önce görünüyor.", "SÜRE KONTROLÜ GEREKLİ.", "sure"))
    if "fesih" in by and "ise_iade" in detect_claims(text or ""):
        out.append(_f(ORTA, "sure", "İşe iade için fesih tebliği–arabuluculuk–dava zinciri doğrulanmalı; süre hesabı uydurulmaz.", "", "sure"))
    return out


def _amount_findings(text: str, secs: dict[str, str]) -> list[dict]:
    out: list[dict] = []
    blob = (secs.get("acik") or "") + "\n" + (secs.get("son") or "")
    m_ay = re.search(r"(?i)(\d{1,3}(?:\.\d{3})+|\d+)\s*(?:TL|₺)[^\n]{0,40}?(\d{1,2})\s*ay", blob)
    if not m_ay:
        m_ay = re.search(r"(?i)(\d{1,2})\s*ay[^\n]{0,40}?(\d{1,3}(?:\.\d{3})+|\d+)\s*(?:TL|₺)", blob)
        if m_ay:
            ay, raw = int(m_ay.group(1)), m_ay.group(2)
            monthly = None
        else:
            ay, raw, monthly = None, None, None
    else:
        monthly = int(re.sub(r"[^\d]", "", m_ay.group(1)))
        ay = int(m_ay.group(2))
        raw = None
    if monthly and ay and monthly < 5_000_000:
        expect = monthly * ay
        totals = []
        for m in _TL_RE.finditer(blob):
            v = int(re.sub(r"[^\d]", "", m.group(1)))
            if v >= monthly:
                totals.append(v)
        if expect not in totals and any(abs(v - expect) > max(100, expect * 0.02) and abs(v - expect) < expect for v in totals):
            out.append(_f(KRITIK, "hesap", f"Aylık {monthly} TL × {ay} ay = {expect} TL ile metindeki toplam örtüşmeyebilir.", "Hesap uydurulmaz; çelişki raporlanır.", "hesap"))
    fold = _fold(blob)
    if "net" in fold and "brut" in fold:
        out.append(_f(ORTA, "netbrut", "Net / brüt / kesinti kavramları aynı metinde; karışıp karışmadığı kontrol edilmeli.", "", "hesap"))
    if re.search(r"(?i)kdv|stopaj|sgk\s*kesinti", blob) and re.search(r"(?i)ücret|kira|tazminat", blob):
        out.append(_f(DUSUK, "netbrut", "Vergi / kesinti ifadesi var; matrah ile talep tutarı karışmamalı.", "", "hesap"))
    return out


def _jurisdiction(form: dict, text: str) -> list[dict]:
    court = str((form or {}).get("court") or "")
    if not court:
        court = (text or "").splitlines()[0] if text else ""
    track = classify(form)["track"]
    spec = TRACKS.get(track) or {}
    hint = spec.get("court_hint") or ""
    if court and hint and not re.search(hint, _fold(court), re.I):
        return [_f(
            YUKSEK, "yetki",
            f"YETKİ/GÖREV KONTROLÜ GEREKLİ: mahkeme satırı ({court[:80]}) ile ön değerlendirme ({spec.get('label')}) örtüşmeyebilir.",
            "Kullanıcının yazdığı mahkeme gerekçesiz değiştirilmez.",
            "yetki",
        )]
    return []


def _procedure(form: dict, text: str, secs: dict[str, str]) -> list[dict]:
    out: list[dict] = []
    blob = _fold(intent_text(form) + "\n" + (text or ""))
    track = classify(form)["track"]
    spec = TRACKS.get(track) or {}
    for need in spec.get("procedure") or ():
        if need == "arabuluculuk":
            if "arabuluculuk" not in blob and "arabulucu" not in blob:
                out.append(_f(YUKSEK, "usul", "Bu türde arabuluculuk dava şartı olabilir; tutanak yok, numara uydurulmaz.", "", "on_sart"))
            elif re.search(r"arabulucu", blob) and not re.search(r"\d", blob):
                out.append(_f(ORTA, "usul", "Arabuluculuk anılmış; büro / tutanak no yok — uydurulmaz, [BİLGİ GİRİLMEDİ].", "", "on_sart"))
        if need == "ihtar" and "tahliye" in detect_claims(text or intent_text(form)) and not re.search(r"ihtar", blob):
            out.append(_f(YUKSEK, "usul", "Tahliye / temerrüt için ihtar bilgisi yok.", "", "on_sart"))
        if need == "sure" and track in ("idare", "vergi") and not _DATE_RE.search(intent_text(form)):
            out.append(_f(YUKSEK, "usul", "İdari / vergi davasında tebliğ-öğrenme tarihi yok; süre hesabı uydurulmaz.", "SÜRE KONTROLÜ GEREKLİ.", "sure"))
        if need == "hakem" and re.search(r"tuketici|tüketici", blob) and not re.search(r"hakem", blob):
            out.append(_f(ORTA, "usul", "Tüketici uyuşmazlığında hakem heyeti eşiği kontrol edilmeli.", "", "on_sart"))
    return out


def _contradictions(text: str) -> list[dict]:
    out: list[dict] = []
    t = text or ""
    fold = _fold(t)
    if re.search(r"sozlu fesih|fesih sozlu", fold) and re.search(r"yazili fesih|fesih bildirimi teblig", fold):
        out.append(_f(KRITIK, "celiski", "Bir yerde sözlü fesih, başka yerde yazılı fesih tebliği var.", "", "vakia"))
    if re.search(r"anlasmali bosan", fold) and re.search(r"cekismeli|kusur|aldat|siddet", fold):
        out.append(_f(YUKSEK, "celiski", "Anlaşmalı boşanma ile çekişmeli / kusur anlatımı yan yana.", "", "vakia"))
    paras = re.findall(r"(?m)^\s*\d{1,2}\.\s+(.{40,160})", t)
    norms = [_fold(p)[:80] for p in paras]
    if len(norms) >= 4 and len(set(norms)) <= max(2, len(norms) // 3):
        out.append(_f(ORTA, "vakia_tekrar", "Aynı vakıa farklı maddelerde gereksiz tekrarlanmış olabilir.", "Hukuken gerekli tekrar silinmez.", "vakia"))
    return out


def _hallucination(form: dict, text: str) -> list[dict]:
    out: list[dict] = []
    src = intent_text(form) + "\n" + str((form or {}).get("parties") or "")
    src_fold = _fold(src)
    for m in _TCKN_RE.finditer(text or ""):
        if m.group(1) not in src:
            out.append(_f(KRITIK, "uydurma", "Metinde TCKN var; kullanıcı kaynağında yok.", "Uydurma bilgi engeli.", "uydurma"))
            break
    for m in re.finditer(r"(?i)tanık\s+([A-ZÇĞİÖŞÜ][A-Za-zÇĞİÖŞÜçğıöşü]+(?:\s+[A-ZÇĞİÖŞÜ][A-Za-zÇĞİÖŞÜçğıöşü]+)+)", text or ""):
        if _fold(m.group(1)) not in src_fold:
            out.append(_f(KRITIK, "uydurma", f"Tanık adı ({m.group(1)}) kullanıcı metninde yok.", "", "uydurma"))
            break
    for m in _EK_RE.finditer(text or ""):
        key = m.group(1)
        if key not in src and "yargıtay" in _fold(text[max(0, m.start() - 30):m.end()]):
            pass
    for pat in PROMPT_LEAK:
        if re.search(pat, text or "", re.I):
            out.append(_f(KRITIK, "sizinti", "KRİTİK ÇIKTI HATASI: mahkeme metnine sistem / prompt sızıntısı girmiş.", "", "bicim"))
            break
    if re.search(r"(?i)kesinlikle (kötü niyet|kusurlu|haksız)", text or ""):
        out.append(_f(ORTA, "kesinlik", "Kanıtlanmamış olgu kesin gerçek gibi yazılmış olabilir.", "İleri sürülmektedir, dili tercih edilir.", "hukuki"))
    return out


def _cite_findings(text: str, memory: dict | None, form: dict) -> list[dict]:
    out: list[dict] = []
    mem = memory or {}
    known = " ".join(str(c) for c in (mem.get("cites") or []))
    for row in mem.get("aym") or []:
        if isinstance(row, dict):
            known += " " + str(row.get("kunye") or "")
    unverified = 0
    for m in _EK_RE.finditer(text or ""):
        if m.group(1) not in known:
            unverified += 1
    if unverified:
        out.append(_f(YUKSEK, "ictihat", f"{unverified} künye tarama hafızasında yok — İçtihat doğrulaması gereklidir.", "Karar uydurulmaz; ilgisiz içtihat eklenmez.", "ictihat"))
    claims = form_claims(form)
    huk = (
        section(text or "", "HUKUKİ SEBEPLER", "DELİLLER")
        or section(text or "", "HUKUKİ SEBEPLER", "SONUÇ VE İSTEM")
        or section(text or "", "HUKUKİ DAYANAKLAR", "SONUÇ VE İSTEM")
    )
    for ln in (huk or "").splitlines():
        if re.search(r"(?i)Yargıtay|Danıştay|AYM|E\.\s*\d{4}", ln) and not cite_fits_claims(ln, claims):
            out.append(_f(KRITIK, "ictihat", "Dayanaktaki içtihat istenmeyen kaleme ait.", "", "ictihat"))
            break
    return out


def _party_roles(form: dict, text: str) -> list[dict]:
    out: list[dict] = []
    davaci = str((form or {}).get("parties") or "")
    m = re.search(r"(?im)^Ad Soyad\s*[:：]\s*(.+)$", text or "")
    header = m.group(1).strip() if m else ""
    body_muv = re.search(
        r"(?i)müvekkil(?:im)?\s+([A-ZÇĞİÖŞÜ][A-Za-zÇĞİÖŞÜçğıöşü]+(?:\s+[A-ZÇĞİÖŞÜ][A-Za-zÇĞİÖŞÜçğıöşü]+){1,2})",
        text or "",
    )
    if header and body_muv:
        a = _fold(header.split()[0])
        b = _fold(body_muv.group(1).split()[0])
        if a and b and a != b and len(a) > 2:
            out.append(_f(KRITIK, "taraf", f"Taraf sıfatı / isim tutarsız: başlıkta {header}, gövdede {body_muv.group(1)}.", "BİLGİ TUTARSIZLIĞI.", "hukuki"))
    return out


def _chain_findings(form: dict, secs: dict[str, str]) -> list[dict]:
    out: list[dict] = []
    acik = secs.get("acik") or ""
    wanted = form_claims(form)
    for code in wanted & {"fazla", "ubgt", "hafta"}:
        if code not in detect_claims(acik) and code in detect_claims(secs.get("son") or ""):
            out.append(_f(YUKSEK, "zincir", f"{_fmt({code})} sonuçta var; vakıada somutlaştırılmamış.", "VAKIA SOMUTLAŞTIRMA EKSİKLİĞİ.", "vakia"))
        elif code in detect_claims(acik):
            if not re.search(r"\d{4}|\d{1,2}[./]\d{1,2}|saat|dönem", acik, re.I):
                out.append(_f(YUKSEK, "zincir", f"{_fmt({code})} anlatılmış; dönem / süre / düzen somut değil.", "VAKIA SOMUTLAŞTIRMA EKSİKLİĞİ.", "vakia"))
    return out


def _adversarial(findings: list[dict], secs: dict[str, str]) -> list[str]:
    notes: list[str] = []
    codes = {f["code"] for f in findings}
    if "talep_tur" in codes or "konu_sonuc" in codes:
        notes.append("Karşı taraf: dava türü ile sonuç fıkrası uyumsuz; talep reddi / ıslah tartışması açılabilir.")
    if "delil" in codes or "delil_analiz" in codes:
        notes.append("Karşı taraf: iddia somutlaştırılmamış / delil iddiayı tek başına ispatlamıyor.")
    if "zincir" in codes:
        notes.append("Hâkim: vakıa–hukuk–delil–talep zinciri kopuk; açıklama istenebilir.")
    if "sure" in codes or "usul" in codes:
        notes.append("Hâkim: dava şartı / süre yönünden dosya usulden incelenebilir.")
    if "uydurma" in codes:
        notes.append("Karşı taraf: metindeki sayı / tanık / künye dayanağı sorulabilir.")
    if not re.search(r"(?i)faiz", secs.get("son") or ""):
        notes.append("Hâkim: faiz türü ve başlangıcı hüküm için açık değil.")
    if not notes:
        notes.append("Belirgin zayıf nokta kural motorunda çıkmadı; bu mahkeme sonucu değildir.")
    return notes[:8]


def _personal(text: str) -> list[dict]:
    out: list[dict] = []
    if re.search(r"(?i)kimlik fotokopi|hesap no\s*[:：]\s*\d{8,}|iban\s*[:：]", text or ""):
        out.append(_f(ORTA, "kvkk", "Gereksiz kişisel veri / hesap ayrıntısı dilekçeye girmiş olabilir.", "", "kvkk"))
    return out


DIMS = (
    "hukuki", "usul", "vakia", "talep", "delil", "delil_vakia", "dayanak",
    "mevzuat", "ictihat", "tarih", "hesap", "faiz", "yetki", "on_sart",
    "kvkk", "bicim", "uydurma",
)

DIM_LABEL = {
    "hukuki": "Hukuki Tutarlılık",
    "usul": "Usul Uygunluğu",
    "vakia": "Vakıa Tutarlılığı",
    "talep": "Talep–Sonuç Uyumu",
    "delil": "Delil Yeterliliği",
    "delil_vakia": "Delil–Vakıa Uyumu",
    "dayanak": "Hukuki Dayanak Uyumu",
    "mevzuat": "Mevzuat Doğruluğu",
    "ictihat": "İçtihat Güvenilirliği",
    "tarih": "Tarih/Kronoloji",
    "hesap": "Tutar/Hesap Doğruluğu",
    "faiz": "Faiz Kontrolü",
    "yetki": "Yetki/Görev Kontrolü",
    "on_sart": "Usuli Ön Şartlar",
    "kvkk": "Kişisel Veri Kontrolü",
    "bicim": "Dil ve Biçim",
    "uydurma": "Uydurma Bilgi Riski",
}

CODE_DIM = {
    "konu_sonuc": "talep", "talep_tur": "talep", "talep_fazla": "talep", "talep_capraz": "talep",
    "belirsiz": "talep", "dayanak_kalem": "dayanak", "madde": "mevzuat", "mevzuat_graf": "mevzuat",
    "ictihat": "ictihat", "delil": "delil", "delil_analiz": "delil_vakia", "delil_ek": "delil",
    "delil_tekrar": "delil", "kronoloji": "tarih", "sure": "tarih", "hesap": "hesap",
    "netbrut": "hesap", "faiz": "faiz", "yetki": "yetki", "usul": "on_sart", "joinder": "usul",
    "sonuc_usul": "usul", "celiski": "vakia", "vakia_tekrar": "vakia", "zincir": "vakia",
    "uydurma": "uydurma", "sizinti": "bicim", "bicim": "bicim", "kesinlik": "hukuki",
    "taraf": "hukuki", "tutar": "hesap", "hagb": "hukuki", "kvkk": "kvkk", "zorunlu": "vakia",
    "cocuk": "hukuki",
}


def _subscores(findings: list[dict], text: str) -> dict[str, int]:
    score = {d: 100 for d in DIMS}
    for f in findings:
        dim = f.get("dim") or CODE_DIM.get(f.get("code") or "", "hukuki")
        if dim not in score:
            dim = "hukuki"
        if f.get("sev") == KRITIK:
            score[dim] -= 28
        elif f.get("sev") == YUKSEK:
            score[dim] -= 14
        elif f.get("sev") == ORTA:
            score[dim] -= 8
        else:
            score[dim] -= 3
    if not re.search(r"(?im)^DAVACI\b", text or ""):
        score["bicim"] -= 20
    if not re.search(r"(?im)^SONUÇ VE İSTEM\b", text or ""):
        score["bicim"] -= 15
    if re.search(r"(?i)müvekkil", text or ""):
        pass
    else:
        score["bicim"] -= 10
    return {k: max(0, min(100, v)) for k, v in score.items()}


def _overall(sub: dict[str, int], findings: list[dict]) -> int:
    w = {
        "hukuki": 8, "dayanak": 6, "mevzuat": 6,  # %20 hukuki doğruluk
        "usul": 8, "on_sart": 7,  # %15 usul
        "talep": 15,
        "vakia": 10,
        "delil": 6, "delil_vakia": 4,  # %10
        "ictihat": 4,  # mevzuat grubuna ek
        "tarih": 5,
        "hesap": 3, "faiz": 2,
        "yetki": 5,
        "bicim": 3, "kvkk": 1, "uydurma": 1,
    }
    # rebalance to 100
    total_w = sum(w.values())
    raw = sum(sub.get(k, 70) * w[k] for k in w)
    score = int(round(raw / total_w))
    if any(f.get("sev") == KRITIK for f in findings):
        score = min(score, 79)
    return max(0, min(100, score))


def analyze(form: dict, text: str = "", memory: dict | None = None, extra: list[dict] | None = None) -> dict[str, Any]:
    secs = split_sections(text or "")
    clf = classify(form)
    findings: list[dict] = list(extra or [])
    if (text or "").strip():
        findings.extend(_alignment(form, secs))
        findings.extend(_statute_findings(form, secs))
        findings.extend(_evidence_findings(form, secs, text))
        findings.extend(_date_findings(text, secs))
        findings.extend(_amount_findings(text, secs))
        findings.extend(_jurisdiction(form, text))
        findings.extend(_procedure(form, text, secs))
        findings.extend(_contradictions(text))
        findings.extend(_hallucination(form, text))
        findings.extend(_cite_findings(text, memory, form))
        findings.extend(_party_roles(form, text))
        findings.extend(_chain_findings(form, secs))
        findings.extend(_personal(text))
    seen: set[str] = set()
    uniq: list[dict] = []
    for f in findings:
        k = (f.get("code") or "") + "|" + (f.get("msg") or "")[:80]
        if k in seen:
            continue
        seen.add(k)
        uniq.append(f)
    sub = _subscores(uniq, text or "")
    score = _overall(sub, uniq)
    adv = _adversarial(uniq, secs) if (text or "").strip() else []
    questions = missing_questions(form, clf["track"])
    labeled = {DIM_LABEL[k]: v for k, v in sub.items()}
    crit = [f for f in uniq if f.get("sev") == KRITIK]
    return {
        "score": score,
        "subscores": labeled,
        "breakdown": {k: f"{v}/100" for k, v in labeled.items()},
        "findings": uniq,
        "classifier": clf,
        "questions": questions,
        "adversarial": adv,
        "ok": score >= 80 and not crit,
        "critical": bool(crit),
        "claims": {
            "form": sorted(form_claims(form)),
            "konu": sorted(detect_claims(secs.get("konu") or "")),
            "acik": sorted(detect_claims(_claim_scan(secs.get("acik") or ""))),
            "sonuc": sorted(detect_claims(secs.get("son") or "")),
        },
    }


def format_quality_report(rev: dict) -> str:
    score = int(rev.get("score") or 0)
    lines = [
        "—— HUKUKİ KALİTE RAPORU (dilekçe metnine yazılmaz) ——",
        f"GENEL PUAN: {score}/100",
    ]
    if rev.get("critical"):
        lines.append("Kritik hata mevcut — dil mükemmel olsa bile 90+ verilmez.")
    clf = rev.get("classifier") or {}
    if clf.get("note"):
        lines.append(clf["note"])
    br = rev.get("breakdown") or {}
    if br:
        lines.append("Puanlar: " + " · ".join(f"{k} {v}" for k, v in list(br.items())[:8]))
        rest = list(br.items())[8:]
        if rest:
            lines.append("         " + " · ".join(f"{k} {v}" for k, v in rest))
    by = {KRITIK: [], YUKSEK: [], ORTA: [], DUSUK: []}
    for f in rev.get("findings") or []:
        by.setdefault(f.get("sev") or ORTA, []).append(f)
    titles = (
        (KRITIK, "KIRMIZI Kritik hatalar"),
        (YUKSEK, "TURUNCU Önemli eksiklikler"),
        (ORTA, "SARI Kontrol edilmesi gerekenler"),
        (DUSUK, "Kontrol"),
    )
    for sev, title in titles:
        items = by.get(sev) or []
        if not items:
            continue
        lines.append(f"{title}:")
        for f in items[:10]:
            lines.append(f"- {f['msg']}")
            if f.get("hint"):
                lines.append(f"  ({f['hint']})")
    strong: list[str] = []
    if not by.get(KRITIK):
        strong.append("Kritik talep/sonuç çelişkisi bu taramada yok.")
    if int((rev.get("subscores") or {}).get("Tarih/Kronoloji") or 0) >= 85:
        strong.append("Tarih / kronoloji tutarlı görünüyor.")
    if int((rev.get("subscores") or {}).get("Dil ve Biçim") or 0) >= 85:
        strong.append("Biçim / dil yüzeyi temiz.")
    if strong:
        lines.append("YESIL Güçlü yönler:")
        lines.extend(f"- {s}" for s in strong)
    if rev.get("adversarial"):
        lines.append("Karşı taraf / hâkim perspektifi (simülasyon, mahkeme sonucu değildir):")
        lines.extend(f"- {x}" for x in rev["adversarial"][:6])
    if rev.get("questions"):
        lines.append("Kullanıcıya sorulacak (öncelikli, kısa):")
        lines.extend(f"- {q}" for q in rev["questions"][:6])
    lines.append(
        "Öncelik: doğruluk > usul > tutarlılık > delil > dayanak > açıklık > üslup. "
        "Eksik veri uydurulmaz."
    )
    return "\n".join(lines)


def format_preflight(form: dict, extra_lines: list[str] | None = None) -> str:
    clf = classify(form)
    qs = missing_questions(form, clf["track"])
    claims = claim_labels(form_claims(form))
    lines = [
        "Yazmadan önce — hukuki ön değerlendirme (kesin hüküm değildir).",
        clf["note"],
        "Talep envanteri (formdan): " + (", ".join(claims) if claims else "[BİLGİ GİRİLMEDİ]"),
    ]
    if extra_lines:
        lines.extend(extra_lines)
    if qs:
        lines.append("Eksik bilgi (cevap gelmese de üretim devam eder; uydurma yok):")
        lines.extend(f"- {q}" for q in qs)
    else:
        lines.append("Öncelikli soru matrisi boş; vakıa kartı ile üretim başlıyor.")
    lines.append("Mahkeme adı formda varsa gerekçesiz değiştirilmez.")
    return "\n".join(lines)
