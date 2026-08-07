"""Projeção de renda passiva da carteira."""

from __future__ import annotations

from typing import Any

import pandas as pd

from src.portfolio.paper import PaperPortfolio


def project_income(
    portfolio: PaperPortfolio,
    fundamentals: pd.DataFrame,
    prices: dict[str, float] | None = None,
    reinvest: bool = False,
    years: int = 10,
    assumed_div_growth: float = 0.04,
) -> dict[str, Any]:
    """Projeta renda anual com e sem reinvestimento (juros compostos simplificados).

    Usa dividend_yield do snapshot fundamentalista sobre o valor de mercado atual.
    """
    prices = prices or {}
    if fundamentals.empty or not portfolio.positions:
        return {
            "annual_income_now": 0.0,
            "monthly_income_now": 0.0,
            "yield_on_equity": 0.0,
            "yield_on_cost": 0.0,
            "by_ticker": pd.DataFrame(),
            "projection": pd.DataFrame(),
            "years": years,
            "reinvest": reinvest,
            "assumed_div_growth": assumed_div_growth,
        }

    fund = fundamentals.set_index("ticker", drop=False)
    rows = []
    annual = 0.0
    cost_base = 0.0
    equity_pos = 0.0
    for t, pos in portfolio.positions.items():
        px = prices.get(t, pos.avg_price)
        mv = pos.shares * px
        cost = pos.shares * pos.avg_price
        dy = 0.0
        if t in fund.index:
            raw = fund.loc[t].get("dividend_yield")
            try:
                dy = float(raw) if raw is not None and not pd.isna(raw) else 0.0
            except (TypeError, ValueError):
                dy = 0.0
        income = mv * dy
        annual += income
        cost_base += cost
        equity_pos += mv
        rows.append(
            {
                "ticker": t,
                "shares": pos.shares,
                "price": px,
                "market_value": mv,
                "dividend_yield": dy,
                "annual_income": income,
                "monthly_income": income / 12,
                "bucket": pos.bucket,
            }
        )

    by_ticker = pd.DataFrame(rows).sort_values("annual_income", ascending=False)
    equity = portfolio.total_value(prices)

    # Projeção ano a ano
    proj_rows = []
    income = annual
    principal = equity_pos
    cash_drag = portfolio.cash  # caixa não rende no modelo simples
    for y in range(1, years + 1):
        if reinvest:
            principal = principal + income
            income = principal * (annual / equity_pos if equity_pos else 0) * (
                (1 + assumed_div_growth) ** (y - 1)
            )
            # approx: yield inicial sobre principal crescente + crescimento de div
        else:
            income = annual * ((1 + assumed_div_growth) ** (y - 1))
        proj_rows.append(
            {
                "year": y,
                "projected_annual_income": income,
                "projected_monthly_income": income / 12,
                "portfolio_equity_est": (principal if reinvest else equity_pos)
                + cash_drag,
            }
        )

    return {
        "annual_income_now": annual,
        "monthly_income_now": annual / 12,
        "yield_on_equity": (annual / equity) if equity else 0.0,
        "yield_on_cost": (annual / cost_base) if cost_base else 0.0,
        "by_ticker": by_ticker,
        "projection": pd.DataFrame(proj_rows),
        "years": years,
        "reinvest": reinvest,
        "assumed_div_growth": assumed_div_growth,
    }
