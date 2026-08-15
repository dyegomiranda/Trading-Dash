"""Pacote: deps — resolução instalada compatível com requirements.lock.

Roda `scripts/check_lock.py` (comparação de versões top-level instaladas contra
o lock). Sinaliza regressão de dependência que quebraria o app após deploy.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_lock_in_sync_with_installed():
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "check_lock.py")],
        capture_output=True,
        text=True,
        cwd=ROOT,
        timeout=60,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr