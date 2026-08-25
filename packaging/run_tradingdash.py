"""Ponto de entrada do executável (PyInstaller): sobe o Streamlit local."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def bundle_dir() -> Path:
    meipass = getattr(sys, "_MEIPASS", None)
    if getattr(sys, "frozen", False) and meipass:
        return Path(meipass)
    return Path(__file__).resolve().parents[1]


def main() -> None:
    base = bundle_dir()
    os.chdir(base)
    if str(base) not in sys.path:
        sys.path.insert(0, str(base))
    app = str(base / "app.py")
    os.environ.setdefault("STREAMLIT_BROWSER_GATHER_USAGE_STATS", "false")
    os.environ.setdefault("STREAMLIT_GLOBAL_DEVELOPMENT_MODE", "false")
    from streamlit.web import cli as stcli

    sys.argv = [
        "streamlit",
        "run",
        app,
        "--global.developmentMode=false",
        "--server.headless=false",
        "--browser.gatherUsageStats=false",
    ]
    raise SystemExit(stcli.main())


if __name__ == "__main__":
    main()
