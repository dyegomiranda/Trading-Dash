"""Walk-forward: corte no tempo e métricas IS vs OOS."""

from __future__ import annotations

import pandas as pd

from src.backtest.engine import BacktestConfig, BacktestResult, run_backtest
from src.backtest.walkforward import cutoff_timestamp, evaluate_walk_forward
from src.data.providers import DemoDataProvider


def _fake_result(n: int = 100) -> BacktestResult:
    dates = pd.date_range("2024-01-02", periods=n, freq="B")
    # treino sobe, teste cai — OOS mais fraco
    eq = []
    v = 10_000.0
    for i in range(n):
        v *= 1.002 if i < int(n * 0.7) else 0.997
        eq.append(v)
    curve = pd.DataFrame({"date": dates, "equity": eq})
    return BacktestResult(
        equity_curve=curve,
        trades=pd.DataFrame(),
        dividends=pd.DataFrame(),
        final_holdings=pd.DataFrame(),
        metrics={"initial_cash": 10_000.0, "final_equity": eq[-1]},
        config=BacktestConfig(start="2024-01-02", end=str(dates[-1].date())),
        notes=[],
    )


def test_evaluate_walk_forward_marks_weaker_oos():
    wf = evaluate_walk_forward(_fake_result(80), fraction=0.70)
    assert wf.n_is_days >= 2 and wf.n_oos_days >= 2
    assert wf.oos_weaker is True
    assert wf.is_return > 0
    assert wf.oos_return < 0


def test_cutoff_inside_range():
    eq = pd.Series(
        [100.0, 101.0, 102.0, 103.0, 104.0, 105.0],
        index=pd.date_range("2024-01-02", periods=6, freq="B"),
    )
    cut = cutoff_timestamp(eq, 0.70)
    assert eq.index[0] < cut < eq.index[-1]


def test_walk_forward_on_demo_backtest():
    prov = DemoDataProvider()
    univ = ["ITUB4", "PETR4", "VALE3", "WEGE3", "BBDC4", "BBAS3", "ABEV3", "EGIE3"]
    cfg = BacktestConfig(
        start="2023-01-02",
        end="2024-12-30",
        initial_cash=10_000,
        top_n=4,
        universe=univ,
    )
    res = run_backtest(prov, cfg)
    wf = evaluate_walk_forward(res, fraction=0.70)
    assert wf.n_is_days + wf.n_oos_days >= len(res.equity_curve) - 1
    assert wf.cutoff >= cfg.start
