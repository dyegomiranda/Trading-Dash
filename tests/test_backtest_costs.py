"""Pacote C: custos no backtest (corretagem, slippage, IR)."""

from __future__ import annotations

from src.backtest.engine import (
    BacktestConfig,
    BacktestCosts,
    conservative_costs,
    run_backtest,
)
from src.data.providers import DemoDataProvider
from src.portfolio.paper import PF_MONTHLY_SALES_EXEMPTION_BRL, PaperPortfolio


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


def test_conservative_costs_apply_jcp_and_capital_gains():
    prov = DemoDataProvider()
    univ = ["ITUB4", "PETR4", "VALE3", "WEGE3", "BBDC4", "BBAS3", "ABEV3", "EGIE3"]
    cfg0 = BacktestConfig(start="2024-01-01", end="2024-09-30", initial_cash=10_000, top_n=4, universe=univ)
    cfgr = BacktestConfig(
        start="2024-01-01",
        end="2024-09-30",
        initial_cash=10_000,
        top_n=4,
        universe=univ,
        costs=conservative_costs(),
    )
    r0 = run_backtest(prov, cfg0)
    rf = run_backtest(prov, cfgr)
    assert rf.metrics["cost_jcp_share"] == 0.25
    assert rf.metrics["cost_capital_gains_rate"] == 0.15
    assert rf.metrics["cost_dividend_cash_lag_days"] == 15
    assert rf.metrics["cost_dynamic_slippage"] is True
    assert rf.metrics["final_equity"] <= r0.metrics["final_equity"]
    assert rf.metrics["cost_pf_monthly_sales_exemption"] == PF_MONTHLY_SALES_EXEMPTION_BRL


def test_pf_exemption_skips_cg_under_20k():
    pf = PaperPortfolio.create(name="ex-small", cash=10_000)
    pf.buy("PETR4", 100, 40.0, ts="2022-01-03T00:00:00")
    cash_before = pf.cash
    pf.sell(
        "PETR4",
        100,
        50.0,
        ts="2022-01-31T00:00:00",
        capital_gains_rate=0.15,
        pf_monthly_sales_exemption=20_000.0,
    )
    # venda R$ 5.000 < 20 mil → sem IR; lucro 1.000 não é tributado
    assert abs(pf.cash - (cash_before + 5_000.0)) < 1e-6
    assert pf.sales_by_month["2022-01"] == 5_000.0


def test_pf_exemption_taxes_when_sales_exceed_20k():
    pf = PaperPortfolio.create(name="ex-big", cash=50_000)
    pf.buy("ITUB4", 1_000, 30.0, ts="2022-01-03T00:00:00")
    cash_before = pf.cash
    pf.sell(
        "ITUB4",
        800,
        40.0,
        ts="2022-01-31T00:00:00",
        capital_gains_rate=0.15,
        pf_monthly_sales_exemption=20_000.0,
    )
    # venda 32.000 > 20 mil; lucro 8.000 × 15% = 1.200
    assert abs(pf.cash - (cash_before + 32_000.0 - 1_200.0)) < 1e-6


def test_pf_exemption_clawback_same_month():
    pf = PaperPortfolio.create(name="ex-claw", cash=80_000)
    pf.buy("VALE3", 2_000, 20.0, ts="2022-03-01T00:00:00")
    pf.sell(
        "VALE3",
        500,
        30.0,
        ts="2022-03-10T00:00:00",
        capital_gains_rate=0.15,
        pf_monthly_sales_exemption=20_000.0,
    )
    # 1ª venda 15.000, lucro 5.000, isenta
    cash_mid = pf.cash
    pf.sell(
        "VALE3",
        400,
        30.0,
        ts="2022-03-20T00:00:00",
        capital_gains_rate=0.15,
        pf_monthly_sales_exemption=20_000.0,
    )
    # 2ª venda 12.000 → mês 27.000; clawback 5.000 + lucro 4.000 = 9.000 × 15% = 1.350
    assert abs(pf.cash - (cash_mid + 12_000.0 - 1_350.0)) < 1e-6


def test_pf_exemption_off_always_taxes():
    pf = PaperPortfolio.create(name="ex-off", cash=10_000)
    pf.buy("WEGE3", 100, 40.0, ts="2022-01-03T00:00:00")
    cash_before = pf.cash
    pf.sell(
        "WEGE3",
        100,
        50.0,
        ts="2022-01-31T00:00:00",
        capital_gains_rate=0.15,
        pf_monthly_sales_exemption=0.0,
    )
    assert abs(pf.cash - (cash_before + 5_000.0 - 150.0)) < 1e-6


def test_exemption_helps_small_account_vs_always_tax():
    prov = DemoDataProvider()
    univ = ["ITUB4", "PETR4", "VALE3", "WEGE3", "BBDC4", "BBAS3", "ABEV3", "EGIE3"]
    common = dict(start="2024-01-01", end="2024-09-30", initial_cash=10_000, top_n=4, universe=univ)
    taxed = BacktestConfig(
        **common,
        costs=BacktestCosts(
            fee_bps=15,
            slippage_bps=10,
            capital_gains_rate=0.15,
            pf_monthly_sales_exemption=0.0,
        ),
    )
    exempt = BacktestConfig(
        **common,
        costs=BacktestCosts(
            fee_bps=15,
            slippage_bps=10,
            capital_gains_rate=0.15,
            pf_monthly_sales_exemption=20_000.0,
        ),
    )
    r_taxed = run_backtest(prov, taxed)
    r_exempt = run_backtest(prov, exempt)
    assert r_exempt.metrics["final_equity"] >= r_taxed.metrics["final_equity"]


def test_from_dict_ignores_missing_sales_fields():
    pf = PaperPortfolio.from_dict(
        {
            "name": "legacy",
            "cash": 1_000,
            "initial_cash": 1_000,
            "positions": {},
            "trades": [],
            "dividends": [],
        }
    )
    assert pf.sales_by_month == {}
    assert pf.untaxed_gains_by_month == {}