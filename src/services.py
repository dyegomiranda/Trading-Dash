"""Serviços de aplicação (cache-friendly) usados pela UI Streamlit."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd

from src.config import get_settings
from src.data.providers import ProviderName, get_provider
from src.data.universe import get_universe
from src.thesis.scoring import ScoreResult, recommend_weights, score_universe


def load_scored_universe(
    provider_name: ProviderName = "demo",
    min_score: float | None = None,
    strict_filters: bool = False,
    tickers: list[str] | None = None,
) -> ScoreResult:
    provider = get_provider(provider_name)
    universe = tickers or get_universe()
    fundamentals = provider.get_fundamentals(universe)
    settings = get_settings()
    return score_universe(
        fundamentals,
        settings=settings,
        min_score=min_score,
        strict_filters=strict_filters,
    )


def build_recommendations(
    scored: ScoreResult,
    top_n: int | None = None,
) -> pd.DataFrame:
    settings = get_settings()
    top_n = top_n or settings.default_top_n
    return recommend_weights(
        scored.filtered if not scored.filtered.empty else scored.scored,
        top_n=top_n,
        core_weight=settings.core_weight,
        satellite_weight=settings.satellite_weight,
        max_position_pct=settings.max_position_pct,
    )


def prices_dict_from_fundamentals(fundamentals: pd.DataFrame) -> dict[str, float]:
    if fundamentals.empty:
        return {}
    out = {}
    for _, row in fundamentals.iterrows():
        t = row.get("ticker")
        p = row.get("price")
        if t is not None and p is not None and pd.notna(p) and float(p) > 0:
            out[str(t)] = float(p)
    return out


def format_pct(x: float | None, decimals: int = 1) -> str:
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return "—"
    return f"{x * 100:.{decimals}f}%"


def format_brl(x: float | None) -> str:
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return "—"
    return f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def thesis_summary() -> dict[str, Any]:
    s = get_settings()
    return {
        "name": "Quality Dividend (renda passiva)",
        "description": (
            "Empresas de qualidade com dividendos sustentáveis e reinvestimento. "
            "Core em setores mais previsíveis; satélite com yield um pouco maior."
        ),
        "core_weight": s.core_weight,
        "satellite_weight": s.satellite_weight,
        "preferred_dy": f"{s.preferred_dy_min:.0%}–{s.preferred_dy_max:.0%}",
        "min_score": s.rebalance_min_score,
        "as_of": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
    }
