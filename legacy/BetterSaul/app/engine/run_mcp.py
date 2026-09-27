import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from bettersaul_mcp.license_gate import enforce

enforce()
from bettersaul_mcp.__main__ import main

if __name__ == "__main__":
    main()
