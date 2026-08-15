"""Verifica que a resolução instalada não regrediu frente a requirements.lock.

O CI instala a partir de ``requirements.txt`` (faixas). Para detectar um salto
de versão que quebre o app ANTES do deploy, comparamos as versões **top-level**
instaladas contra as pinadas no ``requirements.lock``:

- todo pacote do lock que também está instalado deve ter versão ≥ a do lock;
- os pacotes top-level do ``requirements.txt`` devem estar presentes.

Uso:
    python scripts/check_lock.py [--list]

Sem --list: exit 0 se tudo dentro; 1 se algum regrediu.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read_lock() -> dict[str, str]:
    out: dict[str, str] = {}
    for line in (ROOT / "requirements.lock").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "==" in line:
            name, ver = line.split("==", 1)
            out[name.lower()] = ver.strip()
    return out


def _installed() -> dict[str, str]:
    raw = subprocess.run(
        [sys.executable, "-m", "pip", "list", "--format=freeze"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    out: dict[str, str] = {}
    for line in raw.splitlines():
        if "==" in line:
            name, ver = line.split("==", 1)
            out[name.lower()] = ver.strip()
    return out


def _version_geq(a: str, b: str) -> bool:
    """Compara versões simples dotted (Major.Minor.Patch...). Suporta sufixos."""
    va = [int(x) for x in a.split("+")[0].replace("-", ".").split(".") if x.isdigit()]
    vb = [int(x) for x in b.split("+")[0].replace("-", ".").split(".") if x.isdigit()]
    for x, y in zip(va, vb):
        if x != y:
            return x > y
    return len(va) >= len(vb)


def main() -> int:
    lock = _read_lock()
    inst = _installed()
    problems: list[str] = []

    # 1) todo pacote do lock instalado deve estar >= lock
    for name, lock_ver in sorted(lock.items()):
        if name in inst:
            if not _version_geq(inst[name], lock_ver):
                problems.append(f"{name} {inst[name]} < lock {lock_ver}")
            elif "--list" in sys.argv:
                print(f"ok {name} {inst[name]} >= {lock_ver}")
        elif "--list" in sys.argv:
            print(f"info {name}: não instalado")

    # 2) top-level do requirements.txt presentes
    for line in (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or ";" in line:
            continue
        name = line.split("[")[0].split(">")[0].split("<")[0].split("=")[0].strip()
        if name and name.lower() not in inst:
            problems.append(f"top-level ausente: {name}")

    if problems:
        print("FALHAS (resolução regrediu vs lock):")
        for p in problems:
            print(f"  - {p}")
        return 1
    print("TUDO OK — resolução compatível com requirements.lock.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())