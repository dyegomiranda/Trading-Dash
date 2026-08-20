"""Testes do carregador de balanços históricos Point-in-Time."""

from __future__ import annotations

import pandas as pd
from src.data.pit_loader import (
    get_pit_coverage_summary,
    get_pit_dates,
    get_pit_origin,
    has_pit_data,
    load_pit_fundamentals,
    load_pit_meta,
)


def test_has_pit_data():
    assert has_pit_data() is True


def test_get_pit_dates():
    dates = get_pit_dates()
    assert len(dates) >= 4
    # Datas devem estar ordenadas cronologicamente
    assert dates == sorted(dates)
    assert all("-" in d for d in dates)


def test_load_pit_fundamentals_structure():
    snaps = load_pit_fundamentals()
    assert isinstance(snaps, dict)
    assert len(snaps) > 0
    
    # Cada entrada deve ser um DataFrame coerente com o schema
    for q_date, df in snaps.items():
        assert isinstance(df, pd.DataFrame)
        assert not df.empty
        assert "ticker" in df.columns
        assert "roe" in df.columns
        assert "dividend_yield" in df.columns
        assert "net_debt_ebitda" in df.columns
        # ROE real pode ser negativo; a semente atual é positiva, mas não é contrato.


def test_get_pit_coverage_summary():
    summary = get_pit_coverage_summary()
    assert summary["n_quarters"] >= 4
    assert summary["tickers_count"] >= 10
    assert "ITUB4" in summary["tickers"]
    assert "VALE3" in summary["tickers"]
    assert "PETR4" in summary["tickers"]


def test_pit_origin_is_labeled():
    origin = get_pit_origin()
    assert origin in {"seed_curated", "cvm_dfp_itr"}
    meta = load_pit_meta()
    if origin.startswith("cvm"):
        assert meta["is_cvm"] is True
    else:
        assert meta["is_cvm"] is False
        assert "semente" in meta["description"].lower() or "curada" in meta["description"].lower()
