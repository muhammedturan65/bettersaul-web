import argparse
import os
import sys

from .license_gate import enforce
from .server import run_http, run_stdio


def main() -> None:
    enforce()
    parser = argparse.ArgumentParser(prog="bettersaul_mcp")
    parser.add_argument("--http", action="store_true", default=False)
    parser.add_argument("--stdio", action="store_true", default=False)
    parser.add_argument("--port", type=int, default=int(os.environ.get("BETTERSAUL_MCP_PORT") or os.environ.get("PORT") or 8000))
    parser.add_argument("--host", default=os.environ.get("BETTERSAUL_MCP_HOST", "127.0.0.1"))
    parser.add_argument("--ssl-cert", default=os.environ.get("BETTERSAUL_MCP_SSL_CERT", ""))
    parser.add_argument("--ssl-key", default=os.environ.get("BETTERSAUL_MCP_SSL_KEY", ""))
    args, _ = parser.parse_known_args()
    if args.stdio:
        print("BetterSaul MCP stdio", file=sys.stderr, flush=True)
        run_stdio()
        return
    secure = bool(args.ssl_cert and args.ssl_key)
    scheme = "https" if secure else "http"
    print(f"BetterSaul MCP {scheme}://{args.host}:{args.port}/mcp", file=sys.stderr, flush=True)
    run_http(args.host, args.port, ssl_cert=args.ssl_cert if secure else "", ssl_key=args.ssl_key if secure else "")


if __name__ == "__main__":
    main()
