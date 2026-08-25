"""Gera o bundle PyInstaller (pasta TradingDash) a partir da raiz do repo."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = Path(__file__).resolve().parent / "TradingDash.spec"


def main() -> int:
    os.chdir(ROOT)
    cmd = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", str(SPEC)]
    print(" ".join(cmd))
    return subprocess.call(cmd)


if __name__ == "__main__":
    raise SystemExit(main())
