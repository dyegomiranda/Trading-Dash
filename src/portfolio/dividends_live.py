"""Crédito de dividendos “ao vivo” na carteira paper (treino)."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import pandas as pd

from src.data.asset_type import asset_kind, dividend_tax_rate
from src.data.providers import DataProvider, get_provider
from src.data.universe import normalize_ticker
from src.portfolio.paper import DividendEvent, PaperPortfolio
from src.utils import utcnow


def _as_naive_ts(value: Any) -> pd.Timestamp:
    ts = pd.Timestamp(value)
    if ts.tzinfo is not None:
        try:
            ts = ts.tz_convert(None)
        except Exception:
            ts = ts.tz_localize(None)
    return ts


def _lookback_start(portfolio: PaperPortfolio, max_days: int = 540) -> pd.Timestamp:
    """Janela de busca de dividendos na fonte (ampla).

    A busca é larga; o crédito ainda só ocorre se havia posição na data.
    """
    floor = _as_naive_ts(utcnow()) - timedelta(days=int(max_days))
    return floor.normalize()


def _first_buy_date(portfolio: PaperPortfolio, ticker: str) -> pd.Timestamp | None:
    ticker = normalize_ticker(ticker)
    buys = []
    for t in portfolio.trades:
        if normalize_ticker(t.ticker) != ticker or t.side != "buy":
            continue
        buys.append(_as_naive_ts(t.ts))
    if not buys:
        return None
    return min(buys)


def credit_estimated_monthly(
    portfolio: PaperPortfolio,
    fundamentals: pd.DataFrame | None,
    prices: dict[str, float] | None = None,
    *,
    as_of: datetime | None = None,
) -> DividendEvent | None:
    """Credita uma estimativa mensal de dividendos com base no DY atual × posições.

    Serve para a conta de treino “mostrar renda” mesmo quando a compra é recente
    e ainda não houve data-ex real. Identificador único por mês: ``EST|YYYY-MM``.
    """
    prices = prices or {}
    now = as_of or utcnow()
    month_key = pd.Timestamp(now).strftime("%Y-%m")
    ex_date = f"EST|{month_key}"
    # reutiliza chave ticker|ex_date — usamos ticker sintético PORTFOLIO
    if f"PORTFOLIO|{ex_date}" in portfolio._dividend_keys():
        return None
    if not portfolio.positions:
        return None

    fund = fundamentals if fundamentals is not None else pd.DataFrame()
    dy_map: dict[str, float] = {}
    if not fund.empty and "ticker" in fund.columns:
        for _, row in fund.iterrows():
            t = normalize_ticker(str(row.get("ticker")))
            try:
                dy = float(row.get("dividend_yield"))
                if dy == dy and dy > 0:
                    dy_map[t] = dy
            except (TypeError, ValueError):
                continue

    total = 0.0
    parts: list[str] = []
    for t, pos in portfolio.positions.items():
        nt = normalize_ticker(t)
        dy = dy_map.get(nt)
        if dy is None or dy <= 0:
            continue
        px = float(prices.get(nt, pos.avg_price) or pos.avg_price or 0)
        if px <= 0 or pos.shares <= 0:
            continue
        # 1/12 do dividendo anual estimado sobre o valor de mercado
        piece = float(pos.shares) * px * dy / 12.0
        if piece > 0:
            total += piece
            parts.append(f"{nt}:{piece:.2f}")

    if total < 0.01:
        return None

    # Credita como um evento agregado no caixa (ticker PORTFOLIO só para dedup)
    portfolio.cash += total
    event = DividendEvent(
        id=str(__import__("uuid").uuid4()),
        ts=pd.Timestamp(now).isoformat(),
        ticker="PORTFOLIO",
        amount=total,
        shares=1.0,
        note="estimado-mensal:" + ",".join(parts[:12]),
        amount_per_share=total,
        ex_date=ex_date,
    )
    portfolio.dividends.append(event)
    portfolio._touch()
    return event


def sync_paper_dividends(
    portfolio: PaperPortfolio,
    provider: DataProvider | str = "yfinance",
    *,
    end: datetime | str | None = None,
    max_days: int = 540,
    fundamentals: pd.DataFrame | None = None,
    prices: dict[str, float] | None = None,
    allow_monthly_estimate: bool = False,
    jcp_share: float = 0.0,
) -> dict[str, Any]:
    """Busca dividendos e credita em caixa os ainda não registrados.

    1) **Pagamentos reais** da fonte (Yahoo/demo), se você já tinha ações na data
    2) Se nada foi creditado e ``allow_monthly_estimate``, credita **estimativa do mês**
       com base no % de dividendo atual das posições (claro no extrato)

    ``jcp_share`` modela JCP (fração do provento sujeita a IR). Default 0 =
    dividendos de AÇÃO isentos; 0.5 modela metade como JCP retido a 15%.
    FII sempre isento (regra do asset_type).
    """
    if isinstance(provider, str):
        prov = get_provider(provider)  # type: ignore[arg-type]
        provider_name = provider
    else:
        prov = provider
        provider_name = getattr(provider, "name", "custom")

    tickers = sorted({normalize_ticker(t) for t in portfolio.positions.keys()})
    for t in portfolio.trades:
        tickers.append(normalize_ticker(t.ticker))
    tickers = sorted(set(tickers))

    empty_result = {
        "credited": 0,
        "total_brl": 0.0,
        "events": [],
        "skipped_duplicate": 0,
        "skipped_no_shares": 0,
        "errors": [],
        "provider": provider_name,
        "tickers": tickers,
        "start": None,
        "end": None,
        "estimated": False,
        "message": "Carteira sem ações/ordens — monte a carteira primeiro.",
        "asset_kinds": {},
    }
    if not tickers:
        return empty_result

    start = _lookback_start(portfolio, max_days=max_days)
    end_ts = _as_naive_ts(end or utcnow())

    credited: list[DividendEvent] = []
    skipped_dup = 0
    skipped_shares = 0
    errors: list[str] = []
    total_brl = 0.0
    hist = pd.DataFrame()

    try:
        hist = prov.get_dividend_history(tickers, start=start, end=end_ts)
    except Exception as e:
        errors.append(f"Falha ao buscar dividendos: {e}")
        hist = pd.DataFrame()

    if hist is not None and not hist.empty:
        work = hist.copy()
        work["date"] = pd.to_datetime(work["date"], errors="coerce")
        work = work.dropna(subset=["date"]).sort_values("date")
        before_keys = portfolio._dividend_keys()

        for _, row in work.iterrows():
            try:
                ticker = normalize_ticker(str(row["ticker"]))
                dt = _as_naive_ts(row["date"])

                # Data-ex real quando a fonte fornece (`ex_date`); o que
                # decide o direito é a posição NA DATA-EX, não no pagamento.
                ex_value = row.get("ex_date") if "ex_date" in row.index else None
                ex_ts = (
                    _as_naive_ts(ex_value)
                    if ex_value is not None
                    and not (isinstance(ex_value, float) and pd.isna(ex_value))
                    and not pd.isna(ex_value)
                    else dt
                )
                day = ex_ts.strftime("%Y-%m-%d")
                per_share = float(row["amount"])
                if per_share <= 0:
                    continue

                key = f"{ticker}|{day}"
                if key in before_keys:
                    skipped_dup += 1
                    continue

                qty = portfolio.shares_at(ticker, ex_ts - pd.Timedelta(microseconds=1))
                # Na B3, tem direito quem tinha ação no fechamento do dia ANTERIOR
                # à data-ex. Portanto consideramos a posição até o fim do dia antes
                # do ex (ex_ts - 1µs): compra no próprio dia da data-ex não recebe.
                # Se não há trades (só posição legada), usa posição atual se div >= created.
                if qty <= 1e-12 and not portfolio.trades and ticker in portfolio.positions:
                    created = _as_naive_ts(portfolio.created_at)
                    if ex_ts.normalize() >= created.normalize():
                        qty = float(portfolio.positions[ticker].shares)

                if qty <= 1e-12:
                    skipped_shares += 1
                    continue

                event_ts = row.get("payment_date") if "payment_date" in row.index else None
                if event_ts is None or (isinstance(event_ts, float) and pd.isna(event_ts)) or pd.isna(event_ts):
                    event_ts = ex_ts

                ev = portfolio.credit_dividend(
                    ticker,
                    per_share,
                    ts=_as_naive_ts(event_ts).isoformat(),
                    note=f"sync-{provider_name}",
                    shares=qty,
                    ex_date=day,
                    skip_if_duplicate=True,
                    tax_rate=dividend_tax_rate(
                        ticker, jcp_share=jcp_share
                    ),
                )
                if ev is None:
                    skipped_dup += 1
                    continue
                before_keys.add(key)
                credited.append(ev)
                total_brl += float(ev.amount)
            except Exception as e:
                errors.append(str(e))

    estimated = False
    # Se não houve pagamento real no período em que você já tinha ações,
    # credita estimativa mensal (treino) para a UI não ficar “morta”.
    if not credited and allow_monthly_estimate and portfolio.positions:
        ev_est = credit_estimated_monthly(
            portfolio,
            fundamentals,
            prices=prices,
        )
        if ev_est is not None:
            credited.append(ev_est)
            total_brl += float(ev_est.amount)
            estimated = True

    asset_kinds: dict[str, str] = {t: asset_kind(t) for t in tickers}

    def _brl(x: float) -> str:
        return f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    if credited:
        if estimated and len(credited) == 1 and credited[0].ticker == "PORTFOLIO":
            msg = (
                f"Estimativa do mês creditada: {_brl(total_brl)}. "
                "Baseada no % de dividendo atual das suas ações "
                "(ainda não houve data-ex real desde a compra)."
            )
        elif estimated:
            msg = (
                f"{len(credited)} crédito(s) · {_brl(total_brl)} "
                "(inclui estimativa mensal)."
            )
        else:
            msg = f"{len(credited)} pagamento(s) real(is) creditado(s) · {_brl(total_brl)}"
    elif skipped_shares > 0 and (hist is not None and not hist.empty):
        msg = (
            f"A fonte trouxe {len(hist)} pagamento(s) no histórico, mas nenhum "
            "caiu em data em que você já tinha as ações. "
            "Compras recentes só recebem nas próximas datas-ex "
            "(ou uma estimativa mensal se ainda não rodou este mês)."
        )
    elif hist is None or hist.empty:
        msg = (
            "Nenhum dividendo encontrado na fonte neste período. "
            "Tente de novo em alguns minutos."
        )
    else:
        msg = "Nenhum dividendo novo para creditar."

    return {
        "credited": len(credited),
        "total_brl": total_brl,
        "events": credited,
        "skipped_duplicate": skipped_dup,
        "skipped_no_shares": skipped_shares,
        "errors": errors[:12],
        "provider": provider_name,
        "tickers": tickers,
        "start": start.date().isoformat(),
        "end": end_ts.date().isoformat(),
        "estimated": estimated,
        "hist_rows": 0 if hist is None or hist.empty else int(len(hist)),
        "message": msg,
        "asset_kinds": asset_kinds,
        "jcp_share": jcp_share,
    }


def dividends_frame(portfolio: PaperPortfolio) -> pd.DataFrame:
    """Tabela amigável dos dividendos já creditados."""
    if not portfolio.dividends:
        return pd.DataFrame(
            columns=[
                "data",
                "ticker",
                "qtd_acoes",
                "valor_por_acao",
                "total_recebido",
                "obs",
            ]
        )
    rows = []
    for d in portfolio.dividends:
        per = d.amount_per_share
        if (not per) and d.shares:
            per = d.amount / d.shares
        data_label = d.ex_date or (d.ts[:10] if d.ts else "")
        if str(data_label).startswith("EST|"):
            data_label = "Estimativa " + str(data_label).replace("EST|", "")
        ticker_label = d.ticker
        if d.ticker == "PORTFOLIO":
            ticker_label = "Carteira (estimado)"
        rows.append(
            {
                "data": data_label,
                "ticker": ticker_label,
                "qtd_acoes": d.shares if d.ticker != "PORTFOLIO" else "—",
                "valor_por_acao": per if d.ticker != "PORTFOLIO" else "—",
                "total_recebido": d.amount,
                "obs": d.note,
            }
        )
    df = pd.DataFrame(rows)
    return df.sort_values("data", ascending=False).reset_index(drop=True)
