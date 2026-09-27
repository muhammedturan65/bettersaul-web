"""Yerel BetterSaul MCP için TLS yardımcıları.

Sunucu 127.0.0.1 üzerinde kendinden imzalı bir sertifikayla HTTPS açar.
İstemciler (sağlık kontrolü ve motor) BS_MCP_CA ortam değişkenindeki
sertifikayı sistem köklerinin ÜZERİNE ekleyerek güvenir; sistem kök
deposu değiştirilmez, kamu sitelerine giden TLS bozulmaz.
"""
from __future__ import annotations

import contextlib
import os
import ssl


def mcp_ssl_context() -> ssl.SSLContext | bool:
    """Varsayılan kökler + (varsa) BS_MCP_CA yerel sertifikası."""
    ca = (os.environ.get("BS_MCP_CA") or "").strip()
    ctx = ssl.create_default_context()
    if ca and os.path.isfile(ca):
        try:
            ctx.load_verify_locations(cafile=ca)
        except Exception:
            pass
    return ctx


@contextlib.asynccontextmanager
async def open_mcp(url: str):
    """MCP streamable-http akışlarını açar; https ise yerel CA'ya güvenir."""
    from mcp.client import streamable_http as _sh

    connect = getattr(_sh, "streamable_http_client", None) or getattr(
        _sh, "streamablehttp_client"
    )
    if not url.lower().startswith("https://"):
        async with connect(url) as streams:
            yield streams
        return

    import httpx2

    client = httpx2.AsyncClient(
        timeout=httpx2.Timeout(30, read=300),
        verify=mcp_ssl_context(),
    )
    async with client:
        async with connect(url, http_client=client) as streams:
            yield streams
