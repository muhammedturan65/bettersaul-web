"""BetterSaul MCP — Anayasa Mahkemesi kamu araması. Olay / TCKN gönderilmez."""
from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import quote, urljoin

from .sources import _client, _dump, _plain

AYM = "https://www.anayasa.gov.tr"
BB = "https://kararlarbilgibankasi.anayasa.gov.tr"
ND = "https://normkararlarbilgibankasi.anayasa.gov.tr"

_ADVERSE = re.compile(
    r"(?i)kabul edilemez|açıkça dayanaktan yoksun|davan[ıi]n reddi|"
    r"ihlal olmad[ıi][gğ]|başvurunun reddine|incelenmesine (imkan|imkân) bulunmad"
)
_HELP = re.compile(
    r"(?i)ihlal|kamu hizmetine girme|kamu görevine|gerekçe|kişisel veri|etkili başvuru|"
    r"hak arama|güvenlik soruştur|arşiv araştırm|ölçülülük|denetime elveriş|"
    r"atama|masumiyet|eşitlik|gerekçeli karar|HAGB|hükmün açıklanmasının geri"
)
_BB_PATH = re.compile(r"(?i)/BB/\d{4}/\d+")
_ND_PATH = re.compile(r"(?i)/(?:ND|Karar)/[^\s\"']+")
_KUNYE = re.compile(
    r"(?i)(?:B\.\s*No\s*:?\s*|Başvuru\s+No(?:su)?\s*:?\s*)(\d{4}/\d+)|"
    r"(?:E\.\s*)(\d{4}/\d+).{0,24}(?:K\.\s*)(\d{4}/\d+)"
)


def _as_dict(raw: str) -> dict[str, Any]:
    try:
        data = json.loads(raw or "")
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _helps(text: str) -> bool:
    t = text or ""
    if not t or _ADVERSE.search(t):
        return False
    return bool(_HELP.search(t))


def _abs(base: str, href: str) -> str:
    href = (href or "").strip()
    if not href:
        return ""
    if href.startswith("http"):
        return href
    return urljoin(base.rstrip("/") + "/", href.lstrip("/"))


def _row(title: str, esas: str = "", karar: str = "", tarih: str = "", ozet: str = "", url: str = "") -> dict[str, str]:
    kunye = ""
    if esas and karar:
        kunye = f"AYM, E. {esas} K. {karar}"
    elif esas:
        kunye = f"AYM, B. No: {esas}"
    elif title:
        kunye = title[:160]
    if tarih and kunye:
        m = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", (tarih or "").strip())
        if m:
            tarih = f"{int(m.group(3)):02d}.{int(m.group(2)):02d}.{m.group(1)}"
        kunye = f"{kunye}, {tarih}"
    return {
        "baslik": (title or "")[:220],
        "esas": esas,
        "karar": karar,
        "tarih": tarih,
        "ozet": re.sub(r"\s+", " ", ozet or "").strip()[:420],
        "url": url,
        "kunye": kunye,
    }


def _parse_list(html: str, base: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for href, title in re.findall(r'href=["\']([^"\']+)["\'][^>]*>([^<]{12,180})', html or "", re.I):
        url = _abs(base, href)
        if not url or url in seen:
            continue
        if not (_BB_PATH.search(url) or _ND_PATH.search(url) or "/kararlar/" in url.lower()):
            continue
        tit = _plain(title)
        if len(tit) < 8:
            continue
        seen.add(url)
        esas = ""
        karar = ""
        km = _KUNYE.search(tit + " " + url)
        if km:
            esas = km.group(1) or km.group(2) or ""
            karar = km.group(3) or ""
        bb = _BB_PATH.search(url)
        if bb and not esas:
            parts = bb.group(0).strip("/").split("/")
            if len(parts) >= 3:
                esas = f"{parts[1]}/{parts[2]}"
        rows.append(_row(tit, esas=esas, karar=karar, url=url, ozet=tit))
        if len(rows) >= 12:
            break
    return rows


def _search_html(url: str, query: str) -> list[dict[str, str]]:
    found: list[dict[str, str]] = []
    with _client(url) as http:
        http.headers["Accept"] = "text/html,application/xhtml+xml,*/*"
        tries = [
            url,
            f"{url.rstrip('/')}/Ara?KelimeAra={quote(query)}",
            f"{url.rstrip('/')}/Ara?KelimeAra[]={quote(query)}",
            f"{url.rstrip('/')}/BB/Ara?KelimeAra={quote(query)}",
        ]
        if "anayasa.gov.tr" in url and "kararlarbilgi" not in url:
            tries = [
                f"{AYM}/tr/kararlar/bireysel-basvuru/",
                f"{AYM}/tr/kararlar/norm-denetimi/",
                f"{AYM}/tr/kararlar/",
            ]
        for target in tries:
            try:
                res = http.get(target)
                if res.status_code >= 400:
                    continue
                html = res.text or ""
                if re.search(r"(?i)loading\.\.\.|ng-app|id=\"root\"", html) and len(_plain(html)) < 200:
                    continue
                rows = _parse_list(html, str(res.url) if res.url else url)
                qlow = query.lower()
                for row in rows:
                    blob = " ".join(row.values()).lower()
                    if qlow in blob or any(w in blob for w in qlow.split() if len(w) > 3) or _helps(blob):
                        found.append(row)
                if found:
                    break
            except Exception:
                continue
    return found


def _search_api(base: str, query: str, kind: str) -> list[dict[str, str]]:
    payload = {
        "pageSize": 8,
        "pageNumber": 1,
        "searchText": query,
        "keywords": query,
        "decisionType": kind,
    }
    out: list[dict[str, str]] = []
    with _client(base) as http:
        http.headers["Accept"] = "application/json, text/plain, */*"
        http.headers["Content-Type"] = "application/json"
        for path in ("/api/core/public/search", "/api/search", "/api/public/search"):
            try:
                res = http.post(base.rstrip("/") + path, json=payload)
                if res.status_code >= 400:
                    continue
                data = res.json()
            except Exception:
                continue
            blob = data if isinstance(data, dict) else {}
            hits = blob.get("data") or blob.get("items") or blob.get("results") or blob.get("content") or []
            if isinstance(hits, dict):
                hits = hits.get("items") or hits.get("data") or []
            if not isinstance(hits, list):
                continue
            for item in hits[:10]:
                if not isinstance(item, dict):
                    continue
                title = str(item.get("baslik") or item.get("title") or item.get("kararAdi") or "")
                esas = str(item.get("esasNo") or item.get("basvuruNo") or item.get("esas") or "")
                karar = str(item.get("kararNo") or item.get("karar") or "")
                tarih = str(item.get("kararTarihi") or item.get("tarih") or "")
                ozet = str(item.get("ozet") or item.get("sonuc") or item.get("ilke") or title)
                url = str(item.get("url") or item.get("documentUrl") or item.get("href") or "")
                # API çoğu alanı boş döndürebilir; karar linki ve başlık üretilir.
                if not url and re.match(r"^\d{4}/\d+$", esas) and "kararlarbilgibankasi" in base:
                    url = f"{BB}/BB/{esas}"
                if not title and esas:
                    title = f"AYM kararı, B. No: {esas}"
                out.append(_row(title, esas=esas, karar=karar, tarih=tarih, ozet=ozet, url=url))
            if out:
                break
    return out


def search_anayasa(keywords: str, decision_type: str = "bireysel_basvuru") -> str:
    q = re.sub(r"\s+", " ", (keywords or "").strip())
    if not q:
        return _dump({"error": "Anahtar boş.", "sonuc": "taranamadı", "kayitlar": []})
    kind = (decision_type or "bireysel_basvuru").strip().lower()
    if kind in {"norm", "norm_denetimi", "iptal", "itiraz"}:
        kind = "norm_denetimi"
        bases = [ND, AYM]
    else:
        kind = "bireysel_basvuru"
        bases = [BB, AYM]
    rows: list[dict[str, str]] = []
    for base in bases:
        rows.extend(_search_api(base, q, kind))
        if rows:
            break
    if not rows:
        for base in bases:
            rows.extend(_search_html(base, q))
            if rows:
                break
    good = [r for r in rows if _helps(" ".join(r.values()))]
    if not good:
        good = [r for r in rows if not _ADVERSE.search(" ".join(r.values()))]
    pick = (good or [])[:6]
    if not pick:
        return _dump(
            {
                "kaynak": "Anayasa Mahkemesi",
                "query": q,
                "decision_type": kind,
                "sonuc": "taranamadı",
                "kayitlar": [],
            }
        )
    return _dump(
        {
            "kaynak": "Anayasa Mahkemesi",
            "query": q,
            "decision_type": kind,
            "kayitlar": pick,
        }
    )


def _doc_from_api(no: str) -> dict[str, str] | None:
    """Karar sayfası betikle yüklendiğinde başvuru numarasıyla arama API'sinden künye/özet alır."""
    rows = _search_api(BB, no, "bireysel_basvuru") or _search_api(ND, no, "norm_denetimi")
    for r in rows:
        # Yalnızca birebir eşleşme: farklı bir kararı asla ikame etme (uydurma riski).
        if r.get("esas") == no or no in (r.get("kunye") or ""):
            return r
    return None


def get_anayasa_document(url_or_id: str) -> str:
    raw = (url_or_id or "").strip()
    if not raw:
        return _dump({"ok": False, "sonuc": "yok, uydurma"})
    url = raw
    if raw.startswith("/"):
        url = BB + raw
    elif re.match(r"^\d{4}/\d+$", raw):
        y, n = raw.split("/", 1)
        url = f"{BB}/BB/{y}/{n}"
    elif not raw.startswith("http"):
        m = _BB_PATH.search("/" + raw if not raw.startswith("/BB") else raw)
        url = (BB + m.group(0)) if m else raw
    no_m = re.search(r"(\d{4}/\d+)\s*$", url) or re.search(r"^(\d{4}/\d+)$", raw)
    basvuru_no = no_m.group(1) if no_m else ""

    def _api_fallback(neden: str) -> str:
        if basvuru_no:
            row = _doc_from_api(basvuru_no)
            if row:
                row["ok"] = True
                row["ilke"] = row.get("ozet") or ""
                row["not"] = "Karar sayfası betikle yüklendiğinden künye/özet arama API'sinden alındı."
                return _dump(row)
        return _dump({"ok": False, "sonuc": "yok, uydurma", "url": url, "neden": neden})

    try:
        with _client(url) as http:
            http.headers["Accept"] = "text/html,application/xhtml+xml,*/*"
            res = http.get(url)
            if res.status_code >= 400:
                return _api_fallback(f"HTTP {res.status_code}")
            text = _plain(res.text)
    except Exception as exc:
        return _api_fallback(str(exc))
    if len(text) < 80 or re.search(r"(?i)loading\.\.\.|image/svg", text):
        return _api_fallback("sayfa betikle yükleniyor; düz metin alınamadı")
    if _ADVERSE.search(text) and not _HELP.search(text):
        return _dump({"ok": False, "sonuc": "ret/incelenemezlik — atıldı", "url": url})
    title = ""
    tm = re.search(r"(?i)(başvuru\s+no(?:su)?\s*:?\s*\d{4}/\d+|E\.\s*\d{4}/\d+\s*K\.\s*\d{4}/\d+)", text)
    if tm:
        title = tm.group(1)
    km = _KUNYE.search(text)
    esas = (km.group(1) or km.group(2) or "") if km else ""
    karar = (km.group(3) or "") if km else ""
    ilke = ""
    for sent in re.split(r"(?<=[.!?])\s+", text):
        if _helps(sent) and len(sent) > 40:
            ilke = re.sub(r"\s+", " ", sent).strip()[:400]
            break
    if not ilke:
        ilke = text[:360].rsplit(" ", 1)[0] + "…"
    row = _row(title or "AYM kararı", esas=esas, karar=karar, ozet=ilke, url=url)
    row["ilke"] = ilke
    row["ok"] = True
    return _dump(row)


def first_helpful(raw: str) -> dict[str, Any] | None:
    rows = helpful_list(raw, limit=1)
    return rows[0] if rows else None


def helpful_list(raw: str, limit: int = 3) -> list[dict[str, Any]]:
    data = _as_dict(raw)
    recs = [r for r in (data.get("kayitlar") or []) if isinstance(r, dict)]
    good: list[dict[str, Any]] = []
    seen: set[str] = set()

    def take(row: dict[str, Any]) -> None:
        key = str(row.get("kunye") or row.get("url") or row.get("baslik") or "")[:120]
        if not key or key in seen:
            return
        seen.add(key)
        good.append(row)

    for row in recs:
        blob = " ".join(str(v) for v in row.values())
        if (row.get("kunye") or row.get("url")) and _helps(blob):
            take(row)
        if len(good) >= limit:
            return good
    for row in recs:
        blob = " ".join(str(v) for v in row.values())
        if (row.get("kunye") or row.get("url") or row.get("baslik")) and not _ADVERSE.search(blob):
            take(row)
        if len(good) >= limit:
            break
    return good[:limit]


def parse_document(raw: str) -> dict[str, Any]:
    data = _as_dict(raw)
    return data if data.get("ok") else {}
