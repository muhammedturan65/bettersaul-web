"""BetterSaul MCP — resmi kamu karar/arama sitelerine doğrudan HTTP."""
from __future__ import annotations

import json
import re
import time
from datetime import date, datetime, timedelta
from typing import Any
from urllib.parse import urljoin

import httpx

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)
YARGITAY = "https://karararama.yargitay.gov.tr"
EMSAL = "https://emsal.uyap.gov.tr"
DANISTAY = "https://karararama.danistay.gov.tr"
RG = "https://www.resmigazete.gov.tr"
COURT_YARGITAY = ["YARGITAYKARARI"]
COURT_EMSAL = ["YERELHUKUK", "ISTINAFHUKUK", "KYB"]
COURT_DANISTAY = ["DANISTAYKARAR"]
_DOC_HINTS: dict[str, tuple[str, str]] = {}
_LIMITED_UNTIL = 0.0
_COURT_LOCK = ""
_LOCK_AT = 0.0
_YARGITAY_MARK = re.compile(
    r"Yarg[ıi]tay|Asliye\s+Ticaret|Ticaret\s+Mahkeme|\d+\.\s*Hukuk\s+Dairesi|Ceza\s+Dairesi",
    re.I,
)
_STOP_WORDS = {
    "danistay",
    "danıştay",
    "yargitay",
    "yargıtay",
    "emsal",
    "karar",
    "kararı",
    "dava",
    "davasi",
    "davası",
    "ile",
    "icin",
    "için",
    "veya",
    "gibi",
    "olan",
    "olarak",
    "uzerine",
    "üzerine",
}


_VERIFY = None


def _verify_ctx():
    """Sistem sertifika deposu (truststore) + certifi yedeği.

    Bazı kamu siteleri (mevzuat.gov.tr, resmigazete.gov.tr) ara sertifika
    zincirini eksik gönderir; certifi tek başına doğrulayamaz. İşletim
    sisteminin deposu eksik zinciri tamamlayabildiğinden önce o denenir.
    """
    global _VERIFY
    if _VERIFY is not None:
        return _VERIFY
    try:
        import ssl

        import truststore

        _VERIFY = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    except Exception:
        _VERIFY = True
    return _VERIFY


def _client(base: str | None = None) -> httpx.Client:
    headers = {
        "User-Agent": UA,
        "Accept": "application/json, text/javascript, text/html, */*; q=0.8",
        "X-Requested-With": "XMLHttpRequest",
    }
    if base:
        headers["Origin"] = base
        headers["Referer"] = base.rstrip("/") + "/"
    return httpx.Client(
        timeout=httpx.Timeout(28.0, connect=10.0),
        follow_redirects=True,
        headers=headers,
        verify=_verify_ctx(),
    )


def _dump(obj: Any, limit: int = 14000) -> str:
    text = json.dumps(obj, ensure_ascii=False, indent=2) if not isinstance(obj, str) else obj
    return text if len(text) <= limit else text[:limit] + "\n…"


def _plain(html: str) -> str:
    html = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", html or "")
    html = re.sub(r"(?is)<svg\b.*?</svg>", " ", html)
    html = re.sub(r"(?s)<[^>]+>", " ", html)
    html = re.sub(r"&nbsp;|&amp;|&quot;|&#39;", " ", html)
    text = re.sub(r"\s+", " ", html).strip()
    if re.search(
        r"image/svg|svg\+xml|böyle bir içerik mevcut değildir|"
        r"Bilgi İşlem Genel Müdürlüğü|Uygulama içerisinde böyle bir içerik|"
        r"(?:HTTP\s+)?404(?:\s+Uygulama|\s+Not Found|\s+Sayfa)|"
        r"Erişim Sınırı Aşıldı",
        text,
        re.I,
    ):
        return ""
    return text


def _as_dict(data: Any) -> dict[str, Any]:
    return data if isinstance(data, dict) else {"raw": data}


def _rows_from(data: dict[str, Any]) -> tuple[list[dict[str, Any]], int]:
    blob = data.get("data") if isinstance(data.get("data"), dict) else data
    hits = (
        blob.get("data")
        or blob.get("records")
        or blob.get("content")
        or blob.get("items")
        or blob.get("decisions")
        or data.get("data")
        or []
    )
    if isinstance(hits, dict):
        hits = hits.get("records") or hits.get("content") or hits.get("items") or []
    if not isinstance(hits, list):
        hits = []
    rows: list[dict[str, Any]] = []
    for item in hits[:60]:
        if not isinstance(item, dict):
            continue
        ozet = (
            item.get("ozet")
            or item.get("kararOzeti")
            or item.get("ozetMetin")
            or item.get("aciklama")
            or item.get("kararOzet")
            or item.get("snippet")
            or ""
        )
        if not isinstance(ozet, str):
            ozet = str(ozet or "")
        rows.append(
            {
                "documentId": item.get("id") or item.get("documentId") or item.get("kararId"),
                "birimAdi": item.get("daireKurul")
                or item.get("daire")
                or item.get("birimAdi")
                or item.get("mahkeme"),
                "esasNo": item.get("esasNo") or item.get("esas") or (
                    f"{item.get('esasNoYil')}/{item.get('esasNoSira')}"
                    if item.get("esasNoYil") not in (None, "") and item.get("esasNoSira") not in (None, "")
                    else ""
                ),
                "kararNo": item.get("kararNo") or item.get("karar") or (
                    f"{item.get('kararNoYil')}/{item.get('kararNoSira')}"
                    if item.get("kararNoYil") not in (None, "") and item.get("kararNoSira") not in (None, "")
                    else ""
                ),
                "kararTarihi": item.get("kararTarihiStr") or item.get("kararTarihi") or item.get("tarih"),
                "baslik": item.get("baslik") or item.get("title") or item.get("kurum"),
                "ozet": _plain(ozet)[:420] if ozet else "",
            }
        )
    total = blob.get("recordsTotal") or blob.get("total") or blob.get("toplam") or len(rows)
    try:
        total = int(total)
    except (TypeError, ValueError):
        total = len(rows)
    return rows, total


def _rate_limited(res: httpx.Response) -> bool:
    if res.status_code == 429:
        return True
    return bool(re.search(r"Erişim Sınırı Aşıldı|erisim siniri", res.text or "", re.I))


def _mark_limited(seconds: float = 50.0) -> None:
    global _LIMITED_UNTIL
    _LIMITED_UNTIL = time.time() + seconds


def _is_cooling() -> bool:
    return time.time() < _LIMITED_UNTIL


def _remember_docs(base: str, phrase: str, rows: list[dict[str, Any]]) -> None:
    for item in rows:
        doc_id = str(item.get("documentId") or "").strip()
        if doc_id:
            _DOC_HINTS[doc_id] = (base, phrase)


def _apply_court_lock(court_types: list[str] | None) -> None:
    global _COURT_LOCK, _LOCK_AT
    courts = [str(c).upper() for c in (court_types or [])]
    if courts and all("DANISTAY" in c for c in courts):
        _COURT_LOCK = "danistay"
        _LOCK_AT = time.time()
    elif courts and all("YARGITAY" in c or c == "YARGITAYKARARI" for c in courts):
        _COURT_LOCK = "yargitay"
        _LOCK_AT = time.time()


def _active_lock() -> str:
    if time.time() - _LOCK_AT > 1800:
        return ""
    return _COURT_LOCK


def _tokens(phrase: str) -> list[str]:
    words = re.findall(r"[A-Za-zÇĞİÖŞÜçğıöşü0-9]{3,}", phrase or "")
    out: list[str] = []
    for w in words:
        fold = w.replace("İ", "i").replace("I", "i").lower()
        if fold in _STOP_WORDS or w in out:
            continue
        out.append(w)
        if len(out) >= 5:
            break
    return out or [((phrase or "").strip()[:80] or "iptal")]


def _search_body(base: str, phrase: str, page: int, size: int) -> dict[str, Any]:
    if "danistay" in base:
        words = _tokens(phrase)
        # Portal düz gövdeyi Runtime exception ile düşürür; data sarmalayıcı zorunlu.
        if len((phrase or "").strip()) <= 80:
            and_words = [(phrase or "").strip()]
            or_words: list[str] = []
        else:
            and_words = words[:2] or [(phrase or "").strip()[:80] or "iptal"]
            or_words = words[2:5]
        return {
            "data": {
                "andKelimeler": and_words,
                "orKelimeler": or_words,
                "notAndKelimeler": [],
                "notOrKelimeler": [],
                "pageNumber": page,
                "pageSize": min(size, 10),
            }
        }
    return {
        "data": {
            "aranan": phrase,
            "arananKelime": phrase,
            "pageSize": min(size, 20),
            "pageNumber": page,
        }
    }


def _rows_from_html(html: str) -> list[dict[str, Any]]:
    text = html or ""
    ids = re.findall(r"getDokuman\(\s*['\"](\d{5,})['\"]", text)
    ids += re.findall(r'data-(?:id|documentid)=[\'"](\d{5,})[\'"]', text, re.I)
    ids += re.findall(r'documentId["\s:=]+(\d{5,})', text)
    ids += re.findall(r"[?&]id=(\d{5,})", text)
    ids += re.findall(r"\bid\s*[:=]\s*['\"](\d{5,})['\"]", text)
    seen: set[str] = set()
    ordered: list[str] = []
    for doc_id in ids:
        if doc_id not in seen:
            seen.add(doc_id)
            ordered.append(doc_id)
    rows: list[dict[str, Any]] = []
    blocks = re.findall(
        r"(?:Danıştay|Daire|Kurul)[^<]{0,80}.*?(\d{4}/\d{1,6})[^<]{0,40}(\d{4}/\d{1,6})",
        _plain(text),
        re.I,
    )
    for i, doc_id in enumerate(ordered[:40]):
        esas, karar = ("", "")
        if i < len(blocks):
            esas, karar = blocks[i]
        rows.append(
            {
                "documentId": doc_id,
                "birimAdi": "Danıştay" if "danistay" in text.lower() else "",
                "esasNo": esas,
                "kararNo": karar,
                "kararTarihi": "",
                "baslik": "",
                "ozet": "",
            }
        )
    return rows


def _forced_bases(court_types: list[str] | None) -> list[tuple[str, str]]:
    courts = [str(c).upper() for c in (court_types or [])]
    if (courts and all("DANISTAY" in c for c in courts)) or (not courts and _active_lock() == "danistay"):
        return [(DANISTAY, "Danıştay")]
    if (courts and all("YARGITAY" in c or c == "YARGITAYKARARI" for c in courts)) or (
        not courts and _active_lock() == "yargitay"
    ):
        return [(YARGITAY, "Yargıtay")]
    if courts and all(c in COURT_EMSAL or "EMSAL" in c or "YEREL" in c or "ISTINAF" in c for c in courts):
        return [(EMSAL, "Emsal (yerel / istinaf / KYB)")]
    return []


def _target_bases(phrase: str, court_types: list[str] | None = None) -> list[tuple[str, str]]:
    forced = _forced_bases(court_types)
    if forced:
        return forced
    fold = (phrase or "").replace("İ", "i").replace("I", "i").replace("ı", "i").lower()
    if any(
        k in fold
        for k in (
            "danistay",
            "iyuk",
            "idari",
            "iptal dav",
            "tam yargi",
            "2577",
            "yurutmenin durdur",
            "guvenlik sorustur",
            "memuriyet",
            "kamu gorev",
            "kamu görev",
            "657 say",
        )
    ):
        return [(DANISTAY, "Danıştay")]
    if any(k in fold for k in ("istinaf", "yerel mahkeme", " emsal", "kyb")):
        return [(EMSAL, "Emsal (yerel / istinaf / KYB)")]
    return [(YARGITAY, "Yargıtay")]


def _row_fits(base: str, item: dict[str, Any]) -> bool:
    if "danistay" not in (base or ""):
        return True
    blob = " ".join(str(item.get(k) or "") for k in ("birimAdi", "baslik", "ozet", "kaynak"))
    return not _YARGITAY_MARK.search(blob)


def _portal_search(base: str, phrase: str, page_size: int = 50, page_number: int = 1) -> dict[str, Any]:
    phrase = (phrase or "").strip()
    if not phrase:
        return {"error": "Arama ifadesi boş."}
    if _is_cooling():
        return {"error": "Erişim sınırı", "phrase": phrase, "kaynak": base}
    size = max(10, min(int(page_size or 10), 20))
    page = max(1, min(int(page_number or 1), 4))
    body = _search_body(base, phrase, page, size)
    last = "Arama yanıt vermedi."
    with _client(base) as http:
        try:
            res = http.post(base + "/aramalist", json=body)
        except Exception as exc:
            return {"error": str(exc), "phrase": phrase, "kaynak": base}
        last = f"HTTP {res.status_code}"
        if _rate_limited(res):
            _mark_limited()
            return {"error": "Erişim sınırı", "phrase": phrase, "kaynak": base}
        if res.status_code >= 400:
            return {"error": last, "phrase": phrase, "kaynak": base}
        try:
            data = _as_dict(res.json())
            if isinstance(data.get("metadata"), dict) and data["metadata"].get("FMTY") == "ERROR":
                last = data["metadata"].get("FMTE") or last
                return {"error": last, "phrase": phrase, "kaynak": base}
            rows, total = _rows_from(data)
            if not rows and data.get("data") not in (None, {}, []):
                rows = _rows_from_html(_dump(data.get("data")))
                total = total or len(rows)
            rows = [r for r in rows if _row_fits(base, r)]
            if rows:
                _remember_docs(base, phrase, rows)
            return {
                "kaynak": base,
                "phrase": phrase,
                "sayfa": page,
                "toplam": total,
                "decisions": rows,
            }
        except Exception:
            rows = [r for r in _rows_from_html(res.text) if _row_fits(base, r)]
            if rows:
                _remember_docs(base, phrase, rows)
                return {
                    "kaynak": base,
                    "phrase": phrase,
                    "sayfa": page,
                    "toplam": len(rows),
                    "decisions": rows,
                }
    return {"error": last, "phrase": phrase, "kaynak": base}


def _maybe_b64(raw: str) -> str:
    t = (raw or "").strip()
    if len(t) < 80 or len(t) % 4:
        return ""
    if not re.fullmatch(r"[A-Za-z0-9+/=\s]+", t):
        return ""
    try:
        import base64

        out = base64.b64decode(t, validate=False)
        for enc in ("utf-8", "cp1254", "latin-1"):
            try:
                text = out.decode(enc)
            except Exception:
                continue
            if "<" in text or len(text) > 80:
                return text
    except Exception:
        return ""
    return ""


def _doc_from_payload(data: Any) -> str:
    if isinstance(data, str):
        plain = _plain(data)
        if len(plain) >= 40:
            return plain[:16000]
        decoded = _maybe_b64(data)
        return _plain(decoded)[:16000] if decoded else ""
    if not isinstance(data, dict):
        return ""
    meta = data.get("metadata") if isinstance(data.get("metadata"), dict) else {}
    if str(meta.get("FMTY") or "").upper() == "ERROR":
        return ""
    blob = data.get("data")
    if blob is None:
        blob = data.get("content") or data.get("dokuman") or data.get("html")
    if isinstance(blob, str):
        return _doc_from_payload(blob)
    if isinstance(blob, dict):
        for key in ("content", "html", "dokuman", "document", "text", "data"):
            val = blob.get(key)
            if isinstance(val, str) and val.strip():
                got = _doc_from_payload(val)
                if got:
                    return got
    return ""


def _decode_doc_response(res: httpx.Response) -> str:
    if res.status_code >= 400:
        return ""
    text = res.text or ""
    ctype = (res.headers.get("content-type") or "").lower()
    if "json" in ctype or text.lstrip().startswith("{") or text.lstrip().startswith("["):
        try:
            return _doc_from_payload(res.json())
        except Exception:
            return ""
    plain = _plain(text)
    return plain[:16000] if len(plain) > 80 else ""


def _portal_document(base: str, document_id: str, aranan: str = "") -> str:
    document_id = (document_id or "").strip()
    if not document_id:
        return "documentId boş."
    if _is_cooling():
        return "Erişim sınırı"
    hint = aranan or (_DOC_HINTS.get(document_id) or ("", ""))[1]
    if "danistay" in base:
        word = hint or "iptal"
        qs = httpx.QueryParams({"id": document_id, "arananKelime": word})
        url = f"{base}/getDokuman?{qs}"
    else:
        url = f"{base}/getDokuman?id={document_id}"
    with _client(base) as http:
        try:
            res = http.get(url)
        except Exception as exc:
            return str(exc)
        if _rate_limited(res):
            _mark_limited()
            return "Erişim sınırı"
        text = _decode_doc_response(res)
        if text:
            return text
        return f"HTTP {res.status_code}"


def _courts_base(court_types: list[str] | None) -> str:
    courts = [str(c).upper() for c in (court_types or [])]
    if any("DANISTAY" in c for c in courts):
        return DANISTAY
    if any(c in COURT_EMSAL or "EMSAL" in c or "YEREL" in c or "ISTINAF" in c for c in courts):
        return EMSAL
    return YARGITAY


def _row_key(item: dict[str, Any]) -> str:
    e = str(item.get("esasNo") or "").strip()
    k = str(item.get("kararNo") or "").strip()
    d = str(item.get("documentId") or "").strip()
    if e or k:
        return f"{e}|{k}"
    return d or str(item.get("baslik") or "")


def _merge_rows(dest: list[dict[str, Any]], incoming: list[dict[str, Any]]) -> None:
    seen = {_row_key(x) for x in dest if _row_key(x)}
    for item in incoming:
        key = _row_key(item)
        if not key or key in seen:
            continue
        seen.add(key)
        dest.append(item)


def _search_bases(
    phrase: str,
    pages: int = 2,
    page_size: int = 50,
    court_types: list[str] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int]:
    _apply_court_lock(court_types)
    packs: list[dict[str, Any]] = []
    rows: list[dict[str, Any]] = []
    grand = 0
    for base, label in _target_bases(phrase, court_types):
        taken = 0
        total = 0
        err = ""
        for page in range(1, max(1, pages) + 1):
            data = _portal_search(base, phrase, page_size=page_size, page_number=page)
            if data.get("error"):
                err = str(data["error"])
                if page == 1:
                    packs.append({"kaynak": label, "url": base, "sayfa": page, "hata": err})
                break
            total = int(data.get("toplam") or total or 0)
            found = list(data.get("decisions") or [])
            if not found:
                break
            before = len(rows)
            for item in found:
                item["kaynak"] = label
                item["sorgu"] = phrase
            _merge_rows(rows, found)
            taken += len(rows) - before
            if len(found) < 8:
                break
        if taken or total:
            grand += total
            packs.append({"kaynak": label, "url": base, "havuz": total, "alinan": taken, "sorgu": phrase})
        elif err and not any(p.get("kaynak") == label and p.get("hata") for p in packs):
            packs.append({"kaynak": label, "url": base, "hata": err, "sorgu": phrase})
    return packs, rows, grand


def extract_holding(plain: str, limit: int = 520) -> str:
    text = _plain(plain or "")
    if len(text) < 40:
        return text[:limit]
    chunks: list[str] = []
    for mark in ("SONUÇ", "HÜKÜM", "GEREKÇE", "bu nedenle", "sonuç olarak", "açıklanan nedenlerle"):
        idx = text.upper().find(mark.upper()) if mark.isupper() else text.lower().find(mark.lower())
        if idx >= 0:
            piece = text[idx : idx + 700]
            chunks.append(piece)
    if not chunks:
        sents = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if len(s.strip()) > 40]
        keep = [
            s
            for s in sents
            if any(
                w in s.lower()
                for w in (
                    "boşan",
                    "kusur",
                    "sadakat",
                    "velayet",
                    "nafaka",
                    "tazminat",
                    "fesih",
                    "alacak",
                    "iptal",
                    "haksız",
                )
            )
        ]
        chunks = keep[:4] or sents[:3]
    out = " ".join(chunks)
    out = re.sub(r"\s+", " ", out).strip()
    return out[:limit]


def search_corpus(phrase: str, pages: int = 2, court_types: list[str] | None = None) -> str:
    """Tek ifadeyle kilitli mahkeme havuzu (İdare = yalnızca Danıştay)."""
    _apply_court_lock(court_types)
    phrase = (phrase or "").strip()
    if not phrase:
        return _dump({"error": "Arama ifadesi boş."})
    packs, rows, grand = _search_bases(phrase, pages=1, court_types=court_types)
    return _dump(
        {
            "phrase": phrase,
            "gecis": "derin",
            "taranan_havuz": grand,
            "kaynaklar": packs,
            "decisions": rows[:56],
        },
        limit=36000,
    )


def search_corpus_deep(
    phrases: list[str] | str,
    pages: int = 2,
    court_types: list[str] | None = None,
) -> str:
    _apply_court_lock(court_types)
    if isinstance(phrases, str):
        raw = [p.strip() for p in re.split(r"[;\n|]+", phrases) if p.strip()]
    else:
        raw = [str(p).strip() for p in (phrases or []) if str(p).strip()]
    qs = []
    for q in raw:
        if q and q not in qs:
            qs.append(q)
    qs = qs[:2]
    if not qs:
        return _dump({"error": "Arama ifadesi boş."})
    packs: list[dict[str, Any]] = []
    rows: list[dict[str, Any]] = []
    grand = 0
    for phrase in qs:
        if _is_cooling():
            packs.append({"hata": "Erişim sınırı", "sorgu": phrase})
            break
        pks, found, total = _search_bases(phrase, pages=1, court_types=court_types)
        packs.extend(pks)
        grand += total
        _merge_rows(rows, found)
        if any("sınır" in str(p.get("hata") or "") for p in pks):
            break
    return _dump(
        {
            "sorgular": qs,
            "gecis": "coklu-derin",
            "taranan_havuz": grand,
            "kaynaklar": packs,
            "decisions": rows[:72],
        },
        limit=48000,
    )


def search_bedesten(phrase: str, court_types: list[str] | None = None) -> str:
    _apply_court_lock(court_types)
    phrase = (phrase or "").strip()
    if not phrase:
        return _dump({"error": "Arama ifadesi boş."})
    base, label = _target_bases(phrase, court_types)[0]
    data = _portal_search(base, phrase, page_size=10, page_number=1)
    if isinstance(data, dict) and "error" not in data:
        data["kaynak_adi"] = label
    return _dump(data)


def get_bedesten_document(document_id: str) -> str:
    document_id = (document_id or "").strip()
    hint = _DOC_HINTS.get(document_id)
    if hint:
        return _portal_document(hint[0], document_id, aranan=hint[1])
    if _active_lock() == "danistay":
        return _portal_document(DANISTAY, document_id)
    return _portal_document(YARGITAY, document_id)


def get_bedesten_holding(document_id: str) -> str:
    """Bedesten'de holding ucu yoktur; belge çekilip yerelde özetlenir."""
    text = get_bedesten_document(document_id)
    if not text or text.startswith("HTTP ") or "alınamadı" in text or "boş" in text[:20]:
        return text
    return extract_holding(text)


def search_emsal(keyword: str, page_number: int = 1) -> str:
    return _dump(_portal_search(EMSAL, keyword, page_size=50, page_number=page_number))


def _parse_rg_date(raw: str) -> date | None:
    t = (raw or "").strip()
    if not t:
        return None
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%Y%m%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(t[:10] if fmt != "%Y%m%d" else re.sub(r"\D", "", t)[:8], fmt).date()
        except ValueError:
            continue
    m = re.search(r"(\d{4})[-./](\d{1,2})[-./](\d{1,2})", t)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None
    m = re.search(r"(\d{1,2})[./](\d{1,2})[./](\d{4})", t)
    if m:
        try:
            return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        except ValueError:
            return None
    return None


def _rg_fold(s: str) -> str:
    t = (s or "").replace("İ", "i").replace("I", "i")
    table = str.maketrans({"ı": "i", "İ": "i", "ö": "o", "Ö": "o", "ü": "u", "Ü": "u", "ş": "s", "Ş": "s", "ğ": "g", "Ğ": "g", "ç": "c", "Ç": "c"})
    return t.translate(table).lower()


def _rg_day_urls(day: date) -> list[str]:
    y, m, compact = day.strftime("%Y"), day.strftime("%m"), day.strftime("%Y%m%d")
    iso = day.strftime("%Y-%m-%d")
    return [
        f"{RG}/fihrist?tarih={iso}",
        f"{RG}/eskiler/{y}/{m}/{compact}.htm",
    ]


def _rg_item_url(day: date, item: str) -> str:
    y, m, compact = day.strftime("%Y"), day.strftime("%m"), day.strftime("%Y%m%d")
    num = re.sub(r"\D", "", item or "") or "1"
    return f"{RG}/eskiler/{y}/{m}/{compact}-{num}.htm"


def _rg_entries(html: str, page_url: str = "") -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    base = page_url or (RG + "/")
    for href, title in re.findall(r'href=["\']([^"\']+)["\'][^>]*>([^<]{8,240})', html or "", re.I):
        if href.startswith("#") or "javascript:" in href.lower():
            continue
        if not re.search(r"(?i)eskiler|fihrist|ilanlar|\.htm|\.pdf|\d{8}-\d+", href):
            continue
        url = urljoin(base, href).split("#")[0]
        if url in seen:
            continue
        tit = _plain(title)
        if len(tit) < 8 or re.search(r"(?i)pdf görüntüle|önceki sayı|sonraki sayı|mobil uygulaması", tit):
            continue
        seen.add(url)
        rows.append({"baslik": tit[:220], "url": url})
        if len(rows) >= 40:
            break
    if not rows and page_url:
        text = _plain(html)
        if text:
            rows.append({"baslik": text[:180], "url": page_url})
    return rows


def get_resmi_gazete_fihrist(date_text: str) -> str:
    day = _parse_rg_date(date_text)
    if not day:
        return _dump({"kaynak": "Resmî Gazete", "sonuc": "taranamadı", "neden": "tarih yok"})
    last = "fihrist yok"
    with _client(RG) as http:
        http.headers["Accept"] = "text/html,application/xhtml+xml,*/*"
        for url in _rg_day_urls(day):
            try:
                res = http.get(url)
                last = f"HTTP {res.status_code}"
                if res.status_code >= 400:
                    continue
                html = res.text or ""
                if re.search(r"(?i)böyle bir içerik mevcut değildir|404", html):
                    continue
                rows = _rg_entries(html, str(res.url))
                if rows:
                    return _dump(
                        {
                            "kaynak": "Resmî Gazete",
                            "tarih": day.isoformat(),
                            "url": str(res.url),
                            "kayitlar": rows[:30],
                        }
                    )
            except Exception as exc:
                last = str(exc)
    return _dump({"kaynak": "Resmî Gazete", "tarih": day.isoformat(), "sonuc": "taranamadı", "neden": last})


def get_resmi_gazete_document(url_or_date_and_item: str) -> str:
    raw = (url_or_date_and_item or "").strip()
    if not raw:
        return _dump({"ok": False, "sonuc": "taranamadı"})
    url = raw
    if not raw.startswith("http"):
        day = _parse_rg_date(raw)
        item = ""
        m = re.search(r"(?:^|\s)(\d{1,3})(?:\s*$)", raw)
        if m:
            item = m.group(1)
        dash = re.search(r"(\d{8})-(\d{1,3})", raw)
        if dash:
            day = _parse_rg_date(dash.group(1))
            item = dash.group(2)
        if day:
            url = _rg_item_url(day, item or "1") if item else _rg_day_urls(day)[1]
    try:
        with _client(RG) as http:
            http.headers["Accept"] = "text/html,application/xhtml+xml,*/*"
            res = http.get(url)
            if res.status_code >= 400:
                return _dump({"ok": False, "sonuc": "taranamadı", "url": url, "neden": f"HTTP {res.status_code}"})
            text = _plain(res.text)
    except Exception as exc:
        return _dump({"ok": False, "sonuc": "taranamadı", "url": url, "neden": str(exc)})
    if not text:
        return _dump({"ok": False, "sonuc": "taranamadı", "url": url, "neden": "404/svg"})
    return _dump({"ok": True, "kaynak": "Resmî Gazete", "url": url, "metin": text[:6000]})


def search_resmi_gazete(query: str, date_start: str = "", date_end: str = "") -> str:
    q = (query or "").strip()
    if not q:
        return _dump({"error": "Arama ifadesi boş.", "sonuc": "taranamadı"})
    start = _parse_rg_date(date_start)
    end = _parse_rg_date(date_end) or start
    days: list[date] = []
    if start:
        cur = start
        last = end or start
        if last < cur:
            cur, last = last, cur
        while cur <= last and len(days) < 14:
            days.append(cur)
            cur += timedelta(days=1)
    else:
        today = date.today()
        days = [today - timedelta(days=i) for i in range(0, 8)]
    found: list[dict[str, str]] = []
    last = "kayıt yok"
    qlow = _rg_fold(q)
    with _client(RG) as http:
        http.headers["Accept"] = "text/html,application/xhtml+xml,*/*"
        homes = [f"{RG}/", f"{RG}/eskiler/", f"{RG}/fihrist"]
        if not start:
            for url in homes:
                try:
                    res = http.get(url)
                    if res.status_code >= 400:
                        last = f"HTTP {res.status_code}"
                        continue
                    last = f"HTTP {res.status_code}"
                    html = res.text or ""
                    text = _plain(html)
                    fold = _rg_fold(text)
                    if qlow in fold:
                        idx = fold.find(qlow)
                        found.append({"baslik": text[max(0, idx - 80) : idx + 220], "url": str(res.url)})
                    for row in _rg_entries(html, str(res.url)):
                        if qlow in _rg_fold(row.get("baslik") or "") or qlow in _rg_fold(row.get("url") or ""):
                            found.append(row)
                except Exception as exc:
                    last = str(exc)
        for day in days:
            if len(found) >= 12:
                break
            for url in _rg_day_urls(day):
                try:
                    res = http.get(url)
                    if res.status_code >= 400:
                        continue
                    last = f"HTTP {res.status_code}"
                    html = res.text or ""
                    if re.search(r"(?i)böyle bir içerik mevcut değildir", html):
                        continue
                    text = _plain(html)
                    rows = _rg_entries(html, str(res.url))
                    matched = [r for r in rows if qlow in _rg_fold(r.get("baslik") or "")]
                    fold = _rg_fold(text)
                    if not matched and qlow in fold:
                        idx = fold.find(qlow)
                        matched = [{"baslik": text[max(0, idx - 80) : idx + 220], "url": str(res.url), "tarih": day.isoformat()}]
                    for row in matched:
                        row.setdefault("tarih", day.isoformat())
                        found.append(row)
                    if matched:
                        break
                except Exception as exc:
                    last = str(exc)
    uniq: list[dict[str, str]] = []
    seen: set[str] = set()
    for row in found:
        key = (row.get("url") or "") + (row.get("baslik") or "")[:80]
        if key in seen:
            continue
        seen.add(key)
        uniq.append(row)
    if not uniq:
        return _dump({"kaynak": "Resmî Gazete", "query": q, "sonuc": "taranamadı", "neden": last, "kayitlar": []})
    return _dump({"kaynak": "Resmî Gazete", "query": q, "kayitlar": uniq[:12]})
