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


_EMPTY_OHLCV = ("date", "ticker", "open", "high", "low", "close", "adj_close", "volume")
_OHLCV_FIELDS = {"open", "high", "low", "close", "volume", "adj_close", "adj close", "adjclose"}


def _column_label(col: Any) -> str:
    """Nome de coluna seguro mesmo com MultiIndex (nunca usa .astype no Index)."""
    if isinstance(col, tuple):
        # Preferência: parte que parece campo OHLCV
        for part in col:
            s = str(part).strip().lower().replace(" ", "_")
            if s in _OHLCV_FIELDS or (s.startswith("adj") and "close" in s):
                return str(part)
        return str(col[-1]) if col else ""
    return str(col)


def _map_ohlcv_frame(df: pd.DataFrame, ticker: str) -> pd.DataFrame | None:
    """Converte um DataFrame OHLCV (wide) em long padronizado para um ticker."""
    if df is None or df.empty:
        return None
    part = df.copy()
    if isinstance(part.columns, pd.MultiIndex):
        part.columns = [_column_label(c) for c in part.columns]
    else:
        part.columns = [str(c) for c in part.columns]

    part = part.reset_index()
    colmap: dict[Any, str] = {}
    for c in part.columns:
        cl = str(c).lower().replace(" ", "_")
        if cl in {"open", "high", "low", "close", "volume"}:
            colmap[c] = cl
        elif "adj" in cl and "close" in cl or cl in {"adj_close", "adjclose"}:
            colmap[c] = "adj_close"
        elif cl in {"date", "datetime", "index"} or cl.endswith("date"):
            colmap[c] = "date"
    part = part.rename(columns=colmap)

    if "date" not in part.columns:
        # reset_index costuma deixar a data na 1ª coluna
        first = part.columns[0]
        if str(first).lower() not in {"open", "high", "low", "close", "volume", "adj_close", "ticker"}:
            part = part.rename(columns={first: "date"})

    if "close" not in part.columns:
        return None
    if "adj_close" not in part.columns:
        part["adj_close"] = part["close"]
    for need in ("open", "high", "low"):
        if need not in part.columns:
            part[need] = part["close"]
    if "volume" not in part.columns:
        part["volume"] = 0

    part["ticker"] = ticker
    out = part.loc[:, list(_EMPTY_OHLCV)].copy()
    out["date"] = pd.to_datetime(out["date"], errors="coerce")
    for c in ("open", "high", "low", "close", "adj_close", "volume"):
        out[c] = pd.to_numeric(out[c], errors="coerce")
    return out.dropna(subset=["date", "close"])


def _yf_download_to_long(
    raw: pd.DataFrame,
    tickers_n: list[str],
    symbols: list[str],
) -> pd.DataFrame:
    """Normaliza saída do yf.download (single/multi, MultiIndex ou flat) → long OHLCV."""
    empty = pd.DataFrame(columns=list(_EMPTY_OHLCV))
    if raw is None or getattr(raw, "empty", True):
        return empty

    frames: list[pd.DataFrame] = []
    t_to_sym = dict(zip(tickers_n, symbols))

    def _resolve_key(candidates: set[str], ticker: str, symbol: str) -> str | None:
        if symbol in candidates:
            return symbol
        if ticker in candidates:
            return ticker
        for c in candidates:
            if normalize_ticker(str(c)) == ticker:
                return c
            # ITUB4.SA vs ITUB4
            if str(c).upper().replace(".SA", "") == ticker.upper():
                return c
        return None

    if isinstance(raw.columns, pd.MultiIndex) and raw.columns.nlevels >= 2:
        level0 = {str(x) for x in raw.columns.get_level_values(0)}
        level1 = {str(x) for x in raw.columns.get_level_values(1)}
        # group_by="ticker" → nível 0 = ticker; senão nível 0 = Open/High/...
        looks_like_fields = any(
            str(x).lower().replace(" ", "_") in _OHLCV_FIELDS for x in level0
        )
        for t in tickers_n:
            sym = t_to_sym[t]
            try:
                if looks_like_fields:
                    key = _resolve_key(level1, t, sym)
                    if key is None:
                        continue
                    sub = raw.xs(key, axis=1, level=1, drop_level=True)
                else:
                    key = _resolve_key(level0, t, sym)
                    if key is None:
                        continue
                    sub = raw[key]
                    if isinstance(sub, pd.DataFrame) and isinstance(sub.columns, pd.MultiIndex):
                        sub.columns = [_column_label(c) for c in sub.columns]
                mapped = _map_ohlcv_frame(sub if isinstance(sub, pd.DataFrame) else sub.to_frame(), t)
                if mapped is not None and not mapped.empty:
                    frames.append(mapped)
            except Exception:
                continue
    else:
        # Colunas flat: 1 ticker, ou download sem MultiIndex
        if len(tickers_n) == 1:
            mapped = _map_ohlcv_frame(raw, tickers_n[0])
            if mapped is not None and not mapped.empty:
                frames.append(mapped)
        else:
            # tenta por símbolo como coluna de 1º nível (raro sem MultiIndex)
            for t, sym in zip(tickers_n, symbols):
                if sym in raw.columns or t in raw.columns:
                    key = sym if sym in raw.columns else t
                    sub = raw[key]
                    mapped = _map_ohlcv_frame(
                        sub if isinstance(sub, pd.DataFrame) else sub.to_frame(name="close"),
                        t,
                    )
                    if mapped is not None and not mapped.empty:
                        frames.append(mapped)

    if not frames:
        return empty
    out = pd.concat(frames, ignore_index=True)
    return out.dropna(subset=["close"])


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
        """Números sintéticos + metadados REAIS do cadastro B3 (nome/setor).

        Nunca inventa setor a partir do índice do ticker — isso gerava erros
        graves (ex.: LREN3 como Utilities). Indicadores (ROE, DY, etc.) no
        modo demo **continuam fictícios** e não devem embasar dinheiro real.
        """
        from src.data.reference import get_ticker_meta

        rows = []
        for t in self._universe:
            rng = self._rng_for(t)
            meta = get_ticker_meta(t)
            sector = meta.get("sector") or "Unknown"
            industry = meta.get("industry")
            name = meta.get("name") or t
            # qualidade um pouco maior se setor está no core da tese
            is_core = sector in CORE_SECTORS
            quality_boost = 0.06 if is_core else 0.0
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
                    "name": name,
                    "sector": sector,
                    "industry": industry,
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
                    "source": "demo_synthetic_metrics+b3_reference_meta",
                    "data_quality": "synthetic_fundamentals",
                    "meta_source": meta.get("source") or "reference",
                    "ticker_status": meta.get("status") or "unknown",
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
        """Snapshot via Yahoo — paralelo, com teto de tickers e timeout.

        `tk.info` síncrono em 200 papéis trava a UI. Aqui:
        - limita ao scan prioritário se lista for enorme
        - busca em threads com timeout por ticker
        - nome/setor sempre com fallback no cadastro B3
        """
        import yfinance as yf
        from concurrent.futures import ThreadPoolExecutor, as_completed

        from src.data.reference import get_ticker_meta, resolve_successor

        raw_list = [normalize_ticker(t) for t in (tickers or get_universe(mode="core"))]
        tickers_resolved: list[str] = []
        seen: set[str] = set()
        for t in raw_list:
            nt = resolve_successor(t)
            meta = get_ticker_meta(nt)
            if meta.get("status") == "delisted_or_renamed":
                continue
            if nt not in seen:
                seen.add(nt)
                tickers_resolved.append(nt)

        max_n = int(getattr(self.settings, "yfinance_max_tickers", 40) or 40)
        if len(tickers_resolved) > max_n:
            # prioriza core scan se a lista veio full
            core = get_universe(mode="core")
            ordered = [t for t in core if t in set(tickers_resolved)]
            rest = [t for t in tickers_resolved if t not in set(ordered)]
            tickers_resolved = (ordered + rest)[:max_n]

        cache_key = f"yf_fund_v4:{','.join(sorted(tickers_resolved))}"
        cached = _read_cache(cache_key, self.settings.cache_ttl_hours)
        if cached is not None:
            return pd.DataFrame(cached)

        workers = int(getattr(self.settings, "yfinance_workers", 8) or 8)
        t_timeout = float(getattr(self.settings, "yfinance_ticker_timeout", 4.0) or 4.0)

        def _fetch_one(t: str) -> dict[str, Any] | None:
            try:
                meta = get_ticker_meta(t)
                sym = to_yf_symbol(t)
                tk = yf.Ticker(sym)
                price = 0.0
                # fast_info primeiro (bem mais rápido que .info)
                try:
                    fast = getattr(tk, "fast_info", None)
                    if fast is not None:
                        price = float(
                            getattr(fast, "last_price", None)
                            or getattr(fast, "lastPrice", None)
                            or 0
                        )
                except Exception:
                    price = 0.0

                info: dict[str, Any] = {}
                try:
                    info = tk.info or {}
                except Exception:
                    info = {}

                if not price:
                    price = float(
                        info.get("currentPrice")
                        or info.get("regularMarketPrice")
                        or info.get("previousClose")
                        or 0
                    )

                pe = info.get("trailingPE") or info.get("forwardPE")
                dy = info.get("dividendYield")
                if dy is not None and dy > 1:
                    dy = dy / 100.0
                payout = info.get("payoutRatio")
                roe = info.get("returnOnEquity")
                roa = info.get("returnOnAssets")
                debt_eq = info.get("debtToEquity")
                if debt_eq is not None and debt_eq > 5:
                    debt_eq = debt_eq / 100.0
                ebitda = info.get("ebitda")
                total_debt = info.get("totalDebt")
                cash = info.get("totalCash") or 0
                net_debt_ebitda = None
                if ebitda and ebitda > 0 and total_debt is not None:
                    net_debt_ebitda = (total_debt - cash) / ebitda

                yf_name = info.get("shortName") or info.get("longName")
                yf_sector = info.get("sector")
                yf_industry = info.get("industry")
                name = yf_name or meta.get("name") or t
                sector = yf_sector or meta.get("sector") or "Unknown"
                industry = yf_industry or meta.get("industry")
                quality = (
                    "market"
                    if (price and price > 0)
                    else "partial"
                )
                return {
                    "ticker": t,
                    "name": name,
                    "sector": sector,
                    "industry": industry,
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
                    "data_quality": quality,
                    "meta_source": (
                        "yfinance" if yf_sector else (meta.get("source") or "reference")
                    ),
                    "ticker_status": meta.get("status") or "unknown",
                }
            except Exception:
                return None

        rows: list[dict[str, Any]] = []
        # deadline global para não travar a UI (ex.: 40s)
        global_timeout = min(45.0, max(12.0, len(tickers_resolved) * t_timeout / max(workers, 1) + 8))
        with ThreadPoolExecutor(max_workers=max(2, workers)) as pool:
            futs = {pool.submit(_fetch_one, t): t for t in tickers_resolved}
            try:
                for fut in as_completed(futs, timeout=global_timeout):
                    try:
                        row = fut.result(timeout=0.1)
                    except Exception:
                        row = None
                    if row:
                        rows.append(row)
            except Exception:
                # TimeoutError de as_completed — segue com o que já veio
                pass

        # se Yahoo falhou quase tudo, ainda devolve meta+preço vazio a partir do cadastro
        # (melhor que travar / tela em branco)
        got = {r["ticker"] for r in rows}
        for t in tickers_resolved:
            if t in got:
                continue
            meta = get_ticker_meta(t)
            rows.append(
                {
                    "ticker": t,
                    "name": meta.get("name") or t,
                    "sector": meta.get("sector") or "Unknown",
                    "industry": meta.get("industry"),
                    "price": 0.0,
                    "market_cap": None,
                    "roe": None,
                    "roic": None,
                    "roa": None,
                    "net_margin": None,
                    "ebitda_margin": None,
                    "gross_margin": None,
                    "dividend_yield": None,
                    "payout": None,
                    "net_debt_ebitda": None,
                    "debt_equity": None,
                    "current_ratio": None,
                    "interest_coverage": None,
                    "pe": None,
                    "pb": None,
                    "ev_ebitda": None,
                    "peg": None,
                    "fcf_yield": None,
                    "revenue_cagr_5y": None,
                    "earnings_cagr_5y": None,
                    "dividend_cagr_5y": None,
                    "years_paying_dividend": None,
                    "fcf_positive": None,
                    "currency": "BRL",
                    "as_of": datetime.utcnow().date().isoformat(),
                    "source": "yfinance",
                    "data_quality": "unavailable",
                    "meta_source": meta.get("source") or "reference",
                    "ticker_status": meta.get("status") or "unknown",
                }
            )

        df = pd.DataFrame(rows)
        if not df.empty:
            # só cacheia se pelo menos 1 preço veio
            if (df["price"].fillna(0) > 0).any():
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
                df["date"] = pd.to_datetime(df["date"], errors="coerce")
            return df

        if not symbols:
            return pd.DataFrame(columns=list(_EMPTY_OHLCV))

        try:
            raw = yf.download(
                symbols if len(symbols) > 1 else symbols[0],
                start=start_s,
                end=end_s,
                group_by="ticker",
                auto_adjust=False,
                threads=True,
                progress=False,
            )
        except Exception:
            return pd.DataFrame(columns=list(_EMPTY_OHLCV))

        out = _yf_download_to_long(raw, tickers_n, symbols)
        if out.empty:
            return pd.DataFrame(columns=list(_EMPTY_OHLCV))

        try:
            _write_cache(
                cache_key,
                out.assign(date=out["date"].astype(str)).to_dict(orient="records"),
            )
        except Exception:
            pass
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
