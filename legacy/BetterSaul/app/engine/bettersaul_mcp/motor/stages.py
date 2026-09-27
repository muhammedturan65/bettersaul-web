"""Qwen dilekçe hattı: çıkar → yaz → kontrol et → düzelt. Puan üretmez."""
from __future__ import annotations

import json
import re
from typing import Any

CASE_KEYS = (
    "davaci",
    "davali",
    "vekil",
    "mahkeme",
    "dava_turu",
    "olaylar",
    "talepler",
    "tarihler",
    "deliller",
    "hukuki_sebepler",
    "eksik",
)

CHECK_KEYS = (
    "talep_var",
    "sonucta_var",
    "aciklamada_destek",
    "delil_var",
    "tarih_celiskisi",
    "hukuki_sebep_uygun",
    "eksik_bilgi",
    "duzeltilecekler",
)


def empty_case() -> dict[str, Any]:
    return {
        "davaci": {"ad": "", "tckn": "", "adres": ""},
        "davali": {"ad": "", "tckn": "", "adres": ""},
        "vekil": {"ad": "", "baro": "", "sicil": "", "adres": ""},
        "mahkeme": "",
        "dava_turu": "",
        "olaylar": [],
        "talepler": [],
        "tarihler": [],
        "deliller": [],
        "hukuki_sebepler": [],
        "eksik": [],
    }


def empty_report() -> dict[str, Any]:
    return {
        "talep_var": False,
        "sonucta_var": False,
        "aciklamada_destek": False,
        "delil_var": False,
        "tarih_celiskisi": False,
        "hukuki_sebep_uygun": False,
        "eksik_bilgi": [],
        "duzeltilecekler": [],
    }


def _first_json(text: str) -> Any:
    raw = text or ""
    raw = re.sub(r"(?is)^```(?:json)?\s*|\s*```$", "", raw.strip())
    dec = json.JSONDecoder()
    for i, ch in enumerate(raw):
        if ch in "{[":
            try:
                obj, _ = dec.raw_decode(raw, i)
                return obj
            except Exception:
                continue
    return None


def _party(obj: Any) -> dict[str, str]:
    if isinstance(obj, str):
        return {"ad": obj.strip(), "tckn": "", "adres": ""}
    if not isinstance(obj, dict):
        return {"ad": "", "tckn": "", "adres": ""}
    return {
        "ad": str(obj.get("ad") or obj.get("unvan") or obj.get("ad_soyad") or "").strip(),
        "tckn": str(obj.get("tckn") or obj.get("tc") or "").strip(),
        "adres": str(obj.get("adres") or "").strip(),
    }


def _str_list(obj: Any) -> list[str]:
    if isinstance(obj, str) and obj.strip():
        return [obj.strip()]
    if not isinstance(obj, list):
        return []
    out: list[str] = []
    for x in obj:
        if isinstance(x, dict):
            t = str(x.get("metin") or x.get("olay") or x.get("talep") or x.get("tarih") or x.get("ad") or "").strip()
        else:
            t = str(x or "").strip()
        if t and t not in out:
            out.append(t)
    return out


def parse_case_json(text: str) -> dict[str, Any]:
    obj = _first_json(text)
    base = empty_case()
    if not isinstance(obj, dict):
        return base
    base["davaci"] = _party(obj.get("davaci"))
    base["davali"] = _party(obj.get("davali"))
    vek = obj.get("vekil")
    if isinstance(vek, dict):
        base["vekil"] = {
            "ad": str(vek.get("ad") or "").strip(),
            "baro": str(vek.get("baro") or "").strip(),
            "sicil": str(vek.get("sicil") or "").strip(),
            "adres": str(vek.get("adres") or "").strip(),
        }
    elif isinstance(vek, str):
        base["vekil"]["ad"] = vek.strip()
    base["mahkeme"] = str(obj.get("mahkeme") or "").strip()
    base["dava_turu"] = str(obj.get("dava_turu") or obj.get("tur") or "").strip()
    base["olaylar"] = _str_list(obj.get("olaylar"))
    base["talepler"] = _str_list(obj.get("talepler"))
    base["tarihler"] = _str_list(obj.get("tarihler"))
    base["deliller"] = _str_list(obj.get("deliller"))
    base["hukuki_sebepler"] = _str_list(obj.get("hukuki_sebepler") or obj.get("hukuki"))
    base["eksik"] = _str_list(obj.get("eksik") or obj.get("eksik_bilgiler"))
    return base


def parse_check_report(text: str) -> dict[str, Any]:
    obj = _first_json(text)
    base = empty_report()
    if not isinstance(obj, dict):
        return base

    def yn(key: str, default: bool = False) -> bool:
        v = obj.get(key)
        if isinstance(v, bool):
            return v
        s = str(v or "").strip().lower()
        if s in {"1", "true", "evet", "var", "uygun", "destekleniyor"}:
            return True
        if s in {"0", "false", "hayir", "hayır", "yok", "uygunsuz"}:
            return False
        return default

    base["talep_var"] = yn("talep_var")
    base["sonucta_var"] = yn("sonucta_var")
    base["aciklamada_destek"] = yn("aciklamada_destek")
    base["delil_var"] = yn("delil_var")
    base["tarih_celiskisi"] = yn("tarih_celiskisi")
    base["hukuki_sebep_uygun"] = yn("hukuki_sebep_uygun", True)
    base["eksik_bilgi"] = _str_list(obj.get("eksik_bilgi") or obj.get("eksik"))
    base["duzeltilecekler"] = _str_list(obj.get("duzeltilecekler") or obj.get("duzelt"))
    return base


def case_brief(case: dict[str, Any]) -> str:
    d = case.get("davaci") or {}
    v = case.get("davali") or {}
    vek = case.get("vekil") or {}
    lines = [
        f"Davacı: {d.get('ad') or '[yok]'} | TCKN: {d.get('tckn') or '[yok]'} | Adres: {d.get('adres') or '[yok]'}",
        f"Davalı: {v.get('ad') or '[yok]'} | TCKN: {v.get('tckn') or '[yok]'} | Adres: {v.get('adres') or '[yok]'}",
        f"Vekil: {vek.get('ad') or '[yok]'} | {vek.get('baro') or ''} {vek.get('sicil') or ''}".strip(),
        f"Mahkeme: {case.get('mahkeme') or '[yok]'}",
        f"Dava türü: {case.get('dava_turu') or '[yok]'}",
        "Olaylar:",
        *[f"- {x}" for x in (case.get("olaylar") or [])[:12] or ["[yok]"]],
        "Talepler:",
        *[f"- {x}" for x in (case.get("talepler") or [])[:10] or ["[yok]"]],
        "Tarihler:",
        *[f"- {x}" for x in (case.get("tarihler") or [])[:10] or ["[yok]"]],
        "Deliller:",
        *[f"- {x}" for x in (case.get("deliller") or [])[:10] or ["[yok]"]],
        "Hukuki sebepler:",
        *[f"- {x}" for x in (case.get("hukuki_sebepler") or [])[:8] or ["[yok]"]],
        "Eksik (doldurma, uydurma):",
        *[f"- {x}" for x in (case.get("eksik") or [])[:8] or ["[yok]"]],
    ]
    return "\n".join(lines)


def merge_case_into_form(form: dict, case: dict[str, Any]) -> dict:
    f = dict(form or {})
    d = case.get("davaci") or {}
    v = case.get("davali") or {}
    if (d.get("ad") or v.get("ad")) and not str(f.get("parties") or "").strip():
        bits = []
        if d.get("ad"):
            bits.append("DAVACI\nAd Soyad : " + d["ad"])
            if d.get("tckn"):
                bits.append("T.C. Kimlik No : " + d["tckn"])
            if d.get("adres"):
                bits.append("Adres : " + d["adres"])
        if v.get("ad"):
            bits.append("DAVALI\nAd Soyad : " + v["ad"])
            if v.get("tckn"):
                bits.append("T.C. Kimlik No : " + v["tckn"])
            if v.get("adres"):
                bits.append("Adres : " + v["adres"])
        f["parties"] = "\n".join(bits)
    if case.get("mahkeme") and not str(f.get("court") or "").strip():
        f["court"] = str(case["mahkeme"])
    if case.get("dava_turu") and not str(f.get("petitionType") or "").strip():
        f["petitionType"] = str(case["dava_turu"])
    olay = " ".join(case.get("olaylar") or [])
    if olay and not str(f.get("caseSummary") or "").strip():
        f["caseSummary"] = olay[:2200]
    if case.get("talepler") and not str(f.get("requests") or "").strip():
        f["requests"] = "\n".join(case["talepler"])
    vek = case.get("vekil") or {}
    if vek.get("ad") and not str(f.get("lawyerName") or "").strip():
        f["lawyerName"] = vek["ad"]
    f["_case"] = case
    return f


def case_from_model(model: dict[str, Any], form: dict | None = None) -> dict[str, Any]:
    c = empty_case()
    form = form or {}
    c["davaci"]["ad"] = str(model.get("davaci") or "")
    c["davali"]["ad"] = str(model.get("davali") or "")
    c["vekil"]["ad"] = str(model.get("vekil") or form.get("lawyerName") or "")
    c["mahkeme"] = str(model.get("mahkeme") or form.get("court") or "")
    c["dava_turu"] = str(model.get("dava_turu") or form.get("petitionType") or "")
    olay = str(model.get("olaylar") or form.get("caseSummary") or "").strip()
    c["olaylar"] = [x.strip() for x in re.split(r"(?<=[.!?])\s+", olay) if x.strip()][:12]
    req = str(model.get("talepler") or form.get("requests") or "").strip()
    c["talepler"] = [x.strip() for x in re.split(r"[\n;]+", req) if x.strip()][:10]
    c["deliller"] = [x.strip() for x in re.split(r"[\n;]+", str(model.get("deliller") or "")) if x.strip()][:10]
    c["hukuki_sebepler"] = [x.strip() for x in re.split(r"[\n;]+", str(model.get("hukuki") or "")) if x.strip()][:8]
    return c


def fact_messages(raw: str) -> list[dict]:
    return [
        {
            "role": "system",
            "content": (
                "Veriyi yapılandır. Dilekçe yazma. Puanlama, eleştiri, tutarlılık yok. "
                "Yalnızca JSON döndür. Bilinmeyeni boş bırak; uydurma."
            ),
        },
        {
            "role": "user",
            "content": (
                "Şu anahtarlarla JSON yaz: davaci{ad,tckn,adres}, davali{ad,tckn,adres}, "
                "vekil{ad,baro,sicil,adres}, mahkeme, dava_turu, olaylar[], talepler[], "
                "tarihler[], deliller[], hukuki_sebepler[], eksik[].\n\n"
                "Metin:\n"
                + (raw or "")[:3500]
            ),
        },
    ]


def generate_messages(
    brief: str,
    outline: str,
    cites: list[str],
    hukuki: str,
    court: str = "",
    banner: str = "",
) -> list[dict]:
    cite_block = "\n".join(cites[:6]) if cites else "Künye yok; numara yazma."
    head = (court or "").strip()
    if (banner or "").strip():
        head = (head + "\n\n" + banner.strip()).strip()
    return [
        {
            "role": "system",
            "content": (
                "Yalnızca dilekçe yaz. Tutarsızlık kontrolü yok. Puanlama yok. "
                "Eleştiri yok. Promptu tekrar etme. JSON, soru, sistem metni yazma. "
                "Gövde: müvekkil. Başlık: DAVACI. Yeni isim, TCKN, tutar, tarih, künye uydurma. "
                "İlk satırlar: T.C. / mahkeme / baner / DAVA DİLEKÇESİ. Bunları silme."
            ),
        },
        {
            "role": "user",
            "content": (
                "İlk satırlar (aynen yaz):\n"
                f"{head or '[mahkeme satırı]'}\n\n"
                "Yapılandırılmış dosya:\n"
                f"{brief}\n\n"
                f"Açıklama iskeleti:\n{outline}\n\n"
                f"Hukuki dayanak (aynen kullan, künye ekleme):\n{hukuki}\n\n"
                f"İçtihat (yalnızca bunlar; yoksa yazma):\n{cite_block}\n\n"
                "Sıra: T.C. / mahkeme / birleşik baner / DAVA DİLEKÇESİ / tür satırı / "
                "DAVACI / VEKİLİ / DAVALI / KONU / "
                "AÇIKLAMALAR (1- 2- 3-; her vakıada Delil / Hukuki dayanak / Hukuki sonuç) / "
                "HUKUKİ SEBEPLER / DELİLLER / SONUÇ VE İSTEM / tarih / Davacı Vekili / EKLER.\n"
                "T.C. ve DAVA DİLEKÇESİ yaz. Mahkeme satırı ve baner zorunlu. "
                "Yanıtın tamamı dilekçe olsun."
            ),
        },
    ]


def check_messages(brief: str, petition: str) -> list[dict]:
    return [
        {
            "role": "system",
            "content": (
                "Kalite kontrol. Dilekçe yazma. Puan yazma. Prompt tekrar etme. "
                "Yalnızca JSON."
            ),
        },
        {
            "role": "user",
            "content": (
                "Dosya:\n"
                f"{brief}\n\n"
                "Dilekçe:\n"
                f"{(petition or '')[:7000]}\n\n"
                "Şu soruları yanıtla (JSON):\n"
                "talep_var, sonucta_var, aciklamada_destek, delil_var, "
                "tarih_celiskisi, hukuki_sebep_uygun, eksik_bilgi[], duzeltilecekler[]."
            ),
        },
    ]


def repair_messages(brief: str, petition: str, report: dict[str, Any]) -> list[dict]:
    fixes = report.get("duzeltilecekler") or report.get("eksik_bilgi") or []
    return [
        {
            "role": "system",
            "content": (
                "Sadece düzelt. Kontrol raporundaki maddeleri dilekçede gider. "
                "Yeni bilgi uydurma. Dilekçe dışına çıkma. Puan, eleştiri, JSON yok. "
                "Mahkeme satırı ve — baner — satırını silme."
            ),
        },
        {
            "role": "user",
            "content": (
                "Dosya (uydurma kaynağı değil; yalnızca var olanı koru):\n"
                f"{brief}\n\n"
                "Düzeltilecekler:\n"
                + ("\n".join(f"- {x}" for x in fixes[:10]) or "- (rapordaki hayır/çelişki satırları)")
                + "\n\nDilekçe:\n"
                + (petition or "")[:8000]
                + "\n\nYalnızca düzeltilmiş dilekçeyi yaz."
            ),
        },
    ]


def needs_repair(report: dict[str, Any]) -> bool:
    if report.get("tarih_celiskisi"):
        return True
    if report.get("duzeltilecekler"):
        return True
    if not report.get("talep_var"):
        return True
    if not report.get("sonucta_var"):
        return True
    if not report.get("aciklamada_destek"):
        return True
    if not report.get("hukuki_sebep_uygun"):
        return True
    return False


def format_check_report(report: dict[str, Any]) -> str:
    def yn(v: bool) -> str:
        return "Evet" if v else "Hayır"

    lines = [
        "Kalite kontrol (puan yok):",
        f"- Talep var mı? {yn(bool(report.get('talep_var')))}",
        f"- Sonuç kısmında var mı? {yn(bool(report.get('sonucta_var')))}",
        f"- Açıklamada destekleniyor mu? {yn(bool(report.get('aciklamada_destek')))}",
        f"- Delili var mı? {yn(bool(report.get('delil_var')))}",
        f"- Tarih çelişkisi var mı? {yn(bool(report.get('tarih_celiskisi')))}",
        f"- Hukuki sebep uyuyor mu? {yn(bool(report.get('hukuki_sebep_uygun')))}",
    ]
    eksik = report.get("eksik_bilgi") or []
    if eksik:
        lines.append("Eksik bilgi:")
        lines.extend(f"- {x}" for x in eksik[:8])
    fixes = report.get("duzeltilecekler") or []
    if fixes:
        lines.append("Düzeltilecekler:")
        lines.extend(f"- {x}" for x in fixes[:8])
    return "\n".join(lines)
