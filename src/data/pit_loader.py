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

from src.config import DATA_DIR, REFERENCE_DIR
from src.data.schemas import coerce_fundamentals


def pit_snapshots_path():
    """JSON gerado pelo usuário (cache) tem prioridade; senão o arquivo versionado no pacote."""
    override = DATA_DIR / "reference" / "pit_snapshots.json"
    if override.exists():
        return override
    return REFERENCE_DIR / "pit_snapshots.json"


PIT_SNAPSHOTS_PATH = pit_snapshots_path()


def _read_pit_payload() -> dict[str, Any]:
    path = pit_snapshots_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
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


_PIT_OVERLAY_COLS = (
    "roe",
    "roa",
    "net_margin",
    "debt_equity",
    "payout",
    "fcf_positive",
    "current_ratio",
    "fcf",
)


@lru_cache(maxsize=1)
def latest_fundamentals_snapshot() -> pd.DataFrame:
    """Último trimestre CVM por ticker — para completar o que o Yahoo não trouxe."""
    snaps = load_pit_fundamentals()
    if not snaps:
        return pd.DataFrame()
    frames: list[pd.DataFrame] = []
    for dt, df in snaps.items():
        if df is None or df.empty or "ticker" not in df.columns:
            continue
        part = df.copy()
        part["as_of"] = str(dt)
        frames.append(part)
    if not frames:
        return pd.DataFrame()
    all_df = pd.concat(frames, ignore_index=True)
    all_df = all_df.sort_values("as_of")
    return all_df.drop_duplicates(subset=["ticker"], keep="last")


def overlay_pit_on_fundamentals(df: pd.DataFrame) -> pd.DataFrame:
    """Preenche ROE/dívida/FCF vazios com o último DFP/ITR. Não inventa preço nem DY."""
    if df is None or df.empty or "ticker" not in df.columns:
        return df
    pit = latest_fundamentals_snapshot()
    if pit is None or pit.empty or "ticker" not in pit.columns:
        return df
    cols = [c for c in _PIT_OVERLAY_COLS if c in pit.columns]
    if not cols:
        return df
    right = pit[["ticker"] + cols].copy()
    right["ticker"] = right["ticker"].astype(str)
    out = df.copy()
    out["ticker"] = out["ticker"].astype(str)
    merged = out.merge(right, on="ticker", how="left", suffixes=("", "_pit"))
    filled_roe = False
    if "roe" in merged.columns and "roe_pit" in merged.columns:
        filled_roe = merged["roe"].isna() & merged["roe_pit"].notna()
    for c in cols:
        pit_c = f"{c}_pit"
        if pit_c not in merged.columns:
            continue
        if c not in merged.columns:
            merged[c] = merged[pit_c]
        else:
            merged[c] = merged[c].where(merged[c].notna(), merged[pit_c])
        merged = merged.drop(columns=[pit_c])
    if "data_quality" in merged.columns and isinstance(filled_roe, pd.Series):
        merged.loc[filled_roe, "data_quality"] = "pit_overlay"
    return merged


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
