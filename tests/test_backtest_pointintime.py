"""Pacote B: backtest com fundamentals point-in-time (sem look-ahead)."""

from __future__ import annotations

import pandas as pd

from src.backtest.engine import BacktestConfig, _resolve_fundamentals, run_backtest
from src.data.providers import DemoDataProvider

_DF = pd.DataFrame({"ticker": ["ITUB4"], "price": [30.0], "dividend_yield": [0.06]})


def test_resolve_no_snapshots_falls_back():
    cfg = BacktestConfig(start="2024-01-01")
    fallback = _DF
    got, pit = _resolve_fundamentals(cfg, pd.Timestamp("2024-06-30"), fallback)
    assert pit is False
    assert got.equals(fallback)


def test_resolve_picks_latest_snapshot_le_day():
    cfg = BacktestConfig(start="2024-01-01", fundamentals_by_date={
        "2024-03-01": _DF,   # snap mais antigo que dia
        "2024-05-01": _DF,   # snap mais recente <= dia
        "2024-08-01": _DF,   # futuro — NÃO pode ser usado (look-ahead)
    })
    got, pit = _resolve_fundamentals(cfg, pd.Timestamp("2024-06-15"), _DF)
    assert pit is True


def test_resolve_ignores_future_snapshot():
    cfg = BacktestConfig(start="2024-01-01", fundamentals_by_date={
        "2025-01-01": _DF,   # só futuro
    })
    got, pit = _resolve_fundamentals(cfg, pd.Timestamp("2024-06-15"), _DF)
    assert pit is False
    assert got.equals(_DF)


def test_run_backtest_pit_flag():
    prov = DemoDataProvider()
    fund = prov.get_fundamentals()
    cfg = BacktestConfig(
        start="2024-01-01", end="2024-06-30", initial_cash=10_000, top_n=5,
        fundamentals_by_date={"2024-03-31": fund, "2024-06-30": fund},
    )
    res = run_backtest(prov, cfg)
    assert res.metrics["use_point_in_time"] is True
    assert any("point-in-time" in n.lower() for n in res.notes) or any(
        "UPDATE" in n for n in res.notes
    )


def test_run_backtest_snapshot_note():
    prov = DemoDataProvider()
    cfg = BacktestConfig(start="2024-01-01", end="2024-06-30", initial_cash=10_000, top_n=5)
    res = run_backtest(prov, cfg)
    assert any("LIMITE" in n for n in res.notes)