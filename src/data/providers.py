"""Provedores de dados de mercado (live via yfinance e demo sintético)."""

from __future__ import annotations

import contextlib
import hashlib
import json
import time
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Literal

import numpy as np
import pandas as pd

from src.config import CACHE_DIR, get_settings
from src.data.reference import resolve_sector
from src.data.universe import get_universe, normalize_ticker, to_yf_symbol
from src.utils import utcnow, utcnow_date

ProviderName = Literal["demo", "yfinance", "brapi"]

# Fontes de mercado real (usam scan core rápido, têm banner de dados reais,
# não mostram aviso "modo treino"). Demo fica de fora.
REALTIME_PROVIDERS: frozenset[str] = frozenset({"yfinance", "brapi"})


def is_realtime_provider(name: str) -> bool:
    return name in REALTIME_PROVIDERS


def _cadastro_only_row(ticker: str) -> dict[str, Any]:
    """Nome/setor do cadastro B3 — sem números de balanço inventados."""
    from src.data.reference import get_ticker_meta

    t = normalize_ticker(ticker)
    meta = get_ticker_meta(t)
    return {
        "ticker": t,
        "name": meta.get("name") or t,
        "sector": resolve_sector(meta.get("sector")),
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
        "as_of": utcnow_date(),
        "source": "yfinance",
        "data_quality": "unavailable",
        "meta_source": meta.get("source") or "reference",
        "ticker_status": meta.get("status") or "unknown",
    }


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

    def get_split_history(
        self,
        tickers: list[str],
        start: str | datetime,
        end: str | datetime | None = None,
    ) -> pd.DataFrame:
        """Splits/bonificações: date, ticker, ratio (ações novas / velhas)."""
        return pd.DataFrame(columns=["date", "ticker", "ratio"])

    def get_latest_prices(self, tickers: list[str]) -> pd.Series:
        end = utcnow()
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


def _rating_from_score(roe: float) -> str:
    """Converte ROE em rating sintetico (AAA a C), útil para regras de saída.

    - ROE >= 20%     -> AAA
    - ROE >= 15%     -> AA
    - ROE >= 12%     -> A
    - ROE >= 10%     -> BBB
    - ROE >= 8%      -> BB
    - ROE >= 5%      -> B
    - ROE < 5%       -> C
    """
    if roe >= 0.20:
        return "AAA"
    if roe >= 0.15:
        return "AA"
    if roe >= 0.12:
        return "A"
    if roe >= 0.10:
        return "BBB"
    if roe >= 0.08:
        return "BB"
    if roe >= 0.05:
        return "B"
    return "C"


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


def _yf_dividends_from_download(
    raw: pd.DataFrame,
    tickers_n: list[str],
    symbols: list[str],
) -> pd.DataFrame:
    """Extrai coluna Dividends de yf.download(..., actions=True)."""
    empty = pd.DataFrame(columns=["date", "ticker", "amount"])
    if raw is None or getattr(raw, "empty", True):
        return empty
    if not isinstance(raw.columns, pd.MultiIndex) or raw.columns.nlevels < 2:
        return empty
    t_to_sym = dict(zip(tickers_n, symbols))
    level0 = [str(x) for x in raw.columns.get_level_values(0)]
    level0_is_field = any("dividend" in x.lower() or x.lower().replace(" ", "_") in _OHLCV_FIELDS for x in level0)
    rows: list[dict[str, Any]] = []
    for t in tickers_n:
        sym = t_to_sym[t]
        try:
            if level0_is_field:
                keys = {str(x) for x in raw.columns.get_level_values(1)}
                key = next((c for c in (sym, t, f"{t}.SA") if c in keys), None)
                if key is None:
                    continue
                sub = raw.xs(key, axis=1, level=1, drop_level=True)
            else:
                keys = {str(x) for x in raw.columns.get_level_values(0)}
                key = next((c for c in (sym, t, f"{t}.SA") if c in keys), None)
                if key is None:
                    continue
                sub = raw[key]
            if not isinstance(sub, pd.DataFrame):
                continue
            col = next((c for c in sub.columns if "dividend" in str(c).lower()), None)
            if col is None:
                continue
            s = pd.to_numeric(sub[col], errors="coerce").dropna()
            s = s[s > 0]
            for dt, amt in s.items():
                rows.append(
                    {"date": pd.Timestamp(dt).tz_localize(None) if getattr(pd.Timestamp(dt), "tzinfo", None) else pd.Timestamp(dt), "ticker": t, "amount": float(amt)}
                )
        except Exception:
            continue
    return pd.DataFrame(rows) if rows else empty


def _write_cache(key: str, data: Any) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = _cache_path(key)
    path.write_text(
        json.dumps({"ts": time.time(), "data": data}, default=str),
        encoding="utf-8",
    )


def clear_disk_cache() -> int:
    """Apaga o cache em disco (``data/cache/*.json``). Best effort, nunca falha.

    Retorna quantos arquivos foram removidos. Usado pelo refresh "forçado"
    (atualizar dados de mercado ignora o TTL do disco e busca de novo).
    """
    removed = 0
    try:
        if not CACHE_DIR.exists():
            return 0
        for p in CACHE_DIR.glob("*.json"):
            try:
                p.unlink()
                removed += 1
            except OSError:
                pass
    except Exception:
        return removed
    return removed


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
            sector = resolve_sector(meta.get("sector"))
            industry = meta.get("industry")
            name = meta.get("name") or t
            # qualidade um pouco maior se setor está no core da tese
            roe = float(np.clip(rng.normal(0.16, 0.07), -0.05, 0.45))
            roic = float(np.clip(roe - rng.uniform(0.01, 0.04), -0.05, 0.40))
            net_margin = float(np.clip(rng.normal(0.09, 0.05), -0.1, 0.35))
            ebitda_margin = float(np.clip(net_margin + rng.uniform(0.03, 0.12), 0, 0.5))
            dy = float(np.clip(rng.normal(0.06, 0.025), 0.0, 0.18))
            payout = float(np.clip(rng.normal(0.55, 0.15), 0.05, 0.95))
            debt = float(np.clip(rng.normal(1.8, 1.0), 0, 8))
            pe = float(np.clip(rng.normal(12, 5), 3, 40))
            pb = float(np.clip(rng.normal(1.6, 0.8), 0.3, 6))
            ev_ebitda = float(np.clip(rng.normal(7.5, 3), 2, 25))
            rev_cagr = float(np.clip(rng.normal(0.06, 0.08), -0.2, 0.35))
            earn_cagr = float(np.clip(rng.normal(0.05, 0.1), -0.3, 0.4))
            fcf_yield = float(np.clip(rng.normal(0.06, 0.04), -0.05, 0.2))
            div_growth = float(np.clip(rng.normal(0.03, 0.06), -0.3, 0.3))
            years_div = int(np.clip(rng.integers(2, 16), 0, 20))
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
                    "jcp": float(np.clip(rng.normal(0.15, 0.05), 0.05, 0.30)),
                    "rating": _rating_from_score(roe),
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
                    "as_of": utcnow_date(),
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
        dy = float(fund["dividend_yield"]) if fund is not None else 0.0
        days = pd.bdate_range(start, end)
        if len(days) == 0:
            return pd.DataFrame()
        mu = 0.06
        vol = 0.22
        dt = 1 / 252
        # GBM para frente a partir do preço-base. NÃO amarrar o último preço
        # ao valor de hoje — isso + queda ex-div gerava prejuízo sistemático.
        log_rets = rng.normal((mu - 0.5 * vol**2) * dt, vol * np.sqrt(dt), size=len(days))
        path = np.empty(len(days), dtype=float)
        path[0] = base
        if len(days) > 1:
            path[1:] = base * np.exp(np.cumsum(log_rets[1:]))
        if dy > 0:
            for i, day in enumerate(days):
                if (day.month, day.day) in ((5, 15), (11, 15)):
                    amt = float(path[i]) * dy / 2.0
                    path[i:] = np.maximum(path[i:] - amt, 0.5)
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
        end_ts = pd.Timestamp(end or utcnow())
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
        end_ts = pd.Timestamp(end or utcnow())
        rows = []
        for t in tickers:
            nt = normalize_ticker(t)
            if nt not in self._fundamentals.index:
                continue
            fund = self._fundamentals.loc[nt]
            dy = float(fund["dividend_yield"])
            px_df = self._simulate_prices(nt, start_ts, end_ts)
            px_map = {}
            if px_df is not None and not px_df.empty:
                tmp = px_df.copy()
                tmp["date"] = pd.to_datetime(tmp["date"]).dt.normalize()
                px_map = dict(zip(tmp["date"], tmp["close"]))
            fallback_amt = max(0.0, dy * float(fund["price"]) / 2.0)
            years = range(start_ts.year, end_ts.year + 1)
            for y in years:
                for month, day in ((5, 15), (11, 15)):
                    d = pd.Timestamp(year=y, month=month, day=day).normalize()
                    if start_ts.normalize() <= d <= end_ts.normalize():
                        close = float(px_map.get(d) or 0.0)
                        # Mesma conta da queda ex-div no preço (antes do corte).
                        amt = (close / (1.0 - dy / 2.0)) * (dy / 2.0) if dy < 1.8 and close > 0 else fallback_amt
                        if close <= 0:
                            amt = fallback_amt
                        rows.append(
                            {
                                "date": d,
                                "ticker": nt,
                                "amount": float(amt),
                                "ex_date": d,
                            }
                        )
        if not rows:
            return pd.DataFrame(columns=["date", "ticker", "amount", "ex_date"])
        return pd.DataFrame(rows)


class YFinanceDataProvider(DataProvider):
    """Provedor live/histórico via yfinance (tickers .SA)."""

    name: ProviderName = "yfinance"

    def __init__(self) -> None:
        from src.data.yf_quiet import silence_yfinance

        silence_yfinance()
        self.settings = get_settings()

    def get_fundamentals(self, tickers: list[str] | None = None) -> pd.DataFrame:
        """Snapshot: cadastro B3 + último DFP/ITR (CVM) + preço/DY em lote no Yahoo.

        Não chama ``tk.info`` em centenas de papéis (rate-limit → 80 preços de 369).
        """
        from src.data.pit_loader import overlay_pit_on_fundamentals
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

        max_n = int(getattr(self.settings, "yfinance_max_tickers", 400) or 400)
        if len(tickers_resolved) > max_n:
            # prioriza core scan se a lista veio full e excedeu o teto
            core = get_universe(mode="core")
            ordered = [t for t in core if t in set(tickers_resolved)]
            rest = [t for t in tickers_resolved if t not in set(ordered)]
            tickers_resolved = (ordered + rest)[:max_n]


        from src.data.ttl import ttl_for
        from src.monitoring import coverage_event, timed

        cache_key = f"yf_fund_v6:{','.join(sorted(tickers_resolved))}"
        cached = _read_cache(cache_key, ttl_for("fundamentals", self.settings))
        if cached is not None:
            with contextlib.suppress(Exception):
                from src.monitoring import cache_hit

                cache_hit("fetch_fundamentals", n_tickers=len(tickers_resolved))
            return pd.DataFrame(cached)

        rows = [_cadastro_only_row(t) for t in tickers_resolved]
        df = pd.DataFrame(rows)
        with timed("fetch_fundamentals", cache_hit=False, n_tickers=len(tickers_resolved)):
            df = overlay_pit_on_fundamentals(df)
            prices, yields = self._bulk_price_and_yield(tickers_resolved)
            if prices and "ticker" in df.columns:
                df["price"] = df["ticker"].map(lambda t: prices.get(str(t)) or 0.0)
            if yields and "ticker" in df.columns:
                dy_series = df["ticker"].map(lambda t: yields.get(str(t)))
                if "dividend_yield" not in df.columns:
                    df["dividend_yield"] = dy_series
                else:
                    df["dividend_yield"] = df["dividend_yield"].where(
                        df["dividend_yield"].notna(), dy_series
                    )
            if "data_quality" in df.columns:
                has_px = pd.to_numeric(df.get("price"), errors="coerce").fillna(0) > 0
                has_roe = df["roe"].notna() if "roe" in df.columns else False
                keep_pit = df["data_quality"].eq("pit_overlay")
                df.loc[has_px & has_roe & ~keep_pit, "data_quality"] = "market"
                df.loc[has_px & ~has_roe, "data_quality"] = "partial"

        if not df.empty:
            priced = pd.to_numeric(df.get("price"), errors="coerce").fillna(0).gt(0).sum()
            if priced >= max(1, int(len(df) * 0.25)):
                _write_cache(cache_key, df.to_dict(orient="records"))
            from src.data.quality import coverage_summary

            with contextlib.suppress(Exception):
                coverage_event("fundamentals", coverage_summary(df))
        return df

    def _bulk_price_and_yield(
        self, tickers: list[str]
    ) -> tuple[dict[str, float], dict[str, float]]:
        """Um download Yahoo (1 ano, actions=True) → último preço e DY TTM."""
        import yfinance as yf

        if not tickers:
            return {}, {}
        tickers_n = [normalize_ticker(t) for t in tickers]
        symbols = [to_yf_symbol(t) for t in tickers_n]
        try:
            from src.data.yf_retry import fetch_with_retry

            raw = fetch_with_retry(
                lambda: yf.download(
                    symbols if len(symbols) > 1 else symbols[0],
                    period="1y",
                    group_by="ticker",
                    auto_adjust=False,
                    actions=True,
                    threads=True,
                    progress=False,
                ),
                what=f"preços+proventos {len(symbols)} tickers",
            )
        except Exception:
            return {}, {}
        hist = _yf_download_to_long(raw, tickers_n, symbols)
        prices: dict[str, float] = {}
        if hist is not None and not hist.empty and "ticker" in hist.columns:
            last = hist.sort_values("date").groupby("ticker", as_index=True)["close"].last()
            prices = {
                str(k): float(v)
                for k, v in last.items()
                if v is not None and float(v) > 0
            }
        yields: dict[str, float] = {}
        try:
            divs = _yf_dividends_from_download(raw, tickers_n, symbols)
        except Exception:
            divs = pd.DataFrame()
        if divs is not None and not getattr(divs, "empty", True) and "ticker" in divs.columns:
            cutoff = pd.Timestamp(utcnow()) - pd.Timedelta(days=365)
            work = divs.copy()
            work["date"] = pd.to_datetime(work["date"], errors="coerce")
            work = work[work["date"] >= cutoff]
            sums = work.groupby("ticker")["amount"].sum()
            for t, total in sums.items():
                px = prices.get(str(t))
                if px and px > 0 and float(total) > 0:
                    yields[str(t)] = float(total) / px
        return prices, yields

    def get_price_history(
        self,
        tickers: list[str],
        start: str | datetime,
        end: str | datetime | None = None,
    ) -> pd.DataFrame:
        import yfinance as yf

        from src.data.ttl import ttl_for

        tickers_n = [normalize_ticker(t) for t in tickers]
        symbols = [to_yf_symbol(t) for t in tickers_n]
        start_s = pd.Timestamp(start).strftime("%Y-%m-%d")
        end_s = pd.Timestamp(end or utcnow()).strftime("%Y-%m-%d")
        cache_key = f"yf_px:{','.join(symbols)}:{start_s}:{end_s}"
        cached = _read_cache(cache_key, ttl_for("prices", self.settings))
        if cached is not None:
            df = pd.DataFrame(cached)
            if not df.empty:
                df["date"] = pd.to_datetime(df["date"], errors="coerce")
            with contextlib.suppress(Exception):
                from src.monitoring import cache_hit

                cache_hit("fetch_prices", n_tickers=len(symbols))
            return df

        if not symbols:
            return pd.DataFrame(columns=list(_EMPTY_OHLCV))

        from src.monitoring import timed

        try:
            with timed("fetch_prices", cache_hit=False, n_tickers=len(symbols)):
                from src.data.yf_retry import fetch_with_retry

                raw = fetch_with_retry(
                    lambda: yf.download(
                        symbols if len(symbols) > 1 else symbols[0],
                        start=start_s,
                        end=end_s,
                        group_by="ticker",
                        auto_adjust=False,
                        threads=True,
                        progress=False,
                    ),
                    what=f"preços {len(symbols)} tickers",
                )
        except Exception:
            return pd.DataFrame(columns=list(_EMPTY_OHLCV))

        out = _yf_download_to_long(raw, tickers_n, symbols)
        if out.empty:
            return pd.DataFrame(columns=list(_EMPTY_OHLCV))

        with contextlib.suppress(Exception):
            _write_cache(
                cache_key,
                out.assign(date=out["date"].astype(str)).to_dict(orient="records"),
            )
        return out

    def get_dividend_history(
        self,
        tickers: list[str],
        start: str | datetime,
        end: str | datetime | None = None,
    ) -> pd.DataFrame:
        import yfinance as yf

        from src.data.yf_retry import fetch_with_retry
        from src.monitoring import timed

        start_ts = pd.Timestamp(start)
        end_ts = pd.Timestamp(end or utcnow())
        rows = []
        with timed("fetch_dividends", cache_hit=False, n_tickers=len(tickers)):
            for t in tickers:
                nt = normalize_ticker(t)
                sym = to_yf_symbol(nt)
                try:
                    tk = yf.Ticker(sym)
                    divs = fetch_with_retry(
                        lambda: tk.dividends, what=f"dividendos {sym}"
                    )
                    if divs is None or len(divs) == 0:
                        continue
                    s = divs.copy()
                    s.index = pd.to_datetime(s.index).tz_localize(None)
                    mask = (s.index >= start_ts) & (s.index <= end_ts)
                    s = s.loc[mask]
                    for dt, amt in s.items():
                        # O índice do Yahoo PARA dividendos é a data-ex
                        # (quem tinha ação até esse dia tem direito ao provento).
                        d_ex = pd.Timestamp(dt)
                        rows.append(
                            {
                                "date": d_ex,
                                "ticker": nt,
                                "amount": float(amt),
                                "ex_date": d_ex,
                            }
                        )
                except Exception:
                    continue
        if not rows:
            return pd.DataFrame(columns=["date", "ticker", "amount", "ex_date"])
        return pd.DataFrame(rows)

    def get_split_history(
        self,
        tickers: list[str],
        start: str | datetime,
        end: str | datetime | None = None,
    ) -> pd.DataFrame:
        import yfinance as yf

        from src.data.yf_retry import fetch_with_retry

        start_ts = pd.Timestamp(start)
        end_ts = pd.Timestamp(end or utcnow())
        rows = []
        for t in tickers:
            nt = normalize_ticker(t)
            sym = to_yf_symbol(nt)
            try:
                tk = yf.Ticker(sym)
                splits = fetch_with_retry(lambda: tk.splits, what=f"splits {sym}")
                if splits is None or len(splits) == 0:
                    continue
                s = splits.copy()
                s.index = pd.to_datetime(s.index).tz_localize(None)
                mask = (s.index >= start_ts) & (s.index <= end_ts)
                s = s.loc[mask]
                for dt, ratio in s.items():
                    r = float(ratio)
                    if r <= 0 or abs(r - 1.0) < 1e-9:
                        continue
                    rows.append(
                        {
                            "date": pd.Timestamp(dt).normalize(),
                            "ticker": nt,
                            "ratio": r,
                            "source": "yfinance",
                        }
                    )
            except Exception:
                continue
        if not rows:
            return pd.DataFrame(columns=["date", "ticker", "ratio"])
        return pd.DataFrame(rows)


def get_provider(name: ProviderName = "demo") -> DataProvider:
    if name == "brapi":
        from src.data.providers_brapi import BrapiDataProvider

        return BrapiDataProvider()
    if name == "yfinance":
        return YFinanceDataProvider()
    return DemoDataProvider()
