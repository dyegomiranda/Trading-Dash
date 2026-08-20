"""Testes do filtro de liquidez ADV (Average Daily Volume) no backtest."""

from __future__ import annotations

from src.backtest.engine import BacktestConfig, run_backtest
from src.data.providers import DemoDataProvider


def test_backtest_with_pit_auto_injection():
    prov = DemoDataProvider()
    univ = ["ITUB4", "PETR4", "VALE3", "WEGE3", "BBDC4", "BBAS3", "EGIE3", "TAEE11"]
    cfg = BacktestConfig(
        start="2022-01-01",
        end="2024-06-30",
        initial_cash=10_000.0,
        top_n=4,
        universe=univ,
        use_point_in_time_fundamentals=True,
    )
    res = run_backtest(prov, cfg)
    assert res.metrics["use_point_in_time"] is True
    assert res.metrics["n_rebalances_pit"] > 0
    assert any("PIT" in n or "point-in-time" in n.lower() for n in res.notes)
    assert res.metrics.get("ttm_yield_overlay") is True


def test_backtest_adv_filter_metric():
    prov = DemoDataProvider()
    univ = ["ITUB4", "PETR4", "VALE3", "WEGE3"]
    cfg = BacktestConfig(
        start="2024-01-01",
        end="2024-06-30",
        initial_cash=10_000.0,
        top_n=2,
        universe=univ,
        min_daily_volume_brl=100_000.0,
    )
    res = run_backtest(prov, cfg)
    assert res.metrics["min_daily_volume_brl"] == 100_000.0
    assert "adv_excluded_count" in res.metrics
    assert any("ADV" in n for n in res.notes)
