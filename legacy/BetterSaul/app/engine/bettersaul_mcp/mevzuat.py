"""BetterSaul MCP — mevzuat.gov.tr resmi madde özeti. Olay / TCKN gönderilmez."""
from __future__ import annotations

import json
import re
from typing import Any

from .sources import _client, _dump, _plain

MEVZUAT = "https://www.mevzuat.gov.tr"
_ART_HEAD = re.compile(
    r"(?i)((?:Ek\s+)?(?:Geçici\s+)?Madde)\s+(\d+[A-Za-z]?)\s*"
    r"[-–—.]\s*(?:\((?:Değişik|Ek|Mülga)[^)]*\)\s*)?"
)
_LAW_CACHE: dict[str, str] = {}

# Kanun no / tür / tertip — yalnızca sık kullanılan kodlar.
CATALOG: dict[str, dict[str, Any]] = {
    "2709": {
        "no": "2709",
        "tur": 1,
        "tertip": 5,
        "ad": "Türkiye Cumhuriyeti Anayasası",
        "kisa": "Anayasa",
        "aliases": ("anayasa", "2709", "tc anayasası", "anayasa m"),
    },
    "2577": {
        "no": "2577",
        "tur": 1,
        "tertip": 5,
        "ad": "İdari Yargılama Usulü Kanunu",
        "kisa": "İYUK",
        "aliases": ("iyuk", "2577", "idari yargılama", "idari yargilama"),
    },
    "7315": {
        "no": "7315",
        "tur": 1,
        "tertip": 5,
        "ad": "Güvenlik Soruşturması ve Arşiv Araştırması Kanunu",
        "kisa": "7315",
        "aliases": ("7315", "güvenlik soruşturması", "guvenlik sorusturmasi", "arşiv araştırması", "arsiv arastirmasi"),
    },
    "4721": {
        "no": "4721",
        "tur": 1,
        "tertip": 5,
        "ad": "Türk Medeni Kanunu",
        "kisa": "TMK",
        "aliases": ("tmk", "4721", "medeni kanun", "boşanma"),
    },
    "4857": {
        "no": "4857",
        "tur": 1,
        "tertip": 5,
        "ad": "İş Kanunu",
        "kisa": "İş K.",
        "aliases": ("4857", "iş kanunu", "is kanunu", "iş k"),
    },
    "2004": {
        "no": "2004",
        "tur": 1,
        "tertip": 5,
        "ad": "İcra ve İflas Kanunu",
        "kisa": "İİK",
        "aliases": ("iik", "iİK", "2004", "icra ve iflas", "icra"),
    },
    "6502": {
        "no": "6502",
        "tur": 1,
        "tertip": 5,
        "ad": "Tüketicinin Korunması Hakkında Kanun",
        "kisa": "TKHK",
        "aliases": ("tkhk", "6502", "tüketici", "tuketici"),
    },
    "6100": {
        "no": "6100",
        "tur": 1,
        "tertip": 5,
        "ad": "Hukuk Muhakemeleri Kanunu",
        "kisa": "HMK",
        "aliases": ("hmk", "6100", "hukuk muhakemeleri"),
    },
    "5237": {
        "no": "5237",
        "tur": 1,
        "tertip": 5,
        "ad": "Türk Ceza Kanunu",
        "kisa": "TCK",
        "aliases": ("tck", "5237", "türk ceza"),
    },
    "5271": {
        "no": "5271",
        "tur": 1,
        "tertip": 5,
        "ad": "Ceza Muhakemesi Kanunu",
        "kisa": "CMK",
        "aliases": ("cmk", "5271", "ceza muhakemesi", "hagb"),
    },
    "7036": {
        "no": "7036",
        "tur": 1,
        "tertip": 5,
        "ad": "İş Mahkemeleri Kanunu",
        "kisa": "7036",
        "aliases": ("7036", "iş mahkemeleri", "is mahkemeleri", "arabuluculuk"),
    },
}


def _norm(s: str) -> str:
    t = (s or "").replace("İ", "i").replace("I", "i").replace("ı", "i")
    return re.sub(r"\s+", " ", t.lower()).strip()


def resolve_kanun(kanun: str) -> dict[str, Any] | None:
    q = _norm(kanun)
    if not q:
        return None
    q = re.sub(r"^(sayılı|sayili)\s+", "", q)
    q = re.sub(r"\s+(sayılı|sayili|s\.\s*k\.?|kanunu?)$", "", q)
    if q in CATALOG:
        return CATALOG[q]
    digits = re.search(r"\d{3,5}", q)
    if digits and digits.group(0) in CATALOG:
        return CATALOG[digits.group(0)]
    for item in CATALOG.values():
        names = [_norm(item["ad"]), _norm(item["kisa"]), *(_norm(a) for a in item["aliases"])]
        if q in names or any(q == a or a in q or q in a for a in names if len(a) >= 3):
            return item
    return None


def _iframe_url(item: dict[str, Any]) -> str:
    return (
        f"{MEVZUAT}/anasayfa/MevzuatFihristDetayIframe"
        f"?MevzuatTur={item['tur']}&MevzuatNo={item['no']}&MevzuatTertip={item['tertip']}"
    )


def _html_url(item: dict[str, Any]) -> str:
    return f"{MEVZUAT}/MevzuatMetin/{item['tur']}.{item['tertip']}.{item['no']}.html"


def _law_plain(html: str) -> str:
    t = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", html or "")
    t = re.sub(r"(?i)<br\s*/?>|</(p|div|tr|h\d|li|dt|dd)>", "\n", t)
    t = _plain(t)
    return t


def _fetch_law_text(item: dict[str, Any]) -> str:
    key = f"{item['tur']}.{item['tertip']}.{item['no']}"
    cached = _LAW_CACHE.get(key)
    if cached:
        return cached
    last = ""
    with _client(MEVZUAT) as http:
        http.headers["Accept"] = "text/html,application/xhtml+xml,*/*"
        for url in (_iframe_url(item), _html_url(item)):
            try:
                res = http.get(url)
                last = f"HTTP {res.status_code}"
                if res.status_code >= 400:
                    continue
                text = _law_plain(res.text)
                if len(text) < 200:
                    continue
                if re.search(r"(?i)bulunamadı|mevzuat bulunamadı|hata oluştu", text):
                    continue
                _LAW_CACHE[key] = text
                return text
            except Exception as exc:
                last = "HATA: " + str(exc)
    return last if last else ""


def _article_no(madde: str) -> str:
    t = (madde or "").strip()
    t = re.sub(r"(?i)^(m(adde)?\.?\s*)", "", t).strip()
    m = re.search(r"(\d+[A-Za-z]?)", t)
    return m.group(1) if m else ""


def _cut_article(law: str, no: str) -> str:
    if not law or not no:
        return ""
    hits = list(_ART_HEAD.finditer(law))
    if not hits:
        loose = re.search(
            rf"(?i)Madde\s+{re.escape(no)}\s*[-–—.].{{0,2400}}",
            law,
        )
        return re.sub(r"\s+", " ", (loose.group(0) if loose else "")).strip()
    for i, m in enumerate(hits):
        if m.group(2).lower() == no.lower() and "geçici" not in m.group(1).lower():
            start = m.start()
            end = hits[i + 1].start() if i + 1 < len(hits) else min(len(law), start + 2400)
            return re.sub(r"\s+", " ", law[start:end]).strip()
    for i, m in enumerate(hits):
        if m.group(2).lower() == no.lower():
            start = m.start()
            end = hits[i + 1].start() if i + 1 < len(hits) else min(len(law), start + 2400)
            return re.sub(r"\s+", " ", law[start:end]).strip()
    return ""


def _summarize(text: str, limit: int = 800) -> str:
    t = re.sub(r"\s+", " ", text or "").strip()
    if len(t) <= limit:
        return t
    cut = t[: limit - 1]
    if "." in cut[200:]:
        cut = cut.rsplit(".", 1)[0] + "."
    return cut.rstrip() + "…"


def _label(item: dict[str, Any], no: str) -> str:
    short = item.get("kisa") or item["no"]
    if short in {"Anayasa", "İYUK", "TMK", "İİK", "TKHK", "HMK", "TCK", "CMK"}:
        return f"{short} m. {no}"
    if item["no"] in {"7315", "7036", "4857"}:
        return f"{item['no']} sayılı Kanun m. {no}"
    return f"{item['ad']} m. {no}"


def list_mevzuat_catalog() -> str:
    rows = [
        {
            "kanun": item["no"],
            "ad": item["ad"],
            "kisa": item["kisa"],
            "tur": item["tur"],
            "tertip": item["tertip"],
        }
        for item in CATALOG.values()
    ]
    return _dump({"kaynak": "mevzuat.gov.tr", "katalog": rows})


def search_mevzuat(query: str) -> str:
    q = _norm(query)
    if not q:
        return _dump({"error": "Arama ifadesi boş.", "sonuc": "yok, uydurma"})
    hits: list[dict[str, Any]] = []
    for item in CATALOG.values():
        blob = " ".join([item["no"], item["ad"], item["kisa"], *item["aliases"]])
        score = 0
        if q == _norm(item["no"]) or q == _norm(item["kisa"]):
            score = 100
        elif q in _norm(blob):
            score = 80
        elif any(_norm(a) in q or q in _norm(a) for a in item["aliases"] if len(_norm(a)) >= 4):
            score = 70
        if score:
            hits.append({"kanun": item["no"], "ad": item["ad"], "kisa": item["kisa"], "skor": score})
    hits.sort(key=lambda x: -int(x["skor"]))
    if not hits:
        return _dump({"kaynak": "mevzuat.gov.tr", "query": query, "sonuc": "yok, uydurma", "kayitlar": []})
    return _dump({"kaynak": "mevzuat.gov.tr", "query": query, "kayitlar": hits[:8]})


def get_mevzuat_article(kanun: str, madde: str) -> str:
    item = resolve_kanun(kanun)
    no = _article_no(madde)
    if not item or not no:
        return _dump({"ok": False, "sonuc": "yok, uydurma", "kanun": kanun, "madde": madde})
    law = _fetch_law_text(item)
    if not law or law.startswith(("HTTP ", "HATA:")) or len(law) < 80:
        return _dump(
            {
                "ok": False,
                "sonuc": "yok, uydurma",
                "kanun": item["no"],
                "madde": no,
                "neden": law or "metin alınamadı",
            }
        )
    body = _cut_article(law, no)
    if len(body) < 40:
        return _dump(
            {
                "ok": False,
                "sonuc": "yok, uydurma",
                "kanun": item["no"],
                "madde": no,
                "label": _label(item, no),
                "neden": "madde metni ayrıştırılamadı",
            }
        )
    return _dump(
        {
            "ok": True,
            "kaynak": "mevzuat.gov.tr",
            "kanun": item["no"],
            "ad": item["ad"],
            "label": _label(item, no),
            "madde": no,
            "ozet": _summarize(body, 800),
        }
    )


def default_pulls(form: dict | None) -> list[tuple[str, str]]:
    """Tür → çekilecek (kanun, madde). Olay metni dışarı gitmez."""
    form = form or {}
    ptype = str(form.get("petitionType") or "")
    blob = " ".join(
        str(form.get(k) or "")
        for k in ("caseSummary", "userPrompt", "extraInstructions", "requests", "title", "petitionType")
    )
    out: list[tuple[str, str]] = []
    if "İdare" in ptype:
        out = [("2577", "2"), ("2577", "3"), ("2577", "7"), ("2709", "36"), ("2709", "40"), ("2709", "70")]
        if re.search(r"(?i)yürütme[yi]\s+durdur|ivedi|yd\b|m\.\s*27", blob):
            out.append(("2577", "27"))
        if re.search(r"(?i)7315|güvenlik soruştur|arşiv araştırm", blob):
            out.extend(
                [
                    ("2709", "2"),
                    ("2709", "20"),
                    ("2709", "38"),
                    ("2709", "125"),
                    ("7315", "1"),
                    ("7315", "3"),
                    ("7315", "4"),
                    ("7315", "5"),
                ]
            )
        if re.search(r"(?i)HAGB|hükmün açıklanmasının geri", blob):
            out.append(("5271", "231"))
        if re.search(r"(?i)adli\s+yard[ıi]m", blob):
            out.append(("6100", "334"))
        return out
    if "Boşanma" in ptype:
        out = [("4721", "166"), ("4721", "174"), ("4721", "175"), ("4721", "182"), ("4721", "185")]
        if re.search(r"(?i)\b164\b|terk\b", blob):
            out.insert(0, ("4721", "164"))
        return out
    if "İş" in ptype:
        return [("4857", "32"), ("4857", "34"), ("7036", "3"), ("7036", "5")]
    if "İcra" in ptype:
        return [("2004", "67")]
    if "Tüketici" in ptype:
        return [("6502", "8"), ("6502", "11")]
    if "Ceza" in ptype and re.search(r"(?i)HAGB|hükmün açıklanmasının geri", blob):
        return [("5271", "231")]
    return out


def parse_article_json(raw: str) -> dict[str, Any]:
    try:
        data = json.loads(raw or "")
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}
