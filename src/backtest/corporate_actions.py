"""Splits e bonificações no ensaio — sem misturar com ajuste de dividendo.

Política (honesta):
- Marcação a mercado usa ``close`` (não ``adj_close``). Adj Close do Yahoo
  já desconta dividendo; se usássemos isso E creditássemos o provento no
  caixa, o retorno seria contado duas vezes.
- Split / bonificação (aumento de quantidade, preço cai na mesma proporção):
  se a série de preços ainda for *crua*, multiplicamos as ações e dividimos
  o preço médio. Se a série já vier split-adjusted (caso típico do Yahoo
  com auto_adjust=False), **não** redimensionamos a posição.
- Subscrição / direito de compra: **não exercida**. O paper não desembolsa
  caixa para acompanhar a oferta; isso é um viés levemente negativo e
  explícito.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

# Fatores clássicos (ações novas / ações velhas). 1.10 = bonificação 10%.
# 1.05 é ruído demais para inferir de preço; só entra via calendário da fonte.
_CLASSIC_RATIOS = (2.0, 3.0, 4.0, 5.0, 10.0, 1.5, 1.25, 0.5, 1.0 / 3.0)


def empty_splits() -> pd.DataFrame:
    return pd.DataFrame(columns=["date", "ticker", "ratio", "source"])


def normalize_splits(df: pd.DataFrame | None) -> pd.DataFrame:
    if df is None or getattr(df, "empty", True):
        return empty_splits()
    out = df.copy()
    out["date"] = pd.to_datetime(out["date"], errors="coerce").dt.tz_localize(None).dt.normalize()
    out["ticker"] = out["ticker"].astype(str).str.upper()
    out["ratio"] = pd.to_numeric(out["ratio"], errors="coerce")
    if "source" not in out.columns:
        out["source"] = "provider"
    out = out.dropna(subset=["date", "ticker", "ratio"])
    out = out[out["ratio"] > 0]
    out = out[out["ratio"] != 1.0]
    return out.reset_index(drop=True)


def prices_look_raw(prev_close: float, next_close: float, ratio: float) -> bool | None:
    """True = série crua (aplicar split nas ações); False = já ajustada; None = ambíguo."""
    try:
        prev_c = float(prev_close)
        next_c = float(next_close)
        r = float(ratio)
    except (TypeError, ValueError):
        return None
    if prev_c <= 0 or next_c <= 0 or r <= 0 or r == 1.0:
        return None
    expected_raw = prev_c / r
    raw_err = abs(next_c / expected_raw - 1.0)
    adj_err = abs(next_c / prev_c - 1.0)
    if raw_err < 0.12 and raw_err < adj_err:
        return True
    if adj_err < 0.12:
        return False
    return None


def infer_ratio_from_prices(prev_close: float, next_close: float) -> float | None:
    """Infere split clássico se o preço caiu/subiu perto de 1/2, 1/3, …"""
    try:
        prev_c = float(prev_close)
        next_c = float(next_close)
    except (TypeError, ValueError):
        return None
    if prev_c <= 0 or next_c <= 0:
        return None
    implied = prev_c / next_c
    for r in _CLASSIC_RATIOS:
        if abs(implied / r - 1.0) <= 0.06:
            return float(r)
    return None


def infer_splits_from_close(close: pd.DataFrame) -> pd.DataFrame:
    """Percorre o pivot date×ticker e marca saltos clássicos de split."""
    rows: list[dict[str, Any]] = []
    if close is None or close.empty:
        return empty_splits()
    px = close.sort_index()
    prev = px.shift(1)
    for ticker in px.columns:
        for day in px.index:
            p0 = prev.at[day, ticker] if day in prev.index else float("nan")
            p1 = px.at[day, ticker]
            if pd.isna(p0) or pd.isna(p1):
                continue
            ratio = infer_ratio_from_prices(float(p0), float(p1))
            if ratio is None:
                continue
            rows.append(
                {
                    "date": pd.Timestamp(day).normalize(),
                    "ticker": str(ticker),
                    "ratio": ratio,
                    "source": "inferred",
                }
            )
    return normalize_splits(pd.DataFrame(rows) if rows else None)


def merge_splits(*frames: pd.DataFrame) -> pd.DataFrame:
    parts = [normalize_splits(f) for f in frames]
    parts = [p for p in parts if not p.empty]
    if not parts:
        return empty_splits()
    out = pd.concat(parts, ignore_index=True)
    # calendário da fonte vence inferência no mesmo dia+ticker
    out["_rank"] = out["source"].map(lambda s: 0 if s == "inferred" else 1)
    out = out.sort_values(["ticker", "date", "_rank"])
    out = out.drop_duplicates(subset=["ticker", "date"], keep="last")
    return out.drop(columns=["_rank"]).reset_index(drop=True)


def splits_on_day(splits: pd.DataFrame, day: pd.Timestamp) -> pd.DataFrame:
    if splits is None or splits.empty:
        return empty_splits()
    d = pd.Timestamp(day).normalize()
    return splits[splits["date"] == d]
