# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec — inclui Streamlit, páginas, assets e JSON de referência."""

from pathlib import Path

from PyInstaller.building.build_main import COLLECT, EXE, PYZ, Analysis
from PyInstaller.utils.hooks import collect_all, collect_data_files

ROOT = Path(SPECPATH).resolve().parent

datas = []
binaries = []
hiddenimports = [
    "streamlit",
    "streamlit.web.cli",
    "streamlit.runtime.scriptrunner.magic_funcs",
    "plotly",
    "yfinance",
    "pandas",
    "numpy",
    "pydantic",
    "pydantic_settings",
    "tenacity",
    "altair",
    "pyarrow",
]

for pkg in ("streamlit", "altair", "plotly", "jsonschema"):
    try:
        d, b, h = collect_all(pkg)
        datas += d
        binaries += b
        hiddenimports += h
    except Exception:
        pass

datas += collect_data_files("streamlit")
datas += [
    (str(ROOT / "app.py"), "."),
    (str(ROOT / "app_pages"), "app_pages"),
    (str(ROOT / "src"), "src"),
    (str(ROOT / "assets"), "assets"),
    (str(ROOT / "data" / "reference"), "data/reference"),
    (str(ROOT / ".streamlit"), ".streamlit"),
]

a = Analysis(
    [str(ROOT / "packaging" / "run_tradingdash.py")],
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="TradingDash",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="TradingDash",
)
