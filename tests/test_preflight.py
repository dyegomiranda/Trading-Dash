"""Pacote: deploy — pre-flight garante que o app sobe em ambiente limpo.

Roda o script `deploy/preflight.py` (que sobe o app via AppTest com a fonte
forçada para demo, sem rede) e exige saída 0. Detecta quebra de deploy que
os testes unitários não pegam (import de módulo, referência versionada, boot
do entrypoint).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_deploy_preflight_passes():
    proc = subprocess.run(
        [sys.executable, str(ROOT / "deploy" / "preflight.py")],
        capture_output=True,
        text=True,
        cwd=ROOT,
        timeout=120,
    )
    assert proc.returncode == 0, (
        f"preflight falhou (exit {proc.returncode})\n"
        f"--- stdout ---\n{proc.stdout}\n--- stderr ---\n{proc.stderr}"
    )
    assert "TUDO OK" in proc.stdout