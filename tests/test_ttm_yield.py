"""DY TTM no rebalance — sem look-ahead de mercado."""

from __future__ import annotations

import pandas as pd

from src.backtest.engine import _cap_weights_by_adv, _ttm_dividend_yield


def test_ttm_yield_uses_only_past_dividends():
    divs = pd.DataFrame(
        {
            "date": pd.to_datetime(["2023-06-01", "2024-01-15", "2024-07-01"]),
            "ticker": ["ITUB4", "ITUB4", "ITUB4"],
            "amount": [1.0, 1.5, 99.0],  # 99 é futuro
        }
    )
    y = _ttm_dividend_yield(divs, "ITUB4", pd.Timestamp("2024-06-30"), price=50.0)
    # só 2024-01-15 (1.5) dentro da janela; 2023-06-01 tem >365d; 2024-07-01 é futuro
    assert y is not None
    assert abs(y - (1.5 / 50.0)) < 1e-9


def test_ttm_yield_zero_when_no_dividends_in_window():
    divs = pd.DataFrame(
        {"date": pd.to_datetime(["2020-01-01"]), "ticker": ["ITUB4"], "amount": [2.0]}
    )
    y = _ttm_dividend_yield(divs, "ITUB4", pd.Timestamp("2024-06-30"), price=10.0)
    assert y == 0.0


def test_cap_weights_by_adv_reduces_illiquid():
    weights = {"ITUB4": 0.5, "TINY3": 0.5}
    # TINY3 ADV 1_000; 5% = 50; equity 10_000 → cap weight 50/10000 = 0.005
    capped = _cap_weights_by_adv(
        weights,
        equity=10_000,
        day_adv={"ITUB4": 10_000_000, "TINY3": 1_000},
        max_adv_order_pct=0.05,
    )
    assert capped["TINY3"] < capped["ITUB4"]
    assert abs(sum(capped.values()) - 1.0) < 1e-9
