"""Canlılık: yalnızca resmi kaynaklar. Wikipedia / DDG üslubu yok."""
from __future__ import annotations

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)


def _client():
    import httpx

    return httpx.Client(
        timeout=httpx.Timeout(8.0, connect=4.0),
        follow_redirects=True,
        headers={
            "User-Agent": UA,
            "Accept": "text/html,*/*;q=0.8",
            "Accept-Language": "tr-TR,tr;q=0.9",
        },
    )


def internet_reachable() -> bool:
    for url in ("https://www.mevzuat.gov.tr", "https://www.resmigazete.gov.tr"):
        try:
            with _client() as cli:
                res = cli.head(url, timeout=5.0)
                if res.status_code < 500:
                    return True
        except Exception:
            continue
    return False


def fetch_style_hints(kind: str = "") -> tuple[str, int]:
    """Wikipedia / DDG kapalı; dilekçe ve sohbete üslup kalıbı gitmez."""
    return "", 0
