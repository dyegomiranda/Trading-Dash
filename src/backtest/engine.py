"""Simulação histórica: segue indicações da tese no passado e mede o resultado."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

import numpy as np
import pandas as pd

from src.data.benchmarks import build_benchmark_curves
from src.data.providers import DataProvider
from src.data.universe import normalize_ticker
from src.portfolio.paper import PaperPortfolio
from src.thesis.scoring import recommend_weights, score_universe
from src.utils import utcnow_date

RebalanceFreq = Literal["M", "Q"]


@dataclass
class BacktestCosts:
    """Modelo de custos da simulação (simples, honesto).

    - ``fee_bps``: corretagem/emolumentos em pontos-base (1% = 100 bps).
    - ``slippage_bps``: impacto de execução (compra sobe, venda desce).
    - ``tax_rate``: retenção de IR sobre dividendos (0 = isento).
    Todos são opcionais e default a 0 — comportamento par com o MV preexistente.
    """

    fee_bps: float = 0.0
    slippage_bps: float = 0.0
    tax_rate: float = 0.0

    @property
    def enabled(self) -> bool:
        return self.fee_bps > 0 or self.slippage_bps > 0 or self.tax_rate > 0


@dataclass
class BacktestConfig:
    start: str
    end: str | None = None
    initial_cash: float = 100_000.0
    top_n: int = 12
    rebalance: RebalanceFreq = "M"
    min_score: float = 55.0
    core_weight: float = 0.70
    satellite_weight: float = 0.30
    max_position_pct: float = 0.10
    universe: list[str] | None = None
    # Fundamentos ponto-a-ponto: mapeia data (YYYY-MM-DD) → DataFrame de
    # fundamentos VÁLIDOS naquela data. Quando fornecido, o score em cada
    # rebalance usa O snapshot hábil à época (sem look-ahead). Quando vazio,
    # usa o snapshot atual (limitação documentada no app) e acende a nota.
    fundamentals_by_date: dict[str, pd.DataFrame] = field(
        default_factory=dict
    )
    use_point_in_time_fundamentals: bool = False
    include_benchmarks: bool = True
    include_idiv: bool = False
    costs: BacktestCosts = field(default_factory=BacktestCosts)
    # Inclinação do dia do rebalance (histórico). Default None = sem tilt de hoje.
    macro_tilt: dict[str, float] | None = None


@dataclass
class BacktestResult:
    equity_curve: pd.DataFrame
    trades: pd.DataFrame
    dividends: pd.DataFrame
    final_holdings: pd.DataFrame
    metrics: dict[str, Any]
    config: BacktestConfig
    notes: list[str] = field(default_factory=list)
    benchmarks: pd.DataFrame = field(default_factory=pd.DataFrame)


def _month_ends(dates: pd.DatetimeIndex, freq: RebalanceFreq) -> list[pd.Timestamp]:
    s = pd.Series(1, index=dates.sort_values())
    rule = "ME" if freq == "M" else "QE"
    ends = s.resample(rule).last().dropna().index
    # garante que o fim caia em dia com pregão
    out = []
    date_set = set(dates.normalize())
    sorted_dates = list(dates.sort_values())
    for e in ends:
        e = pd.Timestamp(e).normalize()
        if e in date_set:
            out.append(e)
            continue
        # último pregão <= e
        prev = [d for d in sorted_dates if d.normalize() <= e]
        if prev:
            out.append(pd.Timestamp(prev[-1]).normalize())
    # unique preserve order
    seen = set()
    uniq = []
    for d in out:
        if d not in seen:
            seen.add(d)
            uniq.append(d)
    return uniq


def _max_drawdown(equity: pd.Series) -> float:
    if equity.empty:
        return 0.0
    peak = equity.cummax()
    dd = equity / peak - 1.0
    return float(dd.min()) if len(dd) else 0.0


def _cagr(equity: pd.Series) -> float:
    if len(equity) < 2:
        return 0.0
    start, end = float(equity.iloc[0]), float(equity.iloc[-1])
    if start <= 0 or end <= 0:
        return 0.0
    days = (equity.index[-1] - equity.index[0]).days
    if days <= 0:
        return 0.0
    years = days / 365.25
    return float((end / start) ** (1 / years) - 1)


def _resolve_fundamentals(
    config: BacktestConfig,
    day: pd.Timestamp,
    fallback: pd.DataFrame,
) -> tuple[pd.DataFrame, bool]:
    """Escolhe o snapshot de fundamentos válido no dia (point-in-time).

    Retorna (fundamentals, ponto_a_ponto):
    - Se ``fundamentals_by_date`` tiver snapshot para o mês/trimestre do dia,
      usa ESSE (ponto a ponto real, sem look-ahead).
    - Caso contrário devolve o snapshot atual (fallback) com flag False,
      para o relatório avisar que usou dados "de hoje".
    """
    if not config.fundamentals_by_date:
        return fallback, False
    # chave mais antiga <= dia (sem olhar para o futuro)
    day_s = pd.Timestamp(day).normalize()
    candidates = []
    for k, df in config.fundamentals_by_date.items():
        try:
            k_ts = pd.Timestamp(k)
        except Exception:
            continue
        if k_ts <= day_s:
            candidates.append((k_ts, k))
    if not candidates:
        return fallback, False
    candidates.sort(key=lambda x: x[0])
    _, key = candidates[-1]
    return config.fundamentals_by_date[key], True


def run_backtest(provider: DataProvider, config: BacktestConfig) -> BacktestResult:
    notes = [
        "Backtest usa preços e dividendos históricos do provedor selecionado.",
        "Fundamentals: o score em cada rebalance usa o snapshot de dados mais recente "
        "disponível até aquela data (point-in-time) quando fornecido via "
        "fundamentals_by_date; sem ele, recai no snapshot atual (limitação do MVP).",
    ]

    fundamentals = provider.get_fundamentals(config.universe)
    if fundamentals.empty:
        raise ValueError("Sem dados fundamentalistas para o universo.")

    result = score_universe(fundamentals, min_score=config.min_score)
    # Para o backtest, trabalhamos com o universo scored (filtrado frouxo)
    # e reaplicamos filtros a cada rebalance.
    scored_base = result.scored.copy()
    tickers = scored_base["ticker"].tolist()
    if config.universe:
        tickers = [normalize_ticker(t) for t in config.universe]
        scored_base = scored_base[scored_base["ticker"].isin(tickers)]

    start = config.start
    end = config.end or utcnow_date()
    prices = provider.get_price_history(tickers, start=start, end=end)
    divs = provider.get_dividend_history(tickers, start=start, end=end)

    if prices.empty:
        raise ValueError("Sem histórico de preços no período.")

    prices = prices.copy()
    prices["date"] = pd.to_datetime(prices["date"]).dt.tz_localize(None).dt.normalize()
    prices = prices.sort_values(["date", "ticker"])

    # pivot close
    close = prices.pivot_table(index="date", columns="ticker", values="close", aggfunc="last")
    close = close.sort_index().ffill(limit=10)
    all_days = close.index

    if divs is not None and not divs.empty:
        divs = divs.copy()
        divs["date"] = pd.to_datetime(divs["date"]).dt.tz_localize(None).dt.normalize()
    else:
        divs = pd.DataFrame(columns=["date", "ticker", "amount"])

    rebalance_days = _month_ends(all_days, config.rebalance)
    # inclui primeiro dia com dados se não houver rebalance cedo
    if not rebalance_days or rebalance_days[0] > all_days[0]:
        rebalance_days = [all_days[0]] + rebalance_days
    # remove rebalances após o fim
    rebalance_days = [d for d in rebalance_days if d <= all_days[-1]]
    rebalance_set = set(rebalance_days)

    portfolio = PaperPortfolio.create(name="backtest", cash=config.initial_cash)
    equity_rows = []
    trade_rows = []
    div_rows = []
    n_pit = 0  # rebalances com fundamentos point-in-time
    n_snap = 0  # rebalances caindo para snapshot atual

    for day in all_days:
        day = pd.Timestamp(day).normalize()
        # preços do dia
        day_prices = close.loc[day].dropna().to_dict()

        # dividendos do dia
        day_divs = divs[divs["date"] == day] if not divs.empty else divs
        for _, r in day_divs.iterrows():
            ev = portfolio.credit_dividend(
                r["ticker"],
                float(r["amount"]),
                ts=day.isoformat(),
                note="div-historico",
                tax_rate=config.costs.tax_rate,
            )
            if ev:
                div_rows.append(
                    {
                        "date": day,
                        "ticker": ev.ticker,
                        "amount": ev.amount,
                        "shares": ev.shares,
                    }
                )

        if day in rebalance_set:
            # fundamentos válidos no dia (point-in-time) ou snapshot atual
            fund_day, is_pit = _resolve_fundamentals(config, day, fundamentals)
            if is_pit:
                n_pit += 1
            else:
                n_snap += 1
            scored = score_universe(
                fund_day, min_score=config.min_score, strict_filters=True
            )
            tradable = scored.filtered[
                scored.filtered["ticker"].isin(day_prices.keys())
            ].copy()
            if tradable.empty:
                notes.append(
                    f"{day.date()}: ninguém passou no filtro da tese — "
                    "mantive a carteira anterior (sem relaxar o filtro)."
                )
                continue
            picks = recommend_weights(
                tradable,
                top_n=config.top_n,
                core_weight=config.core_weight,
                satellite_weight=config.satellite_weight,
                max_position_pct=config.max_position_pct,
                macro_tilt=config.macro_tilt,
            )
            weights = dict(zip(picks["ticker"], picks["target_weight"]))
            buckets = dict(zip(picks["ticker"], picks.get("bucket", "core")))
            trades = portfolio.rebalance_to_weights(
                weights,
                day_prices,
                buckets=buckets,
                note=f"rebalance-{day.date()}",
                ts=day.isoformat(),
                fee_bps=config.costs.fee_bps,
                slippage_bps=config.costs.slippage_bps,
            )
            for tr in trades:
                trade_rows.append(
                    {
                        "date": day,
                        "side": tr.side,
                        "ticker": tr.ticker,
                        "shares": tr.shares,
                        "price": tr.price,
                        "amount": tr.amount,
                        "note": tr.note,
                    }
                )

        equity = portfolio.total_value(day_prices)
        equity_rows.append(
            {
                "date": day,
                "equity": equity,
                "cash": portfolio.cash,
                "n_positions": len(portfolio.positions),
            }
        )

    equity_curve = pd.DataFrame(equity_rows).set_index("date").sort_index()
    eq = equity_curve["equity"]
    rets = eq.pct_change().dropna()
    final_eq = float(eq.iloc[-1]) if len(eq) else config.initial_cash
    total_ret = float(final_eq / config.initial_cash - 1) if len(eq) else 0.0
    metrics: dict[str, Any] = {
        "start": str(all_days[0].date()),
        "end": str(all_days[-1].date()),
        "initial_cash": config.initial_cash,
        "final_equity": final_eq,
        "total_return": total_ret,
        "cagr": _cagr(eq),
        "max_drawdown": _max_drawdown(eq),
        "volatility_ann": float(rets.std() * np.sqrt(252)) if len(rets) else 0.0,
        "dividends_total": float(sum(r["amount"] for r in div_rows)),
        "n_trades": len(trade_rows),
        "n_rebalances": len(rebalance_days),
        "n_rebalances_pit": n_pit,
        "n_rebalances_snapshot": n_snap,
        "use_point_in_time": bool(config.fundamentals_by_date) and n_pit > 0,
        "costs_enabled": config.costs.enabled,
        "cost_fee_bps": config.costs.fee_bps,
        "cost_slippage_bps": config.costs.slippage_bps,
        "cost_tax_rate": config.costs.tax_rate,
        "top_n": config.top_n,
        "rebalance": config.rebalance,
        "provider": provider.name,
    }

    benchmarks = pd.DataFrame()
    if config.include_benchmarks and len(all_days):
        try:
            bm_df, bm_meta = build_benchmark_curves(
                equity_dates=all_days,
                initial_cash=config.initial_cash,
                provider=provider,
                start=start,
                end=end,
                include_idiv=config.include_idiv,
            )
            bm_df = bm_df.set_index("date")
            bm_df["portfolio"] = eq.reindex(bm_df.index).ffill()
            benchmarks = bm_df.reset_index()
            metrics["benchmark_meta"] = bm_meta

            def _series_return(col: str) -> float | None:
                if col not in bm_df.columns or bm_df[col].isna().all():
                    return None
                s = bm_df[col].dropna()
                if len(s) < 2 or float(s.iloc[0]) <= 0:
                    return None
                return float(s.iloc[-1] / s.iloc[0] - 1)

            def _series_cagr(col: str) -> float | None:
                if col not in bm_df.columns or bm_df[col].isna().all():
                    return None
                s = bm_df[col].dropna()
                if len(s) < 2:
                    return None
                return _cagr(s)

            ibov_ret = _series_return("ibovespa")
            cdi_ret = _series_return("cdi")
            idiv_ret = _series_return("idiv")
            metrics["ibov_return"] = ibov_ret
            metrics["cdi_return"] = cdi_ret
            metrics["ibov_cagr"] = _series_cagr("ibovespa")
            metrics["cdi_cagr"] = _series_cagr("cdi")
            if ibov_ret is not None:
                metrics["excess_vs_ibov"] = total_ret - ibov_ret
            if cdi_ret is not None:
                metrics["excess_vs_cdi"] = total_ret - cdi_ret
            if idiv_ret is not None:
                metrics["idiv_return"] = idiv_ret
                metrics["idiv_cagr"] = _series_cagr("idiv")
                metrics["excess_vs_idiv"] = total_ret - idiv_ret

            notes.append(
                f"Benchmarks: Ibovespa ({bm_meta.get('ibov_source')}), "
                f"CDI ({bm_meta.get('cdi_source')}), "
                f"IDIV ({bm_meta.get('idiv_source') or 'desativado'})."
            )
        except Exception as e:
            notes.append(f"Benchmarks indisponíveis neste run: {e}")

    if config.fundamentals_by_date and n_pit > 0:
        notes.append(
            f"UPDATE: {n_pit} rebalances usaram fundamentos point-in-time "
            f"(histórico fornecido); {n_snap} caíram para o snapshot atual "
            f"por falta de snapshot até aquela data."
        )
    elif not config.fundamentals_by_date:
        notes.append(
            "LIMITE: score usou o snapshot ATUAL em todos os rebalances "
            "(sem histórico point-in-time). Resultados validam o fluxo, não "
            "o desempenho contábil histórico."
        )

    if config.costs.enabled:
        notes.append(
            f"CUSTOS: fee {config.costs.fee_bps:.0f} bps, slippage "
            f"{config.costs.slippage_bps:.0f} bps, IR retido {config.costs.tax_rate:.0%} "
            "sobre dividendos aplicados nas ordens do rebalance."
        )

    last_prices = close.iloc[-1].dropna().to_dict()
    holdings = portfolio.holdings_frame(last_prices)

    return BacktestResult(
        equity_curve=equity_curve.reset_index(),
        trades=pd.DataFrame(trade_rows),
        dividends=pd.DataFrame(div_rows),
        final_holdings=holdings,
        metrics=metrics,
        config=config,
        notes=notes,
        benchmarks=benchmarks,
    )
