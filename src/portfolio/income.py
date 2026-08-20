"""Projeção de renda passiva da carteira (com aportes mensais)."""

from __future__ import annotations

from typing import Any

import pandas as pd

from src.portfolio.paper import PaperPortfolio

# Teto realista para % de dividendo em projeção de longo prazo (tese quality).
# DY de mercado não sobe para sempre; acima disso vira cenário de fantasia.
DEFAULT_MAX_YIELD = 0.10
# Yield recente costuma reverter — não projetar o TTM cheio.
DEFAULT_YIELD_HAIRCUT = 0.25


def suggest_monthly_contribution(monthly_net_income: float) -> dict[str, Any]:
    """Sugere faixas de aporte mensal a partir da renda líquida do usuário.

    Regras didáticas (não são aconselhamento financeiro):
    - leve ~5%  — começar sem apertar o orçamento
    - recomendado ~10% — meta clássica de poupança/investimento
    - forte ~15% — ritmo acelerado, se a vida permitir
    """
    income = max(0.0, float(monthly_net_income or 0.0))
    leve = round(income * 0.05, 2)
    rec = round(income * 0.10, 2)
    forte = round(income * 0.15, 2)
    return {
        "monthly_net_income": income,
        "leve": leve,
        "recomendado": rec,
        "forte": forte,
        "pct_leve": 0.05,
        "pct_recomendado": 0.10,
        "pct_forte": 0.15,
        "blurb": (
            "Use o que sobra depois de contas essenciais e uma reserva de emergência. "
            "Começar pequeno e constante costuma funcionar melhor do que um valor alto intermitente. "
            "A sua renda do trabalho NÃO entra sozinha na carteira — só o valor de aporte que você definir."
        ),
    }


def _portfolio_yield_and_rows(
    portfolio: PaperPortfolio,
    fundamentals: pd.DataFrame,
    prices: dict[str, float],
) -> tuple[float, float, float, float, pd.DataFrame]:
    """Retorna (annual_income, cost_base, equity_pos, total_equity, by_ticker)."""
    if fundamentals is None or fundamentals.empty or not portfolio.positions:
        equity = float(portfolio.total_value(prices))
        return 0.0, 0.0, 0.0, equity, pd.DataFrame()

    fund = fundamentals.set_index("ticker", drop=False)
    rows: list[dict[str, Any]] = []
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
    equity = float(portfolio.total_value(prices))
    return annual, cost_base, equity_pos, equity, by_ticker


def _run_projection(
    *,
    starting_principal: float,
    starting_yield: float,
    years: int,
    reinvest: bool,
    assumed_div_growth: float,
    monthly_contribution: float,
    max_yield: float = DEFAULT_MAX_YIELD,
) -> pd.DataFrame:
    """Simula ano a ano: aportes mensais + (opcional) reinvestimento de dividendos.

    Modelo didático e **conservador**:
    - Aportes do ano = 12 × aporte mensal (entram na carteira da tese)
    - No ano em que entram, contam com ~metade do yield (aportes espalhados no ano)
    - A taxa de dividendo parte do yield atual e pode crescer um pouco, **com teto**
      (no mundo real o % sobre o preço não explode indefinidamente)
    - Se reinvestir: dividendos do ano voltam para o principal
    - Preço das ações fica “de lado” — foco em renda, não em valorização
    - A renda do trabalho do usuário **não** é somada à carteira
    """
    principal = max(0.0, float(starting_principal))
    base_yld = max(0.0, min(float(starting_yield), float(max_yield)))
    contrib_m = max(0.0, float(monthly_contribution))
    annual_contrib = contrib_m * 12.0
    growth = max(0.0, float(assumed_div_growth))
    cap = max(base_yld, float(max_yield))
    total_contributed = 0.0
    rows: list[dict[str, Any]] = []

    for y in range(1, int(years) + 1):
        # Crescimento suave da taxa, com teto (evita “renda mágica” em 10–20 anos)
        yld = min(base_yld * ((1.0 + growth) ** (y - 1)), cap)
        total_contributed += annual_contrib

        # Capital médio aproximado no ano (principal no início + metade dos aportes)
        avg_capital = principal + annual_contrib * 0.5
        income = avg_capital * yld

        principal = principal + annual_contrib
        if reinvest:
            principal = principal + income

        rows.append(
            {
                "year": y,
                "projected_annual_income": income,
                "projected_monthly_income": income / 12.0,
                "portfolio_equity_est": principal,
                "total_contributed": total_contributed,
                "portfolio_yield": yld,
                "annual_contribution": annual_contrib,
                "avg_capital": avg_capital,
            }
        )

    return pd.DataFrame(rows)


def project_income(
    portfolio: PaperPortfolio,
    fundamentals: pd.DataFrame,
    prices: dict[str, float] | None = None,
    reinvest: bool = False,
    years: int = 10,
    assumed_div_growth: float = 0.02,
    monthly_contribution: float = 0.0,
    fallback_yield: float | None = None,
    max_yield: float = DEFAULT_MAX_YIELD,
    starting_principal_override: float | None = None,
    yield_override: float | None = None,
    yield_haircut: float | None = None,
) -> dict[str, Any]:
    """Projeta renda anual com aportes mensais e opcional reinvestimento.

    Parameters
    ----------
    monthly_contribution:
        Valor que o usuário pretende aportar todo mês na tese.
    starting_principal_override:
        Se informado, usa este capital inicial (permite simular R$ 3 mil sem
        depender do default da conta de treino).
    yield_override:
        Se informado, força a taxa inicial de dividendo do cenário.
    """
    prices = prices or {}
    monthly_contribution = max(0.0, float(monthly_contribution or 0.0))
    years = max(1, int(years))
    assumed_div_growth = max(0.0, float(assumed_div_growth or 0.0))
    max_yield = max(0.01, float(max_yield or DEFAULT_MAX_YIELD))

    annual, cost_base, equity_pos, equity, by_ticker = _portfolio_yield_and_rows(
        portfolio, fundamentals if fundamentals is not None else pd.DataFrame(), prices
    )

    cash = float(getattr(portfolio, "cash", 0.0) or 0.0)
    portfolio_principal = max(equity_pos + cash, equity, 0.0)
    if starting_principal_override is not None:
        starting_principal = max(0.0, float(starting_principal_override))
    else:
        starting_principal = portfolio_principal

    if yield_override is not None:
        raw_yield = max(0.0, float(yield_override))
    elif equity_pos > 0 and annual > 0:
        raw_yield = annual / equity_pos
    elif fallback_yield is not None:
        raw_yield = max(0.0, float(fallback_yield))
    else:
        raw_yield = 0.0

    haircut = DEFAULT_YIELD_HAIRCUT if yield_haircut is None else max(0.0, min(0.8, float(yield_haircut)))
    if yield_override is None:
        starting_yield = min(raw_yield * (1.0 - haircut), max_yield)
    else:
        starting_yield = min(raw_yield, max_yield)
    yield_was_capped = raw_yield > max_yield + 1e-9
    yield_was_cut = yield_override is None and haircut > 0 and raw_yield > 0

    # Renda “hoje” escala se o usuário mudou o capital da simulação vs carteira
    if portfolio_principal > 0 and starting_principal_override is not None:
        scale = starting_principal / portfolio_principal
        annual_now = annual * scale
    else:
        annual_now = annual

    if starting_principal <= 0 and monthly_contribution <= 0:
        empty = pd.DataFrame()
        return {
            "annual_income_now": annual_now,
            "monthly_income_now": annual_now / 12.0,
            "yield_on_equity": (annual / equity) if equity else 0.0,
            "yield_on_cost": (annual / cost_base) if cost_base else 0.0,
            "by_ticker": by_ticker,
            "projection": empty,
            "projection_no_contrib": empty,
            "years": years,
            "reinvest": reinvest,
            "assumed_div_growth": assumed_div_growth,
            "monthly_contribution": monthly_contribution,
            "starting_principal": starting_principal,
            "portfolio_principal": portfolio_principal,
            "starting_yield": starting_yield,
            "raw_starting_yield": raw_yield,
            "yield_was_capped": yield_was_capped,
            "yield_was_cut": yield_was_cut,
            "yield_haircut": haircut,
            "max_yield": max_yield,
            "total_contributed_end": 0.0,
            "income_boost_from_contrib": 0.0,
        }

    projection = _run_projection(
        starting_principal=starting_principal,
        starting_yield=starting_yield,
        years=years,
        reinvest=reinvest,
        assumed_div_growth=assumed_div_growth,
        monthly_contribution=monthly_contribution,
        max_yield=max_yield,
    )
    projection_no_contrib = _run_projection(
        starting_principal=starting_principal,
        starting_yield=starting_yield,
        years=years,
        reinvest=reinvest,
        assumed_div_growth=assumed_div_growth,
        monthly_contribution=0.0,
        max_yield=max_yield,
    )

    if not projection.empty and not projection_no_contrib.empty:
        projection = projection.copy()
        projection["projected_annual_income_no_contrib"] = projection_no_contrib[
            "projected_annual_income"
        ].values
        projection["projected_monthly_income_no_contrib"] = projection_no_contrib[
            "projected_monthly_income"
        ].values
        projection["portfolio_equity_no_contrib"] = projection_no_contrib[
            "portfolio_equity_est"
        ].values

    total_contributed_end = (
        float(projection["total_contributed"].iloc[-1]) if not projection.empty else 0.0
    )
    income_end = (
        float(projection["projected_annual_income"].iloc[-1]) if not projection.empty else 0.0
    )
    income_end_no = (
        float(projection_no_contrib["projected_annual_income"].iloc[-1])
        if not projection_no_contrib.empty
        else 0.0
    )
    final_equity = (
        float(projection["portfolio_equity_est"].iloc[-1])
        if not projection.empty
        else starting_principal
    )
    final_yield = (
        float(projection["portfolio_yield"].iloc[-1]) if not projection.empty else starting_yield
    )
    implied_end = (income_end / final_equity) if final_equity > 0 else 0.0

    return {
        "annual_income_now": annual_now,
        "monthly_income_now": annual_now / 12.0,
        "yield_on_equity": (annual / equity) if equity else starting_yield,
        "yield_on_cost": (annual / cost_base) if cost_base else 0.0,
        "by_ticker": by_ticker,
        "projection": projection,
        "projection_no_contrib": projection_no_contrib,
        "years": years,
        "reinvest": reinvest,
        "assumed_div_growth": assumed_div_growth,
        "monthly_contribution": monthly_contribution,
        "starting_principal": starting_principal,
        "portfolio_principal": portfolio_principal,
        "starting_yield": starting_yield,
        "raw_starting_yield": raw_yield,
        "yield_was_capped": yield_was_capped,
        "yield_was_cut": yield_was_cut,
        "yield_haircut": haircut,
        "max_yield": max_yield,
        "final_yield": final_yield,
        "implied_yield_end": implied_end,
        "total_contributed_end": total_contributed_end,
        "income_boost_from_contrib": max(0.0, income_end - income_end_no),
        "final_annual_income": income_end,
        "final_monthly_income": income_end / 12.0,
        "final_equity_est": final_equity,
    }


def project_income_scenarios(
    portfolio: PaperPortfolio,
    fundamentals: pd.DataFrame,
    prices: dict[str, float] | None = None,
    *,
    years: int = 10,
    monthly_contribution: float = 0.0,
    reinvest: bool = True,
    starting_principal: float | None = None,
    base_yield: float | None = None,
    fallback_yield: float | None = None,
    max_yield: float = DEFAULT_MAX_YIELD,
) -> dict[str, Any]:
    """Três faixas: P10 (cauteloso), P50 (base) e P90 (animado).

    Não são percentis estatísticos de Monte Carlo — são cenários didáticos
    com haircut de yield e teto. Nomes P10/P50/P90 deixam a incerteza explícita.
    """
    base = project_income(
        portfolio,
        fundamentals,
        prices=prices,
        reinvest=reinvest,
        years=years,
        assumed_div_growth=0.02,
        monthly_contribution=monthly_contribution,
        fallback_yield=fallback_yield,
        max_yield=max_yield,
        starting_principal_override=starting_principal,
        yield_override=base_yield,
    )
    y0 = float(base.get("starting_yield") or 0.0)
    if y0 <= 0 and fallback_yield is not None:
        y0 = float(fallback_yield)

    cauteloso = project_income(
        portfolio,
        fundamentals,
        prices=prices,
        reinvest=reinvest,
        years=years,
        assumed_div_growth=0.0,
        monthly_contribution=monthly_contribution,
        fallback_yield=fallback_yield,
        max_yield=max_yield,
        starting_principal_override=starting_principal,
        yield_override=max(0.0, y0 * 0.70),
    )
    animado = project_income(
        portfolio,
        fundamentals,
        prices=prices,
        reinvest=reinvest,
        years=years,
        assumed_div_growth=0.03,
        monthly_contribution=monthly_contribution,
        fallback_yield=fallback_yield,
        max_yield=max_yield,
        starting_principal_override=starting_principal,
        yield_override=min(max_yield, y0 * 1.10),
    )

    frames = []
    for name, res in (
        ("P10 · cauteloso", cauteloso),
        ("P50 · base", base),
        ("P90 · animado", animado),
    ):
        proj = res.get("projection")
        if proj is None or getattr(proj, "empty", True):
            continue
        part = proj[["year", "projected_monthly_income", "portfolio_equity_est"]].copy()
        part["scenario"] = name
        frames.append(part)
    combined = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

    return {
        "base": base,
        "cauteloso": cauteloso,
        "animado": animado,
        "p10": cauteloso,
        "p50": base,
        "p90": animado,
        "combined": combined,
        "labels": {
            "cauteloso": "P10 · cauteloso — taxa menor, sem crescimento",
            "base": "P50 · base — taxa da carteira com haircut e crescimento leve",
            "animado": "P90 · animado — um pouco mais otimista (ainda com teto)",
        },
    }
