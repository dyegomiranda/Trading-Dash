"""Pacote: narrativa da tese em português claro (sem LLM).

Garante que ``build_stock_narrative`` e ``build_portfolio_summary`` gerem
texto honesto (nunca inventam dado) e que não quebrem com linhas carentes.
"""

from __future__ import annotations

import pandas as pd

from src.thesis.narrative import build_portfolio_summary, build_stock_narrative


def _row(**kw) -> pd.Series:
    base = {
        "ticker": "PETR4",
        "name": "Petrobras",
        "sector": "Energy",
        "price": 40.0,
        "score_total": 72.0,
        "score_quality": 60.0,
        "score_dividends": 70.0,
        "score_financial_health": 50.0,
        "score_valuation": 65.0,
        "bucket": "core",
        "dividend_yield": 0.08,
        "roe": 0.20,
        "payout": 0.55,
        "net_debt_ebitda": 1.2,
        "pe": 9.0,
        "fcf_positive": True,
        "quality_label": "Dados ok",
        "data_completeness_pct": 75,
    }
    base.update(kw)
    return pd.Series(base)


def test_narrative_mentions_ticker_and_sector():
    txt = build_stock_narrative(_row())
    assert "PETR4" in txt
    assert "Energy" in txt
    assert "**base** da tese" in txt  # bucket core → parte da base
    assert "Nota do app: **72/100**" in txt


def test_narrative_mentions_dy_and_roe():
    txt = build_stock_narrative(_row())
    assert "8.0% ao ano" in txt
    assert "ROE de 20.0%" in txt


def test_narrative_honest_when_no_dy():
    txt = build_stock_narrative(_row(dividend_yield=None, score_dividends=60.0))
    assert "sem dado de dividendo" in txt.lower()


def test_narrative_honest_when_no_debt():
    txt = build_stock_narrative(_row(net_debt_ebitda=None, score_financial_health=55.0))
    assert "sem dado de dívida" in txt.lower()


def test_narrative_debt_high_is_not_forte():
    txt = build_stock_narrative(_row(net_debt_ebitda=3.0))
    debt_line = next(line for line in txt.splitlines() if line.lower().startswith("dívida"))
    assert "forte" not in debt_line.lower()
    assert "3.0x" in debt_line
    assert "esticada" in debt_line.lower() or "preocupante" in debt_line.lower()


def test_narrative_flags_yield_trap():
    txt = build_stock_narrative(_row(dividend_yield=0.16))
    assert "bem alto" in txt.lower()
    assert "sustentável" in txt.lower()


def test_narrative_flags_negative_fcf():
    txt = build_stock_narrative(_row(fcf_positive=False))
    assert "caixa livre está negativo" in txt.lower()


def test_narrative_none_row_not_crash():
    assert "Sem dados" in build_stock_narrative(None)


def test_portfolio_summary_counts_and_top():
    df = pd.DataFrame(
        [
            _row(ticker="ABEV3", bucket="core", score_total=80.0),
            _row(ticker="PETR4", bucket="satellite", score_total=60.0),
        ]
    )
    txt = build_portfolio_summary(df, thesis_label="Quality Dividend", thesis_version="1.3.0")
    assert "2 sugestões" in txt
    assert "1 na base" in txt
    assert "1 no complemento" in txt
    assert "ABEV3" in txt


def test_portfolio_summary_empty():
    assert (
        "Nenhuma sugestão"
        in build_portfolio_summary(pd.DataFrame(), thesis_label="X", thesis_version="1")
    )