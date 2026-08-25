"""O modo treino não pode ter prejuízo sistemático no ensaio."""

from __future__ import annotations

from src.backtest.engine import BacktestConfig, BacktestCosts, run_backtest
from src.data.providers import DemoDataProvider
from src.data.universe import get_universe


def test_demo_zero_cost_long_run_is_not_systematically_negative():
    univ = get_universe()[:20]
    cfg = BacktestConfig(
        start="2022-01-03",
        end="2024-12-30",
        initial_cash=100_000.0,
        top_n=8,
        rebalance="Q",
        min_score=40,
        universe=univ,
        include_benchmarks=False,
        use_point_in_time_fundamentals=False,
        min_daily_volume_brl=0,
        execution_lag_days=0,
        costs=BacktestCosts(),
    )
    res = run_backtest(DemoDataProvider(), cfg)
    assert res.metrics["n_trades"] > 0
    # Drift 6% a.a. menos quedas ex-div compensadas em caixa → deve ficar no azul.
    assert res.metrics["total_return"] > 0.0


def test_cvm_like_row_not_rejected_only_for_missing_net_debt_ebitda():
    import pandas as pd

    from src.thesis.scoring import score_universe

    row = {
        "ticker": "ITUB4",
        "name": "Itau",
        "sector": "Financial Services",
        "price": 30.0,
        "roe": 0.20,
        "dividend_yield": 0.06,
        "payout": 0.4,
        "fcf_positive": True,
        "debt_equity": 1.2,
        "net_debt_ebitda": None,
    }
    scored = score_universe(pd.DataFrame([row]), min_score=0, strict_filters=True)
    assert not scored.filtered.empty
