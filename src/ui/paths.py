"""Caminhos de assets e raiz do projeto."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / "assets"
LOGO_PATH = ASSETS / "logo" / "TD_logo.png"
ICON_PATH = ASSETS / "icon" / "TD_icon.png"
