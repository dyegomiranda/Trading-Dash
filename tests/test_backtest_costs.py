"""Pacote C: custos no backtest (corretagem, slippage, IR)."""

from __future__ import annotations

from src.backtest.engine import BacktestConfig, BacktestCosts, run_backtest
from src.data.providers import DemoDataProvider
from src.portfolio.paper import PaperPortfolio


def test_cost_model_tax_on_dividends():
    pf = PaperPortfolio.create(name="cost-test", cash=10_000)
    pf.buy("PETR4", 100, 40.0)
    before = pf.cash
    pf.credit_dividend("PETR4", 1.0, ex_date="2026-01-10", tax_rate=0.15)
    # 100 * 1.0 = 100 bruto; 15% retido = 85 líquido
    assert abs((pf.cash - before) - 85.0) < 1e-6


def test_buy_fee_and_slippage():
    pf = PaperPortfolio.create(name="cost-test2", cash=10_000)
    tr = pf.buy("VALE3", 100, 10.0, fee_bps=25, slippage_bps=10)
    # execução: 10 * 1.001 = 10.01 → amount 1001.0; fee 25bps = 2.5025 → total 1003.5025
    assert abs(pf.cash - (10_000 - 1001.0 - 2.5025)) < 0.01
    assert abs(tr.price - 10.01) < 1e-6


def test_sell_fee_and_slippage():
    pf = PaperPortfolio.create(name="cost-test3", cash=10_000)
    pf.buy("ITUB4", 100, 30.0, ts="2026-01-01T00:00:00")
    tr = pf.sell("ITUB4", 100, 30.0, fee_bps=25, slippage_bps=10)
    # execução: 30 * 0.999 = 29.97 → amount 2997.0
    assert abs(tr.amount - 2997.0) < 0.01


def test_backtest_costs_reduce_equity():
    prov = DemoDataProvider()
    univ = ["ITUB4", "PETR4", "VALE3", "WEGE3", "BBDC4", "BBAS3", "ABEV3", "EGIE3"]
    cfg0 = BacktestConfig(start="2024-01-01", end="2024-09-30", initial_cash=10_000, top_n=4, universe=univ)
    cfgr = BacktestConfig(
        start="2024-01-01", end="2024-09-30", initial_cash=10_000, top_n=4, universe=univ,
        costs=BacktestCosts(fee_bps=25, slippage_bps=10, tax_rate=0.15),
    )
    r0 = run_backtest(prov, cfg0)
    rf = run_backtest(prov, cfgr)
    assert rf.metrics["costs_enabled"] is True
    assert rf.metrics["final_equity"] < r0.metrics["final_equity"]
    assert rf.metrics["dividends_total"] <= r0.metrics["dividends_total"]
    assert any("CUSTOS" in n for n in rf.notes)