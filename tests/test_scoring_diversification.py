"""Testes de diversificação e armadilha de yield."""

from __future__ import annotations

import pandas as pd

from src.thesis.scoring import composite_score, recommend_weights, score_dividends
from src.config import get_settings


def test_high_yield_trap_lowers_dividend_score():
    settings = get_settings()
    healthy = pd.Series(
        {
            "dividend_yield": 0.06,
            "payout": 0.5,
            "dividend_cagr_5y": 0.04,
            "years_paying_dividend": 8,
            "fcf_positive": True,
            "net_debt_ebitda": 1.0,
        }
    )
    trap = pd.Series(
        {
            "dividend_yield": 0.18,
            "payout": 1.2,
            "dividend_cagr_5y": -0.05,
            "years_paying_dividend": 2,
            "fcf_positive": False,
            "net_debt_ebitda": 5.0,
        }
    )
    assert score_dividends(healthy, settings) > score_dividends(trap, settings)


def test_recommend_weights_respects_position_cap():
    rows = []
    for i in range(12):
        rows.append(
            {
                "ticker": f"T{i:02d}",
                "score_total": 90 - i,
                "bucket": "core" if i < 8 else "satellite",
                "sector": f"S{i % 4}",
                "price": 10.0,
            }
        )
    df = pd.DataFrame(rows)
    recs = recommend_weights(df, top_n=10, max_position_pct=0.10, max_sector_pct=0.35)
    assert not recs.empty
    assert float(recs["target_weight"].max()) <= 0.10 + 1e-6
    # Pode ficar um pouco de caixa residual se caps impedirem 100% investido
    assert 0.70 <= float(recs["target_weight"].sum()) <= 1.0 + 1e-6


def test_missing_pillar_is_not_fifty():
    empty_q = pd.Series({"price": 20, "dividend_yield": 0.06})
    scored = composite_score(empty_q)
    assert scored["score_quality"] is None or (
        scored["score_quality"] != scored["score_quality"]
    )
    assert scored["eligible"] is False
    assert scored["score_total"] < 50.0


def test_incomplete_data_lowers_total():
    full = pd.Series(
        {
            "roe": 0.2,
            "roic": 0.18,
            "net_margin": 0.15,
            "ebitda_margin": 0.25,
            "fcf_positive": True,
            "dividend_yield": 0.06,
            "payout": 0.5,
            "dividend_cagr_5y": 0.03,
            "years_paying_dividend": 10,
            "net_debt_ebitda": 1.0,
            "debt_equity": 0.5,
            "current_ratio": 1.5,
            "interest_coverage": 8,
            "fcf_yield": 0.05,
            "pe": 10,
            "pb": 1.5,
            "ev_ebitda": 7,
            "peg": 1.0,
            "price": 20,
        }
    )
    emptyish = pd.Series({"price": 20, "dividend_yield": 0.06})
    assert composite_score(full)["score_total"] > composite_score(emptyish)["score_total"]
