"""Provedores de dados de mercado (live via yfinance e demo sintético)."""

from __future__ import annotations

import hashlib
import json
import time
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Literal

import numpy as np
import pandas as pd

from src.config import CACHE_DIR, CORE_SECTORS, get_settings
from src.data.universe import get_universe, normalize_ticker, to_yf_symbol

ProviderName = Literal["demo", "yfinance"]


class DataProvider(ABC):
    name: ProviderName

    @abstractmethod
    def get_fundamentals(self, tickers: list[str] | None = None) -> pd.DataFrame:
        """Snapshot fundamentalista atual (uma linha por ticker)."""

    @abstractmethod
    def get_price_history(
        self,
        tickers: list[str],
        start: str | datetime,
        end: str | datetime | None = None,
    ) -> pd.DataFrame:
        """Preços OHLC multi-ticker. Colunas MultiIndex (field, ticker) ou long format.
        Retorna long: date, ticker, open, high, low, close, volume, adj_close
        """

    @abstractmethod
    def get_dividend_history(
        self,
        tickers: list[str],
        start: str | datetime,
        end: str | datetime | None = None,
    ) -> pd.DataFrame:
        """Dividendos: date, ticker, amount."""

    def get_latest_prices(self, tickers: list[str]) -> pd.Series:
        end = datetime.utcnow()
        start = end - timedelta(days=14)
        hist = self.get_price_history(tickers, start=start, end=end)
        if hist.empty:
            return pd.Series(dtype=float)
        last = (
            hist.sort_values("date")
            .groupby("ticker", as_index=True)["close"]
            .last()
        )
        return last


def _cache_path(key: str) -> Path:
    h = hashlib.sha1(key.encode()).hexdigest()[:24]
    return CACHE_DIR / f"{h}.json"


def _read_cache(key: str, ttl_hours: int) -> Any | None:
    path = _cache_path(key)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if time.time() - payload.get("ts", 0) > ttl_hours * 3600:
            return None
        return payload.get("data")
    except Exception:
        return None


def _write_cache(key: str, data: Any) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = _cache_path(key)
    path.write_text(
        json.dumps({"ts": time.time(), "data": data}, default=str),
        encoding="utf-8",
    )


class DemoDataProvider(DataProvider):
    """Mercado sintético determinístico para testes offline e backtest."""

    name: ProviderName = "demo"

    def __init__(self, seed: int = 42) -> None:
        self.seed = seed
        self._universe = get_universe()
        self._fundamentals = self._build_fundamentals()
        self._price_cache: dict[str, pd.DataFrame] = {}

    def _rng_for(self, ticker: str) -> np.random.Generator:
        h = int(hashlib.md5(f"{self.seed}:{ticker}".encode()).hexdigest()[:8], 16)
        return np.random.default_rng(h)

    def _build_fundamentals(self) -> pd.DataFrame:
        rows = []
        sectors_core = list(CORE_SECTORS)[:8] or ["Utilities"]
        sectors_other = [
            "Energy",
            "Basic Materials",
            "Industrials",
            "Consumer Cyclical",
            "Technology",
            "Healthcare",
            "Real Estate",
        ]
        for i, t in enumerate(self._universe):
            rng = self._rng_for(t)
            is_core = i % 3 != 0
            sector = sectors_core[i % len(sectors_core)] if is_core else sectors_other[i % len(sectors_other)]
            # Qualidade maior para subset "core-like"
            quality_boost = 0.08 if is_core else 0.0
            roe = float(np.clip(rng.normal(0.16 + quality_boost, 0.07), -0.05, 0.45))
            roic = float(np.clip(roe - rng.uniform(0, 0.04), -0.05, 0.40))
            net_margin = float(np.clip(rng.normal(0.12 if is_core else 0.06, 0.05), -0.1, 0.35))
            ebitda_margin = float(np.clip(net_margin + rng.uniform(0.03, 0.12), 0, 0.5))
            dy = float(np.clip(rng.normal(0.065 if is_core else 0.04, 0.025), 0.0, 0.18))
            payout = float(np.clip(rng.normal(0.55, 0.15), 0.05, 0.95))
            debt = float(np.clip(rng.normal(1.5 if is_core else 2.8, 1.0), 0, 8))
            pe = float(np.clip(rng.normal(10 if is_core else 14, 5), 3, 40))
            pb = float(np.clip(rng.normal(1.6, 0.8), 0.3, 6))
            ev_ebitda = float(np.clip(rng.normal(7.5, 3), 2, 25))
            rev_cagr = float(np.clip(rng.normal(0.06, 0.08), -0.2, 0.35))
            earn_cagr = float(np.clip(rng.normal(0.05, 0.1), -0.3, 0.4))
            fcf_yield = float(np.clip(rng.normal(0.06, 0.04), -0.05, 0.2))
            div_growth = float(np.clip(rng.normal(0.05 if is_core else 0.01, 0.06), -0.3, 0.3))
            years_div = int(np.clip(rng.integers(1, 15) + (3 if is_core else 0), 0, 20))
            price = float(np.clip(rng.uniform(8, 80), 1, 200))
            rows.append(
                {
                    "ticker": t,
                    "name": t,
                    "sector": sector,
                    "price": price,
                    "market_cap": price * rng.uniform(2e8, 8e10),
                    "roe": roe,
                    "roic": roic,
                    "roa": roe * rng.uniform(0.3, 0.7),
                    "net_margin": net_margin,
                    "ebitda_margin": ebitda_margin,
                    "gross_margin": float(np.clip(ebitda_margin + rng.uniform(0.05, 0.2), 0, 0.7)),
                    "dividend_yield": dy,
                    "payout": payout,
                    "net_debt_ebitda": debt,
                    "debt_equity": float(np.clip(debt * rng.uniform(0.4, 1.2), 0, 10)),
                    "current_ratio": float(np.clip(rng.normal(1.4, 0.4), 0.4, 4)),
                    "interest_coverage": float(np.clip(rng.normal(6, 3), 0.2, 30)),
                    "pe": pe,
                    "pb": pb,
                    "ev_ebitda": ev_ebitda,
                    "peg": float(np.clip(pe / max(earn_cagr * 100, 1), 0.2, 8)),
                    "fcf_yield": fcf_yield,
                    "revenue_cagr_5y": rev_cagr,
                    "earnings_cagr_5y": earn_cagr,
                    "dividend_cagr_5y": div_growth,
                    "years_paying_dividend": years_div,
                    "fcf_positive": fcf_yield > 0,
                    "currency": "BRL",
                    "as_of": datetime.utcnow().date().isoformat(),
                    "source": "demo",
                }
            )
        return pd.DataFrame(rows).set_index("ticker", drop=False)

    def get_fundamentals(self, tickers: list[str] | None = None) -> pd.DataFrame:
        df = self._fundamentals.copy()
        if tickers:
            wanted = {normalize_ticker(t) for t in tickers}
            df = df[df["ticker"].isin(wanted)]
        return df.reset_index(drop=True)

    def _simulate_prices(
        self, ticker: str, start: pd.Timestamp, end: pd.Timestamp
    ) -> pd.DataFrame:
        key = f"{ticker}:{start.date()}:{end.date()}"
        if key in self._price_cache:
            return self._price_cache[key]
        rng = self._rng_for(ticker)
        fund = self._fundamentals.loc[ticker] if ticker in self._fundamentals.index else None
        base = float(fund["price"]) if fund is not None else 20.0
        quality = float(fund["roe"]) if fund is not None else 0.1
        days = pd.bdate_range(start, end)
        if len(days) == 0:
            return pd.DataFrame()
        mu = 0.08 + quality * 0.15  # drift anual
        vol = 0.22 - min(quality, 0.25) * 0.3
        dt = 1 / 252
        shocks = rng.normal((mu - 0.5 * vol**2) * dt, vol * np.sqrt(dt), size=len(days))
        # Começa com ruído histórico para não ancorar só no preço atual
        path = base * np.exp(np.cumsum(shocks[::-1])[::-1])
        path = path / path[-1] * base
        df = pd.DataFrame(
            {
                "date": days,
                "ticker": ticker,
                "open": path * (1 + rng.normal(0, 0.002, len(days))),
                "high": path * (1 + np.abs(rng.normal(0.005, 0.003, len(days)))),
                "low": path * (1 - np.abs(rng.normal(0.005, 0.003, len(days)))),
                "close": path,
                "adj_close": path,
                "volume": rng.integers(100_000, 5_000_000, len(days)),
            }
        )
        self._price_cache[key] = df
        return df

    def get_price_history(
        self,
        tickers: list[str],
        start: str | datetime,
        end: str | datetime | None = None,
    ) -> pd.DataFrame:
        start_ts = pd.Timestamp(start)
        end_ts = pd.Timestamp(end or datetime.utcnow())
        frames = []
        for t in tickers:
            nt = normalize_ticker(t)
            if nt not in self._fundamentals.index:
                continue
            frames.append(self._simulate_prices(nt, start_ts, end_ts))
        if not frames:
            return pd.DataFrame(
                columns=["date", "ticker", "open", "high", "low", "close", "adj_close", "volume"]
            )
        return pd.concat(frames, ignore_index=True)

    def get_dividend_history(
        self,
        tickers: list[str],
        start: str | datetime,
        end: str | datetime | None = None,
    ) -> pd.DataFrame:
        start_ts = pd.Timestamp(start)
        end_ts = pd.Timestamp(end or datetime.utcnow())
        rows = []
        for t in tickers:
            nt = normalize_ticker(t)
            if nt not in self._fundamentals.index:
                continue
            fund = self._fundamentals.loc[nt]
            dy = float(fund["dividend_yield"])
            price = float(fund["price"])
            annual = dy * price
            # 2 pagamentos anuais
            years = range(start_ts.year, end_ts.year + 1)
            for y in years:
                for month, day in ((5, 15), (11, 15)):
                    d = pd.Timestamp(year=y, month=month, day=day)
                    if start_ts <= d <= end_ts:
                        rows.append(
                            {
                                "date": d,
                                "ticker": nt,
                                "amount": annual / 2,
                            }
                        )
        if not rows:
            return pd.DataFrame(columns=["date", "ticker", "amount"])
        return pd.DataFrame(rows)


class YFinanceDataProvider(DataProvider):
    """Provedor live/histórico via yfinance (tickers .SA)."""

    name: ProviderName = "yfinance"

    def __init__(self) -> None:
        self.settings = get_settings()

    def get_fundamentals(self, tickers: list[str] | None = None) -> pd.DataFrame:
        import yfinance as yf

        tickers = [normalize_ticker(t) for t in (tickers or get_universe())]
        cache_key = f"yf_fund_v2:{','.join(sorted(tickers))}"
        cached = _read_cache(cache_key, self.settings.cache_ttl_hours)
        if cached is not None:
            return pd.DataFrame(cached)

        rows: list[dict[str, Any]] = []
        # Batch em blocos para não sobrecarregar
        batch_size = 20
        for i in range(0, len(tickers), batch_size):
            batch = tickers[i : i + batch_size]
            symbols = [to_yf_symbol(t) for t in batch]
            try:
                tickers_obj = yf.Tickers(" ".join(symbols))
            except Exception:
                tickers_obj = None
            for t, sym in zip(batch, symbols):
                try:
                    tk = (
                        tickers_obj.tickers.get(sym)
                        if tickers_obj is not None
                        else yf.Ticker(sym)
                    )
                    info = tk.info or {}
                    if not info or info.get("trailingPegRatio") is None and info.get("regularMarketPrice") is None:
                        # fallback rápido
                        fast = getattr(tk, "fast_info", None)
                        price = float(getattr(fast, "last_price", None) or 0) if fast else 0.0
                    else:
                        price = float(
                            info.get("currentPrice")
                            or info.get("regularMarketPrice")
                            or info.get("previousClose")
                            or 0
                        )
                    trailing_pe = info.get("trailingPE")
                    forward_pe = info.get("forwardPE")
                    pe = trailing_pe or forward_pe
                    dy = info.get("dividendYield")
                    # yfinance às vezes devolve DY já em fração, às vezes *100 inconsistente
                    if dy is not None and dy > 1:
                        dy = dy / 100.0
                    payout = info.get("payoutRatio")
                    roe = info.get("returnOnEquity")
                    roa = info.get("returnOnAssets")
                    debt_eq = info.get("debtToEquity")
                    if debt_eq is not None and debt_eq > 5:
                        # frequentemente vem *100
                        debt_eq = debt_eq / 100.0
                    ebitda = info.get("ebitda")
                    total_debt = info.get("totalDebt")
                    cash = info.get("totalCash") or 0
                    net_debt_ebitda = None
                    if ebitda and ebitda > 0 and total_debt is not None:
                        net_debt_ebitda = (total_debt - cash) / ebitda
                    rows.append(
                        {
                            "ticker": t,
                            "name": info.get("shortName") or info.get("longName") or t,
                            "sector": info.get("sector") or "Unknown",
                            "industry": info.get("industry"),
                            "price": price,
                            "market_cap": info.get("marketCap"),
                            "roe": roe,
                            "roic": info.get("returnOnCapital") or roe,
                            "roa": roa,
                            "net_margin": info.get("profitMargins"),
                            "ebitda_margin": info.get("ebitdaMargins"),
                            "gross_margin": info.get("grossMargins"),
                            "dividend_yield": dy,
                            "payout": payout,
                            "net_debt_ebitda": net_debt_ebitda,
                            "debt_equity": debt_eq,
                            "current_ratio": info.get("currentRatio"),
                            "interest_coverage": None,
                            "pe": pe,
                            "pb": info.get("priceToBook"),
                            "ev_ebitda": info.get("enterpriseToEbitda"),
                            "peg": info.get("pegRatio"),
                            "fcf_yield": (
                                (info.get("freeCashflow") / info.get("marketCap"))
                                if info.get("freeCashflow") and info.get("marketCap")
                                else None
                            ),
                            "revenue_cagr_5y": info.get("revenueGrowth"),
                            "earnings_cagr_5y": info.get("earningsGrowth"),
                            "dividend_cagr_5y": None,
                            "years_paying_dividend": None,
                            "fcf_positive": (
                                True
                                if info.get("freeCashflow") and info.get("freeCashflow") > 0
                                else (
                                    False
                                    if info.get("freeCashflow") is not None
                                    else None
                                )
                            ),
                            "currency": info.get("currency") or "BRL",
                            "as_of": datetime.utcnow().date().isoformat(),
                            "source": "yfinance",
                        }
                    )
                except Exception:
                    continue

        df = pd.DataFrame(rows)
        if not df.empty:
            _write_cache(cache_key, df.to_dict(orient="records"))
        return df

    def get_price_history(
        self,
        tickers: list[str],
        start: str | datetime,
        end: str | datetime | None = None,
    ) -> pd.DataFrame:
        import yfinance as yf

        tickers_n = [normalize_ticker(t) for t in tickers]
        symbols = [to_yf_symbol(t) for t in tickers_n]
        start_s = pd.Timestamp(start).strftime("%Y-%m-%d")
        end_s = pd.Timestamp(end or datetime.utcnow()).strftime("%Y-%m-%d")
        cache_key = f"yf_px:{','.join(symbols)}:{start_s}:{end_s}"
        cached = _read_cache(cache_key, self.settings.cache_ttl_hours)
        if cached is not None:
            df = pd.DataFrame(cached)
            if not df.empty:
                df["date"] = pd.to_datetime(df["date"])
            return df

        if not symbols:
            return pd.DataFrame(
                columns=["date", "ticker", "open", "high", "low", "close", "adj_close", "volume"]
            )

        raw = yf.download(
            symbols,
            start=start_s,
            end=end_s,
            group_by="ticker",
            auto_adjust=False,
            threads=True,
            progress=False,
        )
        frames = []
        if len(symbols) == 1:
            sym = symbols[0]
            t = tickers_n[0]
            if raw is None or raw.empty:
                return pd.DataFrame(
                    columns=["date", "ticker", "open", "high", "low", "close", "adj_close", "volume"]
                )
            part = raw.reset_index()
            part.columns = [str(c).lower().replace(" ", "_") for c in part.columns]
            part["ticker"] = t
            rename = {"adj_close": "adj_close", "date": "date"}
            if "adj_close" not in part.columns and "adj close" in [c.lower() for c in raw.columns.astype(str)]:
                pass
            colmap = {}
            for c in part.columns:
                cl = c.lower()
                if cl in {"open", "high", "low", "close", "volume"}:
                    colmap[c] = cl
                elif "adj" in cl:
                    colmap[c] = "adj_close"
                elif cl in {"date", "datetime", "index"}:
                    colmap[c] = "date"
            part = part.rename(columns=colmap)
            if "adj_close" not in part.columns:
                part["adj_close"] = part.get("close")
            frames.append(part[["date", "ticker", "open", "high", "low", "close", "adj_close", "volume"]])
        else:
            # MultiIndex columns
            for t, sym in zip(tickers_n, symbols):
                try:
                    if isinstance(raw.columns, pd.MultiIndex):
                        # yfinance may use ticker or symbol as first level
                        level0 = raw.columns.get_level_values(0)
                        key = sym if sym in set(level0) else t
                        if key not in set(level0):
                            # try without .SA
                            candidates = [c for c in set(level0) if normalize_ticker(str(c)) == t]
                            if not candidates:
                                continue
                            key = candidates[0]
                        sub = raw[key].copy()
                    else:
                        continue
                    sub = sub.reset_index()
                    sub.columns = [str(c) for c in sub.columns]
                    colmap = {}
                    for c in sub.columns:
                        cl = c.lower().replace(" ", "_")
                        if cl in {"open", "high", "low", "close", "volume"}:
                            colmap[c] = cl
                        elif "adj" in cl:
                            colmap[c] = "adj_close"
                        elif cl in {"date", "datetime"}:
                            colmap[c] = "date"
                    sub = sub.rename(columns=colmap)
                    sub["ticker"] = t
                    if "adj_close" not in sub.columns and "close" in sub.columns:
                        sub["adj_close"] = sub["close"]
                    frames.append(
                        sub[["date", "ticker", "open", "high", "low", "close", "adj_close", "volume"]]
                    )
                except Exception:
                    continue

        if not frames:
            return pd.DataFrame(
                columns=["date", "ticker", "open", "high", "low", "close", "adj_close", "volume"]
            )
        out = pd.concat(frames, ignore_index=True)
        out["date"] = pd.to_datetime(out["date"])
        out = out.dropna(subset=["close"])
        _write_cache(cache_key, out.assign(date=out["date"].astype(str)).to_dict(orient="records"))
        return out

    def get_dividend_history(
        self,
        tickers: list[str],
        start: str | datetime,
        end: str | datetime | None = None,
    ) -> pd.DataFrame:
        import yfinance as yf

        start_ts = pd.Timestamp(start)
        end_ts = pd.Timestamp(end or datetime.utcnow())
        rows = []
        for t in tickers:
            nt = normalize_ticker(t)
            sym = to_yf_symbol(nt)
            try:
                tk = yf.Ticker(sym)
                divs = tk.dividends
                if divs is None or len(divs) == 0:
                    continue
                s = divs.copy()
                s.index = pd.to_datetime(s.index).tz_localize(None)
                mask = (s.index >= start_ts) & (s.index <= end_ts)
                s = s.loc[mask]
                for dt, amt in s.items():
                    rows.append({"date": pd.Timestamp(dt), "ticker": nt, "amount": float(amt)})
            except Exception:
                continue
        if not rows:
            return pd.DataFrame(columns=["date", "ticker", "amount"])
        return pd.DataFrame(rows)


def get_provider(name: ProviderName = "demo") -> DataProvider:
    if name == "yfinance":
        return YFinanceDataProvider()
    return DemoDataProvider()
