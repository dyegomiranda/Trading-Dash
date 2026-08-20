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

RebalanceFreq = Literal["M", "Q", "A"]


STRESS_SCENARIOS: dict[str, dict[str, str]] = {
    "corona_crash": {
        "title": "💥 Corona Crash (2020)",
        "desc": "Choque agudo de volatilidade global e teste de resiliência de dividendos.",
        "start": "2020-01-02",
        "end": "2020-07-31",
    },
    "selic_spike": {
        "title": "📈 Choque de Juros (2021–2022)",
        "desc": "Subida rápida da Selic de 2% para 13,75% a.a. e estresse de alavancagem.",
        "start": "2021-01-04",
        "end": "2022-12-29",
    },
    "recovery_rally": {
        "title": "🚀 Rally e Ciclo de Corte (2023–2024)",
        "desc": "Início do ciclo de afrouxamento monetário e valorização de qualidade.",
        "start": "2023-01-02",
        "end": "2024-12-30",
    },
    "full_cycle": {
        "title": "🔄 Ciclo Completo (2020–2026)",
        "desc": "Simulação estendida multi-regime de longo prazo.",
        "start": "2020-01-02",
        "end": "2026-06-30",
    },
}


@dataclass
class BacktestCosts:
    """Modelo de custos da simulação (simples, honesto e auditável)."""

    fee_bps: float = 0.0
    slippage_bps: float = 0.0
    tax_rate: float = 0.0
    jcp_share: float = 0.0
    capital_gains_rate: float = 0.0
    # Confiabilidade avançada:
    dynamic_slippage: bool = False
    slippage_gamma: float = 0.10
    dividend_cash_lag_days: int = 0  # 0 = crédito imediato; >0 = delay real de liquidação

    @property
    def enabled(self) -> bool:
        return (
            self.fee_bps > 0
            or self.slippage_bps > 0
            or self.tax_rate > 0
            or self.jcp_share > 0
            or self.capital_gains_rate > 0
            or self.dynamic_slippage
            or self.dividend_cash_lag_days > 0
        )


def conservative_costs() -> BacktestCosts:
    """Defaults institucionais: giro não é de graça; IR no ganho; JCP explícito; cash lag."""
    return BacktestCosts(
        fee_bps=15.0,
        slippage_bps=10.0,
        tax_rate=0.0,
        jcp_share=0.25,
        capital_gains_rate=0.15,
        dynamic_slippage=True,
        slippage_gamma=0.10,
        dividend_cash_lag_days=15,
    )


@dataclass
class BacktestConfig:
    start: str
    end: str | None = None
    initial_cash: float = 100_000.0
    top_n: int = 12
    rebalance: RebalanceFreq = "Q"
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
    # Fase B: Filtro de liquidez mínima (ADV) e teto de capacidade por ordem
    min_daily_volume_brl: float = 0.0
    max_adv_order_pct: float = 0.0


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
    rule = {"M": "ME", "Q": "QE", "A": "YE"}.get(freq, "QE")
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


def _ttm_dividend_yield(
    divs: pd.DataFrame,
    ticker: str,
    day: pd.Timestamp,
    price: float,
) -> float | None:
    """Dividend yield TTM até ``day`` (sem olhar o futuro). None se não dá para calcular."""
    try:
        px = float(price)
    except (TypeError, ValueError):
        return None
    if px <= 0 or px != px or divs is None or getattr(divs, "empty", True):
        return None
    window_start = pd.Timestamp(day).normalize() - pd.Timedelta(days=365)
    part = divs[
        (divs["ticker"] == ticker)
        & (divs["date"] > window_start)
        & (divs["date"] <= pd.Timestamp(day).normalize())
    ]
    if part.empty:
        return 0.0
    total = float(pd.to_numeric(part["amount"], errors="coerce").fillna(0.0).sum())
    return total / px


def _overlay_market_on_fundamentals(
    fund: pd.DataFrame,
    day_prices: dict[str, float],
    divs: pd.DataFrame,
    day: pd.Timestamp,
) -> pd.DataFrame:
    """Substitui preço pelo fechamento do dia e DY pelo TTM histórico (anti look-ahead)."""
    if fund is None or fund.empty:
        return fund
    out = fund.copy()
    tickers = out["ticker"].astype(str)
    prices = [float(day_prices[t]) if t in day_prices and day_prices[t] else float("nan") for t in tickers]
    out["price"] = prices
    if divs is None or getattr(divs, "empty", True):
        return out
    yields: list[float] = []
    for t, px in zip(tickers, prices):
        y = _ttm_dividend_yield(divs, t, day, px)
        yields.append(float(y) if y is not None else float("nan"))
    out["dividend_yield"] = yields
    return out


def _cap_weights_by_adv(
    weights: dict[str, float],
    equity: float,
    day_adv: dict[str, float],
    max_adv_order_pct: float,
) -> dict[str, float]:
    """Corta peso-alvo se a posição inteira passaria de X% do ADV."""
    if max_adv_order_pct <= 0 or equity <= 0:
        return weights
    capped: dict[str, float] = {}
    for t, w in weights.items():
        target_val = abs(float(w) * equity)
        adv = float(day_adv.get(t) or 0.0)
        cap_val = adv * max_adv_order_pct
        if cap_val > 0 and target_val > cap_val:
            capped[t] = cap_val / equity
        else:
            capped[t] = float(w)
    total = sum(capped.values())
    if total <= 0:
        return weights
    return {t: w / total for t, w in capped.items()}


def run_backtest(provider: DataProvider, config: BacktestConfig) -> BacktestResult:
    notes = [
        "Backtest usa preços e dividendos históricos do provedor selecionado.",
    ]

    pit_origin = ""
    # Auto-carregar fundamentos point-in-time quando solicitado e disponível
    if config.use_point_in_time_fundamentals and not config.fundamentals_by_date:
        try:
            from src.data.pit_loader import get_pit_origin, load_pit_fundamentals

            config.fundamentals_by_date = load_pit_fundamentals()
            pit_origin = get_pit_origin()
        except Exception:
            pit_origin = ""
    elif config.fundamentals_by_date:
        pit_origin = "injected"

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
    # TTM de 12 meses precisa de proventos anteriores ao início do ensaio
    div_start = (pd.Timestamp(start) - pd.Timedelta(days=400)).strftime("%Y-%m-%d")
    divs = provider.get_dividend_history(tickers, start=div_start, end=end)

    if prices.empty:
        raise ValueError("Sem histórico de preços no período.")

    prices = prices.copy()
    prices["date"] = pd.to_datetime(prices["date"]).dt.tz_localize(None).dt.normalize()
    prices = prices.sort_values(["date", "ticker"])

    # pivot close
    close = prices.pivot_table(index="date", columns="ticker", values="close", aggfunc="last")
    close = close.sort_index().ffill(limit=10)
    all_days = close.index

    # Fase B: Volume financeiro diário e ADV (Rolling 20 dias)
    adv_20 = None
    if "volume" in prices.columns:
        vol_df = prices.copy()
        vol_df["turnover"] = vol_df["close"] * pd.to_numeric(vol_df["volume"], errors="coerce").fillna(0.0)
        turnover_pivot = vol_df.pivot_table(index="date", columns="ticker", values="turnover", aggfunc="last")
        adv_20 = turnover_pivot.sort_index().ffill(limit=10).rolling(window=20, min_periods=1).mean()

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
    pending_dividends: list[dict[str, Any]] = []
    n_pit = 0
    n_snap = 0
    adv_excluded_count = 0
    last_px: dict[str, float] = {}
    from src.data.asset_type import dividend_tax_rate

    for day in all_days:
        day = pd.Timestamp(day).normalize()
        day_prices = close.loc[day].dropna().to_dict()
        last_px.update({t: float(p) for t, p in day_prices.items() if p and p > 0})

        # Fase B: Liquidar proventos pendentes cuja data de liquidação chegou (Cash Lag)
        ready_divs = [d for d in pending_dividends if d["settle_day"] <= day]
        pending_dividends = [d for d in pending_dividends if d["settle_day"] > day]
        for d in ready_divs:
            portfolio.cash += d["net_amount"]
            div_rows.append(
                {
                    "date": day,
                    "ticker": d["ticker"],
                    "amount": d["net_amount"],
                    "shares": d["shares"],
                }
            )

        for t in list(portfolio.positions):
            if t in day_prices:
                continue
            px = last_px.get(t)
            if not px:
                continue
            pos = portfolio.positions[t]
            try:
                tr = portfolio.sell(
                    t,
                    pos.shares,
                    px,
                    note="delistagem",
                    ts=day.isoformat(),
                    fee_bps=config.costs.fee_bps,
                    slippage_bps=config.costs.slippage_bps,
                    capital_gains_rate=config.costs.capital_gains_rate,
                )
            except ValueError:
                continue
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
            notes.append(f"{day.date()}: saída por falta de preço ({t}) — delistagem/illiquidez.")

        day_divs = divs[divs["date"] == day] if not divs.empty else divs
        for _, r in day_divs.iterrows():
            ticker = str(r["ticker"])
            pos = portfolio.positions.get(ticker)
            if pos and pos.shares > 1e-6:
                jcp_tax = dividend_tax_rate(ticker, jcp_share=config.costs.jcp_share)
                tax_rate = max(float(config.costs.tax_rate or 0.0), jcp_tax)
                lag_days = int(config.costs.dividend_cash_lag_days or 0)
                gross = float(pos.shares) * float(r["amount"])
                net = gross * (1.0 - tax_rate)

                if lag_days > 0:
                    settle_day = day + pd.Timedelta(days=int(lag_days * 7 / 5))
                    pending_dividends.append(
                        {
                            "settle_day": settle_day,
                            "ticker": ticker,
                            "net_amount": net,
                            "shares": pos.shares,
                        }
                    )
                else:
                    ev = portfolio.credit_dividend(
                        ticker,
                        float(r["amount"]),
                        ts=day.isoformat(),
                        note="div-historico",
                        tax_rate=tax_rate,
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
            fund_day = _overlay_market_on_fundamentals(fund_day, day_prices, divs, day)
            scored = score_universe(
                fund_day, min_score=config.min_score, strict_filters=True
            )
            tradable = scored.filtered[
                scored.filtered["ticker"].isin(day_prices.keys())
            ].copy()

            # Filtro de liquidez mínima (ADV)
            day_adv: dict[str, float] = {}
            if adv_20 is not None and day in adv_20.index:
                day_adv = adv_20.loc[day].dropna().to_dict()
            if config.min_daily_volume_brl > 0 and day_adv:
                valid_adv_tickers = {
                    t for t, v in day_adv.items() if float(v) >= config.min_daily_volume_brl
                }
                before_len = len(tradable)
                tradable = tradable[tradable["ticker"].isin(valid_adv_tickers)].copy()
                adv_excluded_count += max(0, before_len - len(tradable))

            if tradable.empty:
                notes.append(
                    f"{day.date()}: ninguém passou no filtro da tese/liquidez — "
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
            if config.max_adv_order_pct > 0 and day_adv:
                equity_now = float(portfolio.total_value(day_prices))
                weights = _cap_weights_by_adv(
                    weights, equity_now, day_adv, float(config.max_adv_order_pct)
                )

            # Fase B: Slippage dinâmico com base na liquidez
            eff_slippage_bps = config.costs.slippage_bps
            if config.costs.dynamic_slippage and adv_20 is not None and day in adv_20.index:
                day_adv_mean = float(adv_20.loc[day].mean()) if not adv_20.loc[day].empty else 1_000_000.0
                order_size_est = portfolio.total_value(day_prices) / max(len(picks), 1)
                impact_factor = float(np.sqrt(order_size_est / max(day_adv_mean, 100_000.0)))
                eff_slippage_bps = config.costs.slippage_bps + float(config.costs.slippage_gamma * impact_factor * 10_000.0)
                eff_slippage_bps = min(eff_slippage_bps, 150.0)

            trades = portfolio.rebalance_to_weights(
                weights,
                day_prices,
                buckets=buckets,
                note=f"rebalance-{day.date()}",
                ts=day.isoformat(),
                fee_bps=config.costs.fee_bps,
                slippage_bps=eff_slippage_bps,
                capital_gains_rate=config.costs.capital_gains_rate,
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
        "pit_origin": pit_origin,
        "ttm_yield_overlay": True,
        "min_daily_volume_brl": config.min_daily_volume_brl,
        "max_adv_order_pct": config.max_adv_order_pct,
        "adv_excluded_count": adv_excluded_count,
        "costs_enabled": config.costs.enabled,
        "cost_fee_bps": config.costs.fee_bps,
        "cost_slippage_bps": config.costs.slippage_bps,
        "cost_tax_rate": config.costs.tax_rate,
        "cost_jcp_share": config.costs.jcp_share,
        "cost_capital_gains_rate": config.costs.capital_gains_rate,
        "cost_dynamic_slippage": config.costs.dynamic_slippage,
        "cost_dividend_cash_lag_days": config.costs.dividend_cash_lag_days,
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

    notes.append(
        "MERCADO: no rebalance, preço = fechamento do dia e DY = TTM 12 meses "
        "dos dividendos já pagos (sem look-ahead de mercado)."
    )
    if config.fundamentals_by_date and n_pit > 0:
        origin_txt = pit_origin or "injetado"
        if str(origin_txt).startswith("cvm"):
            notes.append(
                f"PIT CVM: {n_pit} rebalances usaram contas DFP/ITR vigentes até a data "
                f"({n_snap} caíram para o retrato atual). Origem={origin_txt}."
            )
        elif origin_txt == "injected":
            notes.append(
                f"PIT: {n_pit} rebalances usaram snapshots injetados "
                f"(sem look-ahead além da data); {n_snap} caíram para o retrato atual."
            )
        else:
            notes.append(
                f"PIT SEMENTE: {n_pit} rebalances usaram o JSON curado "
                f"(não é parse da CVM). {n_snap} caíram para o retrato atual. "
                "Rode scripts/download_cvm_data.py --build para promover."
            )
    elif not config.fundamentals_by_date:
        notes.append(
            "LIMITE: score usou o snapshot ATUAL em todos os rebalances "
            "(sem histórico point-in-time). Resultados validam o fluxo, não "
            "o desempenho contábil histórico."
        )

    if config.min_daily_volume_brl > 0:
        notes.append(
            f"LIQUIDEZ (ADV): volume mínimo diário R$ {config.min_daily_volume_brl:,.0f} "
            f"(exclusões por liquidez: {adv_excluded_count})."
        )

    if config.costs.enabled:
        extra_c = []
        if config.costs.dynamic_slippage:
            extra_c.append("slippage dinâmico por liquidez")
        if config.costs.dividend_cash_lag_days > 0:
            extra_c.append(f"cash lag {config.costs.dividend_cash_lag_days}d")
        extra_txt = f" ({', '.join(extra_c)})" if extra_c else ""
        notes.append(
            f"CUSTOS: fee {config.costs.fee_bps:.0f} bps, slippage base "
            f"{config.costs.slippage_bps:.0f} bps{extra_txt}, JCP {config.costs.jcp_share:.0%} "
            f"do provento a 15%, IR ganho {config.costs.capital_gains_rate:.0%} na venda."
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
