"""BetterSaul MCP sağlık kontrolü — JSON satırı yazar."""
from __future__ import annotations

import json
import os
import sys


def main() -> None:
    from bettersaul_mcp.license_gate import MESSAGE, blocked

    if blocked():
        print(json.dumps({"ok": False, "url": "", "error": MESSAGE}, ensure_ascii=False))
        raise SystemExit(2)
    url = os.environ.get("BS_MCP_URL", "https://127.0.0.1:8000/mcp")
    try:
        from mcp import ClientSession
        import anyio
        from bettersaul_mcp.tls import open_mcp

        async def _list() -> list[str]:
            async with open_mcp(url) as streams:
                r, w = streams[0], streams[1]
                async with ClientSession(r, w) as s:
                    await s.initialize()
                    res = await s.list_tools()
                    return [t.name for t in res.tools]

        tools = anyio.run(_list)
        print(json.dumps({"ok": True, "url": url, "tools": tools}, ensure_ascii=False))
    except Exception as exc:
        msg = str(exc).split("\n")[0]
        if "TaskGroup" in msg or "unhandled errors" in msg:
            msg = "sunucu kapalı veya henüz hazır değil"
        print(json.dumps({"ok": False, "url": url, "error": msg}, ensure_ascii=False))
        raise SystemExit(1)


if __name__ == "__main__":
    main()
