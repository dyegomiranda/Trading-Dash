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
    assert sc["p10"] is sc["cauteloso"]
    assert sc["p50"] is sc["base"]
    assert sc["p90"] is sc["animado"]
    assert any("P10" in str(x) for x in sc["combined"]["scenario"].unique())


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


def test_reinvest_snowball_beats_withdrawing():
    """Reinvestir dividendos deve acumular MAIS capital que sacar (juros compostos)."""
    pf = PaperPortfolio.create(name="t", cash=10_000)
    fund = pd.DataFrame([{"ticker": "ITUB4", "dividend_yield": 0.06}])
    prices = {"ITUB4": 30.0}
    pf.buy("ITUB4", 100, 30.0)

    reinvest = project_income(
        pf, fund, prices=prices, reinvest=True, years=10,
        monthly_contribution=500, fallback_yield=0.06,
    )
    withdraw = project_income(
        pf, fund, prices=prices, reinvest=False, years=10,
        monthly_contribution=500, fallback_yield=0.06,
    )
    eq_reinvest = float(reinvest["projection"]["portfolio_equity_est"].iloc[-1])
    eq_withdraw = float(withdraw["projection"]["portfolio_equity_est"].iloc[-1])
    assert eq_reinvest > eq_withdraw * 1.05  # bem maior no fim
    # aportes são os mesmos; a diferença vem SÓ do reinvestimento
    assert reinvest["total_contributed_end"] == withdraw["total_contributed_end"]


def test_yield_haircut_is_surfaced():
    pf = PaperPortfolio.create(name="t", cash=10_000)
    r = project_income(
        pf,
        pd.DataFrame(),
        prices={},
        reinvest=False,
        years=5,
        monthly_contribution=0,
        fallback_yield=0.08,
        starting_principal_override=10_000,
    )
    assert r["yield_was_cut"] is True
    assert abs(r["starting_yield"] - 0.08 * 0.75) < 1e-9
    assert abs(r["yield_haircut"] - 0.25) < 1e-9


def test_p10_has_no_three_percent_floor():
    """Cauteloso antigo forçava 3% — isso inflava carteiras de yield baixo."""
    pf = PaperPortfolio.create(name="t", cash=10_000)
    sc = project_income_scenarios(
        pf,
        pd.DataFrame(),
        prices={},
        years=5,
        monthly_contribution=0,
        reinvest=False,
        starting_principal=10_000,
        fallback_yield=0.04,
    )
    p10 = float(sc["p10"]["starting_yield"])
    p50 = float(sc["p50"]["starting_yield"])
    assert p50 == 0.04 * 0.75  # haircut
    assert p10 < 0.03
    assert p10 <= p50
