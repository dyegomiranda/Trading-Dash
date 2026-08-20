"""Carregador de fundamentos históricos Point-in-Time.

Lê ``data/reference/pit_snapshots.json``. A origem vem no campo ``origin``:

- ``seed_curated`` — semente offline para o motor funcionar sem baixar a CVM.
  Números ilustrativos; **não** são DFP/ITR parseados.
- ``cvm_dfp_itr`` — gerado por ``scripts/download_cvm_data.py --build`` a
  partir dos ZIPs oficiais (ROE/margem/alavancagem). Preço e DY continuam
  vindo do pregão do dia no motor.

O backtest só deixa de ter look-ahead contábil quando ``origin=cvm_dfp_itr``
(e mesmo assim o DY usa TTM dos dividendos históricos, não a CVM).
"""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

import pandas as pd

from src.config import DATA_DIR
from src.data.schemas import coerce_fundamentals

PIT_SNAPSHOTS_PATH = DATA_DIR / "reference" / "pit_snapshots.json"


def _read_pit_payload() -> dict[str, Any]:
    if not PIT_SNAPSHOTS_PATH.exists():
        return {}
    try:
        return json.loads(PIT_SNAPSHOTS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


@lru_cache(maxsize=1)
def load_pit_meta() -> dict[str, Any]:
    data = _read_pit_payload()
    origin = str(data.get("origin") or "seed_curated")
    return {
        "origin": origin,
        "origin_note": str(data.get("origin_note") or ""),
        "description": str(data.get("description") or ""),
        "version": str(data.get("version") or ""),
        "updated_at": str(data.get("updated_at") or ""),
        "is_cvm": origin.startswith("cvm"),
    }


def get_pit_origin() -> str:
    return str(load_pit_meta().get("origin") or "seed_curated")


@lru_cache(maxsize=1)
def load_pit_fundamentals() -> dict[str, pd.DataFrame]:
    """Carrega os snapshots trimestrais indexados por data (YYYY-MM-DD)."""
    data = _read_pit_payload()
    quarters = data.get("quarters") or {}
    origin = str(data.get("origin") or "seed_curated")
    source_default = "cvm_pit" if origin.startswith("cvm") else "pit_seed"

    result: dict[str, pd.DataFrame] = {}
    for q_date, rows in quarters.items():
        if not rows:
            continue
        df = pd.DataFrame(rows)
        if "source" not in df.columns:
            df["source"] = source_default
        if "data_quality" not in df.columns:
            df["data_quality"] = "pit_historical"
        if "as_of" not in df.columns:
            df["as_of"] = q_date
        result[q_date] = coerce_fundamentals(df, op="pit_loader")
    return result


def has_pit_data() -> bool:
    """Verifica se a base de snapshots históricos point-in-time está disponível."""
    snaps = load_pit_fundamentals()
    return len(snaps) > 0


def pit_badge() -> tuple[str, str] | None:
    """Badge curto para o cabeçalho: (texto, variante) ou None."""
    if not has_pit_data():
        return None
    origin = get_pit_origin()
    if origin.startswith("cvm"):
        return ("PIT CVM", "pit")
    return ("PIT semente", "pit")


def get_pit_dates() -> list[str]:
    """Retorna as datas dos trimestres disponíveis em ordem cronológica."""
    snaps = load_pit_fundamentals()
    return sorted(snaps.keys())


def get_pit_coverage_summary() -> dict[str, Any]:
    """Retorna um resumo de cobertura (número de trimestres, tickers e período coberto)."""
    snaps = load_pit_fundamentals()
    if not snaps:
        return {"n_quarters": 0, "dates": [], "tickers_count": 0, "tickers": []}

    dates = sorted(snaps.keys())
    all_tickers: set[str] = set()
    for df in snaps.values():
        if "ticker" in df.columns:
            all_tickers.update(df["ticker"].dropna().unique())

    return {
        "n_quarters": len(snaps),
        "start_date": dates[0],
        "end_date": dates[-1],
        "dates": dates,
        "tickers_count": len(all_tickers),
        "tickers": sorted(all_tickers),
    }
