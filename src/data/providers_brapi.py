"""Provedor de dados B3 via brapi.dev (fonte BR gratuita).

Permite usar uma fonte brasileira dedicada além do Yahoo. A API pública do
brapi.dev (sem token) tem limite de chamadas por minuto, então:
- cada batch de tickers é único;
- usamos cache em disco com TTL (o mesmo helper de providers.py);
- em caso de erro/rate-limit, view retorna vazio (a UI cai para demo/metadata).

Endpoints usados (plano gratuito):
- ``GET /api/quote/<TICKER>`` → fundamentos (longName, sector, marketCap,
  dividendYield, roe, etc.)
- ``GET /api/quote/<TICKER>?range=1y&interval=1d`` → histórico de preços
- ``GET /api/quote/<TICKER>?dividends=true`` → histórico de dividendos
"""

from __future__ import annotations

import contextlib
from datetime import datetime
from typing import Any

import pandas as pd

from src.config import get_settings
from src.data.providers import DataProvider, _read_cache, _write_cache
from src.data.reference import get_ticker_meta
from src.data.ttl import ttl_for
from src.data.universe import normalize_ticker
from src.utils import utcnow, utcnow_date


def _naive(x: datetime | str | None = None) -> pd.Timestamp:
    """Timestamp naive normalizado (sem timezone) — compatível com colunas datetime64."""
    ts = pd.Timestamp(x if x is not None else utcnow())
    if ts.tzinfo is not None:
        ts = ts.tz_localize(None)
    return ts.normalize()


def _first(*values: Any) -> Any:
    """Primeiro valor preenchido (cobre chaves diferentes entre versões da API)."""
    for v in values:
        if v is not None and str(v).strip() not in ("", "NaT", "None"):
            return v
    return None


class BrapiDataProvider(DataProvider):
    """Provider B3 via brapi.dev. name='brapi'."""

    name = "brapi"  # type: ignore[assignment]

    def __init__(self, base_url: str = "https://brapi.dev/api", token: str | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.settings = get_settings()
        # Token opcional da .env (BRAPI_TOKEN) — aumenta limites da API gratuita.
        self.token = token or getattr(self.settings, "brapi_token", None)

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"} if self.token else {}

    def _get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        import requests

        url = f"{self.base_url}{path}"
        resp = requests.get(url, params=params, headers=self._headers(), timeout=30)
        resp.raise_for_status()
        return resp.json()

    def _fetch_quote(self, ticker: str) -> dict[str, Any]:
        """Uma cotação única (fundamentos + último preço)."""
        cache_key = f"brapi_q:{ticker}"
        cached = _read_cache(cache_key, ttl_for("brapi_quote", self.settings))
        if cached is not None:
            return cached
        try:
            data = self._get(f"/quote/{normalize_ticker(ticker)}", {"range": "1d", "interval": "1d"})
            results = data.get("results") or []
            if not results:
                return {}
            q = results[0]
            _write_cache(cache_key, q)
            return q
        except Exception:
            return {}

    def get_fundamentals(self, tickers: list[str] | None = None) -> pd.DataFrame:
        from datetime import timedelta

        universe = [normalize_ticker(t) for t in (tickers or [])]
        rows: list[dict[str, Any]] = []
        for t in universe:
            q = self._fetch_quote(t)
            if not q:
                # Sem dados do brapi (erro/rate-limit): pula o papel — a UI
                # cai para demo/metadata em vez de criar linha com tudo None.
                continue
            meta = get_ticker_meta(t)
            price = q.get("regularMarketPrice")
            dy = q.get("dividendYield") or q.get("dy") or None
            if dy is not None and dy > 1:
                # brapi ás vezes devolve DY em percentual (ex.: 5.0)
                dy = dy / 100.0

            # ROE/payout não vêm do plano gratuito — deixamos None (honesto),
            # mas preenchemos o que dá: PE e EPS.
            pe = q.get("priceEarnings") or q.get("pe") or None
            earnings = q.get("earningsPerShare") or None
            if isinstance(earnings, dict):
                earnings = earnings.get("average") or earnings.get("value")
            payout = None
            try:
                if dy and earnings and float(earnings) > 0 and price:
                    payout = dy * float(price) / float(earnings)
            except (TypeError, ValueError, ZeroDivisionError):
                payout = None

            fcf = q.get("freeCashFlow")
            fcf_yield = None
            fcf_positive = None
            mcap = q.get("marketCap")
            if fcf is not None:
                try:
                    fcf_f = float(fcf)
                    fcf_positive = fcf_f > 0
                    if mcap and float(mcap) > 0:
                        fcf_yield = fcf_f / float(mcap)
                except (TypeError, ValueError, ZeroDivisionError):
                    fcf_positive = None
                    fcf_yield = None

            rows.append(
                {
                    "ticker": t,
                    "name": q.get("longName") or meta.get("name") or t,
                    "sector": meta.get("sector") or "Unknown",
                    "industry": meta.get("industry"),
                    "price": float(price) if price else None,
                    "market_cap": q.get("marketCap") or None,
                    "dividend_yield": float(dy) if dy is not None else None,
                    "roe": None,
                    "roic": None,
                    "roa": None,
                    "net_margin": None,
                    "ebitda_margin": None,
                    "gross_margin": None,
                    "payout": float(payout) if payout is not None else None,
                    "fcf_yield": fcf_yield,
                    "fcf_positive": fcf_positive,
                    "net_debt_ebitda": None,
                    "debt_equity": None,
                    "current_ratio": None,
                    "interest_coverage": None,
                    "pe": float(pe) if pe is not None else None,
                    "pb": None,
                    "ev_ebitda": None,
                    "peg": None,
                    "revenue_cagr_5y": None,
                    "earnings_cagr_5y": None,
                    "dividend_cagr_5y": None,
                    "years_paying_dividend": None,
                    "currency": "BRL",
                    "as_of": utcnow_date(),
                    "source": "brapi",
                    "data_quality": "market_partial",
                    "meta_source": meta.get("source") or "reference",
                    "ticker_status": meta.get("status") or "unknown",
                }
            )
        df = pd.DataFrame(rows)
        if not df.empty:
            df = df.set_index("ticker", drop=False)
        # Dy real: soma de dividendos dos últimos 12 meses / preço.
        try:
            if not df.empty and universe:
                div_start = (_naive() - timedelta(days=365)).strftime("%Y-%m-%d")
                div = self.get_dividend_history(list(df["ticker"]), start=div_start, end=None)
                if not div.empty and "label" in div.columns:
                    # Só dividendos em dinheiro (exclui bonificações)
                    div = div[div["label"].str.upper() != "BONIFICACAO"]
                by = div.groupby("ticker")["amount"].sum()
                for t in df["ticker"]:
                    if t in by.index and by[t] > 0:
                        px = float(df.loc[df["ticker"] == t, "price"].iloc[0] or 0)
                        if px > 0:
                            df.loc[df["ticker"] == t, "dividend_yield"] = float(by[t]) / px
        except Exception:
            pass
        if not df.empty:
            with contextlib.suppress(Exception):
                from src.data.quality import coverage_summary
                from src.monitoring import coverage_event

                coverage_event("fundamentals", coverage_summary(df))
        return df

    def get_price_history(
        self,
        tickers: list[str],
        start: str | datetime,
        end: str | datetime | None = None,
    ) -> pd.DataFrame:
        universe = [normalize_ticker(t) for t in tickers]

        start_s = _naive(start).strftime("%Y-%m-%d")
        end_s = _naive(end).strftime("%Y-%m-%d")
        cache_key = f"brapi_px:{','.join(universe)}:{start_s}:{end_s}"
        cached = _read_cache(cache_key, ttl_for("prices", self.settings))
        if cached is not None:
            df = pd.DataFrame(cached)
            if not df.empty:
                df["date"] = pd.to_datetime(df["date"], errors="coerce")
            with contextlib.suppress(Exception):
                from src.monitoring import cache_hit

                cache_hit("fetch_prices", source="brapi", n_tickers=len(universe))
            return df

        out_dfs: list[pd.DataFrame] = []
        from src.monitoring import timed

        with timed("fetch_prices", cache_hit=False, source="brapi", n_tickers=len(universe)):
            span_days = max(1, (_naive(end) - _naive(start)).days)
            if span_days <= 40:
                rng = "1mo"
            elif span_days <= 120:
                rng = "3mo"
            elif span_days <= 400:
                rng = "1y"
            elif span_days <= 800:
                rng = "2y"
            else:
                rng = "5y"
            for t in universe:
                try:
                    q = self._get(f"/quote/{t}", {"range": rng, "interval": "1d"})
                except Exception:
                    continue
                results = q.get("results") or []
                if not results:
                    continue
                hist = (results[0].get("historicalDataPrice") or []) if results else []
                rows = []
                for h in hist:
                    try:
                        raw_date = h["date"]
                        if isinstance(raw_date, (int, float)):
                            dt = pd.Timestamp(raw_date, unit="s").tz_localize(None)
                        else:
                            dt = pd.Timestamp(raw_date).tz_localize(None)
                        rows.append(
                            {
                                "date": dt,
                                "ticker": t,
                                "open": h.get("open"),
                                "high": h.get("high"),
                                "low": h.get("low"),
                                "close": h.get("close"),
                                "adj_close": h.get("adjustedClose", h.get("close")),
                                "volume": h.get("volume"),
                            }
                        )
                    except (KeyError, TypeError, ValueError):
                        continue
                if rows:
                    out_dfs.append(pd.DataFrame(rows))

        if not out_dfs:
            return pd.DataFrame(columns=["date", "ticker", "open", "high", "low", "close", "adj_close", "volume"])
        df = pd.concat(out_dfs, ignore_index=True)
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df = df.dropna(subset=["date"])
        df = df[(df["date"] >= _naive(start)) & (df["date"] <= _naive(end))]
        if df.empty:
            # Evita cachear vazio: uma falha transitória/range-limpo não deve
            # "envenenar" o cache e esconder dados que venham a existir.
            return df
        with contextlib.suppress(Exception):
            _write_cache(
                cache_key,
                df.assign(date=df["date"].astype(str)).to_dict(orient="records"),
            )
        return df

    def get_dividend_history(
        self,
        tickers: list[str],
        start: str | datetime,
        end: str | datetime | None = None,
    ) -> pd.DataFrame:
        start_ts = _naive(start)
        end_ts = _naive(end)
        rows: list[dict[str, Any]] = []
        for t in tickers:
            nt = normalize_ticker(t)
            try:
                q = self._get(f"/quote/{nt}", {"dividends": "true"})
                results = q.get("results") or []
                if not results:
                    continue
                hist = results[0].get("dividendsData") or {}
                # brapi: {'cashDividends': [...], 'stockDividends': [...]}
                # valor por ação vem em 'rate' (em ''rate'' não há 'value'); label
                # diferencia JCP/DIVIDENDO/BONIFICACAO.
                for div in hist.get("cashDividends") or []:
                    amt = div.get("value")
                    if amt is None:
                        amt = div.get("rate")
                    if amt is None:
                        continue
                    # Entitlement: exDate. lastDatePrior é data-com (véspera da ex).
                    # Nunca usar paymentDate como data de direito.
                    raw_ex = _first(div.get("exDate"), div.get("dataEx"))
                    try:
                        if raw_ex:
                            ex_date = _naive(raw_ex)
                        elif _first(div.get("lastDatePrior")):
                            com = _naive(div.get("lastDatePrior"))
                            ex_date = (com + pd.Timedelta(days=1)).normalize()
                        else:
                            continue
                    except Exception:
                        continue
                    if pd.isna(ex_date):
                        continue
                    # Filtra pela data-ex (entitlement) — não pelo pagamento.
                    if start_ts <= ex_date <= end_ts:
                        rows.append(
                            {
                                "date": ex_date,
                                "ticker": nt,
                                "amount": float(amt),
                                "label": div.get("label") or "",
                                "ex_date": ex_date,
                                "payment_date": (
                                    _naive(_first(div.get("paymentDate"), div.get("payoutDate")))
                                    if _first(div.get("paymentDate"), div.get("payoutDate"))
                                    else pd.NaT
                                ),
                            }
                        )
            except Exception:
                continue
        if not rows:
            return pd.DataFrame(columns=["date", "ticker", "amount", "label", "ex_date", "payment_date"])
        return pd.DataFrame(rows)