"""Sanidade da projeção de renda — evita distorções otimistas demais."""

from __future__ import annotations

import pandas as pd

from src.portfolio.income import project_income, project_income_scenarios, _run_projection
from src.portfolio.paper import PaperPortfolio


def test_three_k_plus_two_k_monthly_is_sane():
    """3 mil inicial + 2 mil/mês por 10 anos a ~6% não deve gerar renda mágica."""
    proj = _run_projection(
        starting_principal=3_000,
        starting_yield=0.06,
        years=10,
        reinvest=True,
        assumed_div_growth=0.02,
        monthly_contribution=2_000,
        max_yield=0.10,
    )
    last = proj.iloc[-1]
    # Capital: aportes 240k + inicial + reinvest → ordem de 300–400k
    assert 250_000 < last["portfolio_equity_est"] < 450_000
    # Renda anual no fim: tipicamente ~15–30k (não 80k+)
    assert 10_000 < last["projected_annual_income"] < 40_000
    # Taxa implícita no fim não explode
    implied = last["projected_annual_income"] / last["portfolio_equity_est"]
    assert implied <= 0.12


def test_yield_cap_prevents_explosion():
    proj = _run_projection(
        starting_principal=50_000,
        starting_yield=0.20,  # dado ruim
        years=15,
        reinvest=True,
        assumed_div_growth=0.10,
        monthly_contribution=0,
        max_yield=0.10,
    )
    assert proj["portfolio_yield"].max() <= 0.10 + 1e-9


def test_scenarios_order():
    pf = PaperPortfolio.create(name="t", cash=10_000)
    fund = pd.DataFrame()
    sc = project_income_scenarios(
        pf,
        fund,
        prices={},
        years=10,
        monthly_contribution=500,
        reinvest=True,
        starting_principal=10_000,
        base_yield=0.06,
    )
    c = sc["cauteloso"]["final_monthly_income"]
    b = sc["base"]["final_monthly_income"]
    a = sc["animado"]["final_monthly_income"]
    assert c <= b <= a
    assert not sc["combined"].empty


def test_override_principal_independent_of_portfolio():
    pf = PaperPortfolio.create(name="t", cash=100_000)
    r = project_income(
        pf,
        pd.DataFrame(),
        prices={},
        reinvest=False,
        years=5,
        monthly_contribution=0,
        fallback_yield=0.06,
        starting_principal_override=3_000,
    )
    assert abs(r["starting_principal"] - 3_000) < 1e-6
    # Renda escala com capital menor
    assert r["final_annual_income"] < 5_000
