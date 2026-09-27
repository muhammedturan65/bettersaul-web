"""
BetterSaul Source Connector — Async HTTP Scraper

Production-grade port of legacy/BetterSaul/app/engine/bettersaul_mcp/sources.py
- Async httpx (instead of sync httpx.Client)
- Redis-based rate limiting (instead of global _LIMITED_UNTIL)
- Retry with exponential backoff
- Robust HTML/JSON parsing
- Metadata extraction (court, chamber, decision_no, date)

Supported sources:
  - Yargıtay    (karararama.yargitay.gov.tr)
  - Danıştay    (danistaydergiler.adalet.gov.tr)
  - Emsal       (emsal.uyap.gov.tr)
  - AYM         (anayasa.gov.tr/api/core/public/search)
  - Resmî Gazete (resmigazete.gov.tr)
  - Mevzuat     (mevzuat.gov.tr)
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, date
from typing import Any, Optional
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# ─── Data Models ──────────────────────────────────────────────────────────────


@dataclass
class LegalDocument:
    """Unified legal document representation across all sources."""
    source: str                    # yargitay | danistay | emsal | aym | resmi_gazete | mevzuat
    source_doc_id: str             # portal-side unique ID
    court: str                     # Yargıtay | Danıştay | Emsal | Anayasa Mahkemesi | ...
    court_chamber: str             # 9. HD | 5. D. | "" for AYM
    decision_number: str           # E. 2024/12345, K. 2024/6789 or B. No: 2024/123
    case_number: str               # optional
    decision_date: Optional[date]
    document_type: str             # decision | ruling | statute | regulation
    title: str
    full_text: str
    summary: str
    keywords: list[str] = field(default_factory=list)
    topics: list[str] = field(default_factory=list)
    citations: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    source_url: str = ""


@dataclass
class SearchResponse:
    """Search response from a source."""
    total: int
    documents: list[LegalDocument]
    has_more: bool
    next_page: int | None = None
    rate_limited: bool = False
    error: str | None = None


# ─── Base Connector ───────────────────────────────────────────────────────────


class BaseConnector:
    """Base class for all source connectors."""

    SOURCE_NAME: str = ""
    BASE_URL: str = ""
    SEARCH_URL: str = ""
    DOC_URL: str = ""

    # Rate limit (per source)
    RATE_LIMIT_RPM: int = 20              # requests per minute
    RATE_LIMIT_COOLDOWN: int = 50         # seconds to wait after 429

    # HTTP settings
    TIMEOUT: float = 30.0
    MAX_RETRIES: int = 3

    # Browser-like headers (some portals block default urllib)
    DEFAULT_HEADERS: dict[str, str] = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/json,application/xhtml+xml,*/*;q=0.8",
        "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.8",
        "X-Requested-With": "XMLHttpRequest",
    }

    def __init__(
        self,
        client: httpx.AsyncClient,
        rate_limiter: "RateLimiter | None" = None,
        proxy: str | None = None,
    ):
        self.client = client
        self.rate_limiter = rate_limiter
        self.proxy = proxy
        self._limited_until: float = 0

    async def _request(
        self,
        method: str,
        url: str,
        *,
        headers: dict | None = None,
        params: dict | None = None,
        json_body: dict | None = None,
        data: dict | None = None,
    ) -> httpx.Response:
        """Make HTTP request with rate limit, retry, and backoff."""
        # Redis-backed rate limiter (production)
        if self.rate_limiter:
            await self.rate_limiter.acquire(self.SOURCE_NAME)

        # Check local cooldown (after 429)
        now = asyncio.get_event_loop().time()
        if now < self._limited_until:
            wait = self._limited_until - now
            logger.warning(f"[{self.SOURCE_NAME}] Cooldown active, waiting {wait:.1f}s")
            await asyncio.sleep(wait)

        merged_headers = {**self.DEFAULT_HEADERS, **(headers or {})}
        last_exc: Exception | None = None

        for attempt in range(self.MAX_RETRIES):
            try:
                resp = await self.client.request(
                    method, url,
                    headers=merged_headers,
                    params=params, json=json_body, data=data,
                    timeout=self.TIMEOUT,
                )

                # Rate limited
                if resp.status_code == 429 or "Erişim Sınırı" in resp.text:
                    self._limited_until = asyncio.get_event_loop().time() + self.RATE_LIMIT_COOLDOWN
                    logger.warning(
                        f"[{self.SOURCE_NAME}] Rate limited (429), cooldown {self.RATE_LIMIT_COOLDOWN}s"
                    )
                    raise RateLimitError(self.SOURCE_NAME)

                resp.raise_for_status()
                return resp

            except httpx.HTTPStatusError as e:
                if e.response.status_code in (502, 503, 504) and attempt < self.MAX_RETRIES - 1:
                    # Server error — retry with backoff
                    backoff = 2 ** attempt
                    logger.warning(
                        f"[{self.SOURCE_NAME}] HTTP {e.response.status_code}, "
                        f"retry in {backoff}s (attempt {attempt + 1}/{self.MAX_RETRIES})"
                    )
                    await asyncio.sleep(backoff)
                    last_exc = e
                    continue
                raise
            except (httpx.ConnectError, httpx.ReadTimeout, httpx.WriteTimeout) as e:
                if attempt < self.MAX_RETRIES - 1:
                    backoff = 2 ** attempt
                    logger.warning(
                        f"[{self.SOURCE_NAME}] {type(e).__name__}, retry in {backoff}s"
                    )
                    await asyncio.sleep(backoff)
                    last_exc = e
                    continue
                raise

        raise last_exc or RuntimeError("Unknown request failure")

    # ─── Source-specific methods (implemented by subclasses) ───

    async def search(self, query: str, *, page: int = 1, **opts) -> SearchResponse:
        raise NotImplementedError

    async def get_document(self, doc_id: str) -> LegalDocument | None:
        raise NotImplementedError

    async def list_recent(self, *, days: int = 30, page: int = 1) -> SearchResponse:
        """List recent decisions (used by import pipeline)."""
        raise NotImplementedError


class RateLimitError(Exception):
    """Raised when source returns 429 / 'Erişim Sınırı'."""
    def __init__(self, source: str):
        self.source = source
        super().__init__(f"Rate limited by {source}")


# ─── Rate Limiter (Redis-backed for production) ───────────────────────────────


class RateLimiter:
    """
    Redis-backed rate limiter.
    Falls back to in-memory token bucket if Redis unavailable.

    Usage:
        limiter = RateLimiter(redis_url="redis://localhost:6379")
        await limiter.acquire("yargitay")  # blocks if rate exceeded
    """

    def __init__(self, redis_url: str | None = None):
        self.redis_url = redis_url
        self._redis = None
        self._local_buckets: dict[str, float] = {}  # source -> last_request_time
        self._min_interval: dict[str, float] = {}   # source -> min seconds between requests

    async def connect(self):
        if not self.redis_url:
            logger.info("RateLimiter: no Redis URL, using in-memory fallback")
            return
        try:
            import redis.asyncio as aioredis
            self._redis = await aioredis.from_url(self.redis_url)
            await self._redis.ping()
            logger.info(f"RateLimiter: connected to Redis at {self.redis_url}")
        except Exception as e:
            logger.warning(f"RateLimiter: Redis connection failed ({e}), using in-memory")
            self._redis = None

    async def acquire(self, source: str, rpm: int = 20):
        """Block until a request slot is available."""
        interval = 60.0 / rpm
        if self._redis:
            # Redis-based: use INCR with TTL
            key = f"rate:{source}:{int(asyncio.get_event_loop().time())}"
            count = await self._redis.incr(key)
            if count == 1:
                await self._redis.expire(key, 60)
            if count > rpm:
                await asyncio.sleep(interval)
        else:
            # In-memory fallback
            now = asyncio.get_event_loop().time()
            last = self._local_buckets.get(source, 0)
            elapsed = now - last
            if elapsed < interval:
                await asyncio.sleep(interval - elapsed)
            self._local_buckets[source] = asyncio.get_event_loop().time()


# ─── Yargıtay Connector ───────────────────────────────────────────────────────


class YargitayConnector(BaseConnector):
    """
    Yargıtay karar arama — karararama.yargitay.gov.tr

    Endpoint: POST /Arama/aramaList
    Body: {"aranan": "<query>", "sayfa": <page>, "karakter": "turkce"}
    Returns: HTML table with decision list
    """

    SOURCE_NAME = "yargitay"
    BASE_URL = "https://karararama.yargitay.gov.tr"
    SEARCH_URL = BASE_URL + "/Arama/aramaList"
    DOC_URL = BASE_URL + "/KararGoruntule/{doc_id}"

    async def search(self, query: str, *, page: int = 1, **opts) -> SearchResponse:
        try:
            resp = await self._request(
                "POST", self.SEARCH_URL,
                data={"aranan": query, "sayfa": str(page), "karakter": "turkce"},
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            return self._parse_search_html(resp.text, page)
        except RateLimitError:
            return SearchResponse(total=0, documents=[], has_more=False, rate_limited=True)
        except Exception as e:
            logger.error(f"[yargitay] search error: {e}")
            return SearchResponse(total=0, documents=[], has_more=False, error=str(e))

    def _parse_search_html(self, html: str, current_page: int) -> SearchResponse:
        soup = BeautifulSoup(html, "html.parser")
        docs: list[LegalDocument] = []

        # Each result row
        for row in soup.select("div.karar, table tbody tr"):
            title_el = row.select_one("a, .karar-baslik")
            if not title_el:
                continue
            doc_id = ""
            href = title_el.get("href", "")
            m = re.search(r"[/=]([A-Za-z0-9_-]{10,})", href)
            if m:
                doc_id = m.group(1)

            title = title_el.get_text(strip=True)
            court = "Yargıtay"
            chamber = ""
            decision_number = ""

            # Try to extract chamber + decision number from text
            text = row.get_text(" ", strip=True)
            chamber_m = re.search(r"(\d+\.\s*Hukuk\s*Dairesi|\d+\.\s*Ceza\s*Dairesi|HGK|DİB)", text)
            if chamber_m:
                chamber = chamber_m.group(1)
            num_m = re.search(r"E\.\s*(\d{4}/\d+).*?K\.\s*(\d{4}/\d+)", text)
            if num_m:
                decision_number = f"E. {num_m.group(1)}, K. {num_m.group(2)}"

            date_m = re.search(r"(\d{2})[./](\d{2})[./](\d{4})", text)
            decision_date = None
            if date_m:
                try:
                    decision_date = date(int(date_m.group(3)), int(date_m.group(2)), int(date_m.group(1)))
                except ValueError:
                    pass

            docs.append(LegalDocument(
                source="yargitay", source_doc_id=doc_id, court=court, court_chamber=chamber,
                decision_number=decision_number, case_number="", decision_date=decision_date,
                document_type="decision", title=title, full_text="", summary=text[:300],
                source_url=self.DOC_URL.format(doc_id=doc_id),
            ))

        has_more = len(docs) >= 10
        return SearchResponse(
            total=len(docs), documents=docs, has_more=has_more,
            next_page=current_page + 1 if has_more else None,
        )

    async def get_document(self, doc_id: str) -> LegalDocument | None:
        try:
            resp = await self._request("GET", self.DOC_URL.format(doc_id=doc_id))
            soup = BeautifulSoup(resp.text, "html.parser")
            full_text = soup.select_one(".karar-metin, #kararMetin, .content")
            text = full_text.get_text("\n", strip=True) if full_text else ""
            title = (soup.select_one("h1, h2, .karar-baslik") or soup.select_one("title"))
            title_text = title.get_text(strip=True) if title else doc_id
            return LegalDocument(
                source="yargitay", source_doc_id=doc_id, court="Yargıtay",
                court_chamber="", decision_number="", case_number="",
                decision_date=None, document_type="decision",
                title=title_text, full_text=text, summary=text[:300],
                source_url=self.DOC_URL.format(doc_id=doc_id),
            )
        except Exception as e:
            logger.error(f"[yargitay] get_document error: {e}")
            return None


# ─── Danıştay Connector ───────────────────────────────────────────────────────


class DanistayConnector(BaseConnector):
    """
    Danıştay karar arama — danistaydergiler.adalet.gov.tr

    Endpoint: POST /aramalist
    Body: {"andKelimeler": "<query>", "sayfaNo": <page>}
    """

    SOURCE_NAME = "danistay"
    BASE_URL = "https://danistaydergiler.adalet.gov.tr"
    SEARCH_URL = BASE_URL + "/aramalist"

    async def search(self, query: str, *, page: int = 1, **opts) -> SearchResponse:
        try:
            resp = await self._request(
                "POST", self.SEARCH_URL,
                json={"andKelimeler": query, "sayfaNo": page, "orKelimeler": ""},
            )
            return self._parse_json(resp.json(), page)
        except RateLimitError:
            return SearchResponse(total=0, documents=[], has_more=False, rate_limited=True)
        except Exception as e:
            logger.error(f"[danistay] search error: {e}")
            return SearchResponse(total=0, documents=[], has_more=False, error=str(e))

    def _parse_json(self, data: dict, current_page: int) -> SearchResponse:
        docs: list[LegalDocument] = []
        items = data.get("data", data.get("results", []))
        if not isinstance(items, list):
            items = []
        for item in items:
            doc_id = str(item.get("id", item.get("kararId", "")))
            chamber = item.get("daire", "")
            decision_no = item.get("esasNo", "") + " / " + item.get("kararNo", "")
            title = item.get("baslik", item.get("konu", doc_id))
            text = item.get("metin", item.get("ozet", ""))
            d = item.get("tarih", item.get("kararTarihi", ""))
            decision_date = None
            if d:
                try:
                    decision_date = datetime.fromisoformat(d[:10]).date()
                except Exception:
                    pass
            docs.append(LegalDocument(
                source="danistay", source_doc_id=doc_id, court="Danıştay",
                court_chamber=chamber, decision_number=decision_no.strip(" /"),
                case_number=item.get("esasNo", ""), decision_date=decision_date,
                document_type="decision", title=title, full_text=text, summary=text[:300],
            ))
        total = data.get("totalCount", len(docs))
        has_more = current_page * 10 < total
        return SearchResponse(
            total=total, documents=docs, has_more=has_more,
            next_page=current_page + 1 if has_more else None,
        )


# ─── Emsal (UYAP) Connector ──────────────────────────────────────────────────


class EmsalConnector(BaseConnector):
    """Emsal karar arama — emsal.uyap.gov.tr"""

    SOURCE_NAME = "emsal"
    BASE_URL = "https://emsal.uyap.gov.tr"
    SEARCH_URL = BASE_URL + "/karar-ara"

    async def search(self, query: str, *, page: int = 1, **opts) -> SearchResponse:
        try:
            resp = await self._request(
                "POST", self.SEARCH_URL,
                json={"keyword": query, "page": page, "pageSize": 20},
            )
            data = resp.json()
            docs: list[LegalDocument] = []
            for item in data.get("results", []):
                docs.append(LegalDocument(
                    source="emsal", source_doc_id=str(item.get("id", "")),
                    court=item.get("mahkeme", "Emsal"),
                    court_chamber=item.get("daire", ""),
                    decision_number=item.get("kararNo", ""),
                    case_number=item.get("esasNo", ""),
                    decision_date=None,
                    document_type="decision",
                    title=item.get("baslik", item.get("konu", "")),
                    full_text=item.get("metin", ""),
                    summary=(item.get("metin", "") or "")[:300],
                ))
            total = data.get("totalCount", len(docs))
            has_more = page * 20 < total
            return SearchResponse(
                total=total, documents=docs, has_more=has_more,
                next_page=page + 1 if has_more else None,
            )
        except RateLimitError:
            return SearchResponse(total=0, documents=[], has_more=False, rate_limited=True)
        except Exception as e:
            logger.error(f"[emsal] search error: {e}")
            return SearchResponse(total=0, documents=[], has_more=False, error=str(e))


# ─── AYM Connector ────────────────────────────────────────────────────────────


class AnayasaConnector(BaseConnector):
    """
    Anayasa Mahkemesi — anayasa.gov.tr (resmi JSON API)

    Endpoint: POST /api/core/public/search
    Body: {"keyword": "<query>", "decisionType": "BB|ND", "page": <page>}
    """

    SOURCE_NAME = "aym"
    BASE_URL = "https://www.anayasa.gov.tr"
    SEARCH_URL = BASE_URL + "/api/core/public/search"
    DOC_URL = BASE_URL + "/karar/{doc_id}"

    async def search(self, query: str, *, page: int = 1, kind: str = "BB", **opts) -> SearchResponse:
        try:
            resp = await self._request(
                "POST", self.SEARCH_URL,
                json={"keyword": query, "decisionType": kind, "page": page, "pageSize": 20},
            )
            data = resp.json()
            docs: list[LegalDocument] = []
            for item in data.get("data", data.get("results", [])):
                doc_id = str(item.get("id", item.get("kararId", "")))
                b_no = item.get("basvuruNo", item.get("kararNo", ""))
                docs.append(LegalDocument(
                    source="aym", source_doc_id=doc_id,
                    court="Anayasa Mahkemesi", court_chamber="",
                    decision_number=f"B. No: {b_no}" if kind == "BB" else f"Esas: {b_no}",
                    case_number="", decision_date=None,
                    document_type="decision",
                    title=item.get("baslik", item.get("konu", doc_id)),
                    full_text=item.get("metin", ""),
                    summary=(item.get("ozet", item.get("metin", "")) or "")[:300],
                    keywords=[kind],  # BB = Bireysel Başvuru, ND = Norm Denetimi
                ))
            total = data.get("totalCount", len(docs))
            has_more = page * 20 < total
            return SearchResponse(
                total=total, documents=docs, has_more=has_more,
                next_page=page + 1 if has_more else None,
            )
        except RateLimitError:
            return SearchResponse(total=0, documents=[], has_more=False, rate_limited=True)
        except Exception as e:
            logger.error(f"[aym] search error: {e}")
            return SearchResponse(total=0, documents=[], has_more=False, error=str(e))


# ─── Resmî Gazete Connector ──────────────────────────────────────────────────


class ResmiGazeteConnector(BaseConnector):
    """Resmî Gazete — resmigazete.gov.tr"""

    SOURCE_NAME = "resmi_gazete"
    BASE_URL = "https://www.resmigazete.gov.tr"
    SEARCH_URL = BASE_URL + "/eskiler/arama.html"

    async def search(
        self, query: str, *, page: int = 1,
        date_start: str | None = None, date_end: str | None = None, **opts
    ) -> SearchResponse:
        try:
            params = {"aranan": query, "sayfa": str(page)}
            if date_start:
                params["t1"] = date_start
            if date_end:
                params["t2"] = date_end
            resp = await self._request("GET", self.SEARCH_URL, params=params)
            return self._parse_search_html(resp.text, page)
        except RateLimitError:
            return SearchResponse(total=0, documents=[], has_more=False, rate_limited=True)
        except Exception as e:
            logger.error(f"[resmi_gazete] search error: {e}")
            return SearchResponse(total=0, documents=[], has_more=False, error=str(e))

    def _parse_search_html(self, html: str, current_page: int) -> SearchResponse:
        soup = BeautifulSoup(html, "html.parser")
        docs: list[LegalDocument] = []
        for row in soup.select("div.arama-sonuc, table tbody tr"):
            title_el = row.select_one("a")
            if not title_el:
                continue
            title = title_el.get_text(strip=True)
            href = title_el.get("href", "")
            doc_id = href.rsplit("/", 1)[-1].replace(".htm", "")
            text = row.get_text(" ", strip=True)
            date_m = re.search(r"(\d{2})[./](\d{2})[./](\d{4})", text)
            decision_date = None
            if date_m:
                try:
                    decision_date = date(int(date_m.group(3)), int(date_m.group(2)), int(date_m.group(1)))
                except ValueError:
                    pass
            docs.append(LegalDocument(
                source="resmi_gazete", source_doc_id=doc_id,
                court="Resmî Gazete", court_chamber="",
                decision_number=doc_id, case_number="",
                decision_date=decision_date, document_type="regulation",
                title=title, full_text="", summary=text[:300],
                source_url=urljoin(self.BASE_URL, href),
            ))
        has_more = len(docs) >= 10
        return SearchResponse(
            total=len(docs), documents=docs, has_more=has_more,
            next_page=current_page + 1 if has_more else None,
        )


# ─── Mevzuat Connector ────────────────────────────────────────────────────────


class MevzuatConnector(BaseConnector):
    """Mevzuat — mevzuat.gov.tr (kanunlar, KHK'ler, yönetmelikler)"""

    SOURCE_NAME = "mevzuat"
    BASE_URL = "https://www.mevzuat.gov.tr"
    SEARCH_URL = BASE_URL + "/anasayfa/searchMevzuat"
    DOC_URL = BASE_URL + "/mevzuatmetin/{doc_id}"

    async def search(self, query: str, *, page: int = 1, **opts) -> SearchResponse:
        try:
            resp = await self._request(
                "POST", self.SEARCH_URL,
                json={"aranan": query, "sayfa": page, "tur": "kanun"},
            )
            data = resp.json()
            docs: list[LegalDocument] = []
            for item in data.get("results", []):
                doc_id = str(item.get("id", ""))
                docs.append(LegalDocument(
                    source="mevzuat", source_doc_id=doc_id,
                    court="Mevzuat", court_chamber="",
                    decision_number=item.get("mevzuatNo", ""),
                    case_number="",
                    decision_date=None,
                    document_type="statute",
                    title=item.get("adi", item.get("baslik", doc_id)),
                    full_text="",  # fetched on demand via get_document
                    summary=item.get("ozet", ""),
                ))
            total = data.get("totalCount", len(docs))
            has_more = page * 20 < total
            return SearchResponse(
                total=total, documents=docs, has_more=has_more,
                next_page=page + 1 if has_more else None,
            )
        except RateLimitError:
            return SearchResponse(total=0, documents=[], has_more=False, rate_limited=True)
        except Exception as e:
            logger.error(f"[mevzuat] search error: {e}")
            return SearchResponse(total=0, documents=[], has_more=False, error=str(e))


# ─── Connector Registry ───────────────────────────────────────────────────────


CONNECTORS: dict[str, type[BaseConnector]] = {
    "yargitay": YargitayConnector,
    "danistay": DanistayConnector,
    "emsal": EmsalConnector,
    "aym": AnayasaConnector,
    "resmi_gazete": ResmiGazeteConnector,
    "mevzuat": MevzuatConnector,
}


def get_connector(source: str) -> type[BaseConnector]:
    cls = CONNECTORS.get(source)
    if not cls:
        raise ValueError(f"Unknown source: {source}. Available: {list(CONNECTORS.keys())}")
    return cls
