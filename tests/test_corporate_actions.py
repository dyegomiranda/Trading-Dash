"""Splits/bonificação: custo em R$ se conserva; série ajustada não redimensiona."""

from __future__ import annotations

import pandas as pd

from src.backtest.corporate_actions import (
    infer_ratio_from_prices,
    infer_splits_from_close,
    prices_look_raw,
)
from src.backtest.engine import BacktestConfig, run_backtest
from src.data.providers import DemoDataProvider
from src.portfolio.paper import PaperPortfolio


def test_apply_split_preserves_cost_and_market_value():
    pf = PaperPortfolio.create(name="s", cash=10_000)
    pf.buy("ITUB4", 100, 20.0)
    assert pf.apply_split("ITUB4", 2.0) is True
    pos = pf.positions["ITUB4"]
    assert abs(pos.shares - 200.0) < 1e-9
    assert abs(pos.avg_price - 10.0) < 1e-9
    assert abs(pos.market_value(10.0) - 2_000.0) < 1e-9


def test_apply_split_missing_position():
    pf = PaperPortfolio.create(name="s", cash=10_000)
    assert pf.apply_split("VALE3", 2.0) is False


def test_infer_two_for_one():
    assert infer_ratio_from_prices(20.0, 10.0) == 2.0
    assert infer_ratio_from_prices(20.0, 19.5) is None


def test_prices_look_raw_vs_adjusted():
    assert prices_look_raw(20.0, 10.0, 2.0) is True
    assert prices_look_raw(20.0, 20.2, 2.0) is False


def test_infer_splits_from_close_pivot():
    idx = pd.to_datetime(["2024-03-14", "2024-03-15", "2024-03-18"])
    close = pd.DataFrame({"ITUB4": [20.0, 10.0, 10.2]}, index=idx)
    found = infer_splits_from_close(close)
    assert len(found) == 1
    assert found.iloc[0]["ticker"] == "ITUB4"
    assert float(found.iloc[0]["ratio"]) == 2.0


class _RawSplitStub:
    """Preço cai à metade no split — série crua; o motor deve dobrar as ações."""

    name = "demo"

    def get_fundamentals(self, tickers=None):
        return pd.DataFrame(
            [
                {
                    "ticker": "ITUB4",
                    "name": "Itau",
                    "sector": "Financial Services",
                    "price": 20.0,
                    "roe": 0.22,
                    "roic": 0.18,
                    "dividend_yield": 0.07,
                    "payout": 0.45,
                    "net_debt_ebitda": 0.4,
                    "net_margin": 0.22,
                    "ebitda_margin": 0.35,
                    "fcf_positive": True,
                    "pe": 8.0,
                    "source": "demo",
                }
            ]
        )

    def get_price_history(self, tickers, start, end=None):
        days = pd.bdate_range(start, end or "2024-04-30")
        cut = pd.Timestamp("2024-03-15")
        rows = []
        for d in days:
            px = 20.0 if d < cut else 10.0
            rows.append(
                {
                    "date": d,
                    "ticker": "ITUB4",
                    "open": px,
                    "high": px,
                    "low": px,
                    "close": px,
                    "adj_close": px,
                    "volume": 2_000_000,
                }
            )
        return pd.DataFrame(rows)

    def get_dividend_history(self, tickers, start, end=None):
        return pd.DataFrame(columns=["date", "ticker", "amount"])

    def get_split_history(self, tickers, start, end=None):
        return pd.DataFrame(
            [{"date": pd.Timestamp("2024-03-15"), "ticker": "ITUB4", "ratio": 2.0, "source": "test"}]
        )

    def get_latest_prices(self, tickers):
        return pd.Series({"ITUB4": 10.0})


def test_backtest_applies_raw_split_and_keeps_value():
    cfg = BacktestConfig(
        start="2024-01-02",
        end="2024-04-30",
        initial_cash=10_000,
        top_n=1,
        min_score=0,
        universe=["ITUB4"],
        include_benchmarks=False,
        rebalance="M",
    )
    res = run_backtest(_RawSplitStub(), cfg)
    assert res.metrics["n_splits_applied"] >= 1
    assert any("split" in n.lower() for n in res.notes)


def test_backtest_does_not_apply_split_on_adjusted_demo_series():
    """Demo não tem gap 50%; Yahoo-like já ajustado → n_splits_applied = 0."""
    prov = DemoDataProvider()
    univ = ["ITUB4", "PETR4", "VALE3", "WEGE3", "BBDC4", "BBAS3", "ABEV3", "EGIE3"]
    cfg = BacktestConfig(
        start="2024-01-01",
        end="2024-06-30",
        initial_cash=10_000,
        top_n=4,
        universe=univ,
    )
    res = run_backtest(prov, cfg)
    assert res.metrics["n_splits_applied"] == 0
    assert any("EVENTOS" in n for n in res.notes)
    assert any("close" in n and "adj_close" in n for n in res.notes)
