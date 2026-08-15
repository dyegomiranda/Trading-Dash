"""Serviços de aplicação (cache-friendly) usados pela UI Streamlit."""

from __future__ import annotations

from typing import Any

import pandas as pd

from src.config import get_settings
from src.data.providers import ProviderName, get_provider, is_realtime_provider
from src.data.universe import get_universe
from src.thesis.macro import macro_tilt_from_settings
from src.thesis.scoring import ScoreResult, recommend_weights, score_universe
from src.utils import utcnow


def load_scored_universe(
    provider_name: ProviderName = "demo",
    min_score: float | None = None,
    strict_filters: bool = True,
    tickers: list[str] | None = None,
    *,
    universe_mode: str = "auto",
) -> ScoreResult:
    """Carrega e pontua o universo.

    universe_mode:
      - auto: demo=full, yfinance=core (rápido)
      - core / full: força o modo
    """
    provider = get_provider(provider_name)
    if tickers is not None:
        universe = tickers
    else:
        mode = universe_mode
        if mode == "auto":
            mode = "core" if is_realtime_provider(provider_name) else "full"
        universe = get_universe(mode=mode)
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
        scored.filtered,
        top_n=top_n,
        core_weight=settings.core_weight,
        satellite_weight=settings.satellite_weight,
        max_position_pct=settings.max_position_pct,
        macro_tilt=macro_tilt_from_settings(settings),
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
    """Percentual no locale ativo — delega ao hook de formatação."""
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return "—"
    from src.format_hooks import format_pct_hook

    return format_pct_hook(x, decimals)


def format_brl(x: float | None) -> str:
    """Moeda no locale ativo — delega ao hook de formatação."""
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return "—"
    from src.format_hooks import format_brl_hook

    return format_brl_hook(x)


def thesis_summary() -> dict[str, Any]:
    s = get_settings()
    return {
        "name": "Quality Dividend (renda passiva)",
        "description": (
            "Empresas de qualidade com dividendos sustentáveis e reinvestimento. "
            "Base em setores mais previsíveis; complemento com um pouco mais de flexibilidade."
        ),
        "core_weight": s.core_weight,
        "satellite_weight": s.satellite_weight,
        "preferred_dy": f"{s.preferred_dy_min:.0%}–{s.preferred_dy_max:.0%}",
        "min_score": s.rebalance_min_score,
        "as_of": utcnow().strftime("%Y-%m-%d %H:%M UTC"),
    }
