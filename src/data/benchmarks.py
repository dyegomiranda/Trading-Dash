"""Séries de benchmark para comparação no backtest (Ibovespa + CDI)."""

from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime
from typing import Any
from urllib.request import Request, urlopen

import numpy as np
import pandas as pd

from src.config import CACHE_DIR, get_settings
from src.data.providers import DataProvider


def _cache_path(key: str):
    h = hashlib.sha1(key.encode()).hexdigest()[:24]
    return CACHE_DIR / f"bm_{h}.json"


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
    _cache_path(key).write_text(
        json.dumps({"ts": time.time(), "data": data}, default=str),
        encoding="utf-8",
    )


def fetch_ibovespa_close(
    start: str | datetime,
    end: str | datetime | None = None,
) -> pd.Series:
    """Preço de fechamento do Ibovespa (^BVSP) via yfinance."""
    start_s = pd.Timestamp(start).strftime("%Y-%m-%d")
    end_s = pd.Timestamp(end or datetime.utcnow()).strftime("%Y-%m-%d")
    cache_key = f"ibov:{start_s}:{end_s}"
    settings = get_settings()
    cached = _read_cache(cache_key, settings.cache_ttl_hours)
    if cached is not None:
        s = pd.Series(cached)
        s.index = pd.to_datetime(s.index)
        return s.sort_index()

    try:
        import yfinance as yf

        raw = yf.download(
            "^BVSP",
            start=start_s,
            end=end_s,
            auto_adjust=False,
            progress=False,
            threads=False,
        )
        if raw is None or raw.empty:
            return pd.Series(dtype=float)
        if isinstance(raw.columns, pd.MultiIndex):
            close = raw["Close"]
            if isinstance(close, pd.DataFrame):
                close = close.iloc[:, 0]
        else:
            close = raw["Close"] if "Close" in raw.columns else raw.iloc[:, 3]
        s = pd.Series(close.astype(float).values, index=pd.to_datetime(close.index))
        s = s.tz_localize(None) if s.index.tz is not None else s
        s = s.sort_index().dropna()
        s.index = s.index.normalize()
        _write_cache(cache_key, {str(k.date()): float(v) for k, v in s.items()})
        return s
    except Exception:
        return pd.Series(dtype=float)


def fetch_cdi_daily_factors(
    start: str | datetime,
    end: str | datetime | None = None,
) -> pd.Series:
    """Fatores diários de CDI (SGS BCB série 12 = CDI diário %).

    Retorna Series index=data, value=fator diário (1 + taxa/100).
    """
    start_ts = pd.Timestamp(start).normalize()
    end_ts = pd.Timestamp(end or datetime.utcnow()).normalize()
    cache_key = f"cdi:{start_ts.date()}:{end_ts.date()}"
    settings = get_settings()
    cached = _read_cache(cache_key, settings.cache_ttl_hours)
    if cached is not None:
        s = pd.Series(cached)
        s.index = pd.to_datetime(s.index)
        return s.sort_index()

    # BCB API: dataInicial/dataFinal dd/mm/yyyy
    url = (
        "https://api.bcb.gov.br/dados/serie/bcdata.sgs.12/dados"
        f"?formato=json&dataInicial={start_ts.strftime('%d/%m/%Y')}"
        f"&dataFinal={end_ts.strftime('%d/%m/%Y')}"
    )
    try:
        req = Request(url, headers={"User-Agent": "TradingDash/0.1"})
        with urlopen(req, timeout=20) as resp:
            rows = json.loads(resp.read().decode("utf-8"))
        dates = []
        factors = []
        for row in rows:
            # valor em % ao dia
            d = pd.to_datetime(row["data"], dayfirst=True).normalize()
            rate = float(str(row["valor"]).replace(",", "."))
            dates.append(d)
            factors.append(1.0 + rate / 100.0)
        s = pd.Series(factors, index=pd.DatetimeIndex(dates)).sort_index()
        _write_cache(cache_key, {str(k.date()): float(v) for k, v in s.items()})
        return s
    except Exception:
        return pd.Series(dtype=float)


def demo_ibovespa_like(
    index: pd.DatetimeIndex,
    seed: int = 7,
) -> pd.Series:
    """Série sintética tipo índice (modo treino)."""
    if len(index) == 0:
        return pd.Series(dtype=float)
    rng = np.random.default_rng(seed)
    dt = 1 / 252
    mu, vol = 0.10, 0.20
    shocks = rng.normal((mu - 0.5 * vol**2) * dt, vol * np.sqrt(dt), size=len(index))
    path = 100_000 * np.exp(np.cumsum(shocks))
    # ancora no capital inicial no primeiro dia
    path = path / path[0] * 100_000
    return pd.Series(path, index=index)


def demo_cdi_like(index: pd.DatetimeIndex, annual_rate: float = 0.12) -> pd.Series:
    """Acúmulo sintético tipo CDI (juros compostos diários)."""
    if len(index) == 0:
        return pd.Series(dtype=float)
    daily = (1 + annual_rate) ** (1 / 252) - 1
    levels = 100_000 * np.cumprod(np.full(len(index), 1 + daily))
    # começa em 100k no dia 0: shift so first = 100k
    levels = levels / levels[0] * 100_000
    return pd.Series(levels, index=index)


def build_benchmark_curves(
    equity_dates: pd.DatetimeIndex,
    initial_cash: float,
    provider: DataProvider,
    start: str,
    end: str,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Alinha benchmarks aos dias da carteira e normaliza para initial_cash.

    Returns
    -------
    curves : DataFrame com colunas date, portfolio (preenchido depois), ibovespa, cdi
    meta : métricas auxiliares / flags
    """
    dates = pd.DatetimeIndex(equity_dates).normalize().unique().sort_values()
    meta: dict[str, Any] = {
        "ibov_source": None,
        "cdi_source": None,
        "ibov_available": False,
        "cdi_available": False,
    }

    # --- Ibovespa ---
    if provider.name == "demo":
        ibov = demo_ibovespa_like(dates)
        meta["ibov_source"] = "demo"
        meta["ibov_available"] = len(ibov) > 0
    else:
        raw = fetch_ibovespa_close(start, end)
        if raw.empty:
            ibov = demo_ibovespa_like(dates)
            meta["ibov_source"] = "demo-fallback"
            meta["ibov_available"] = len(ibov) > 0
        else:
            raw = raw.reindex(dates).ffill().bfill()
            if raw.isna().all() or float(raw.iloc[0]) <= 0:
                ibov = demo_ibovespa_like(dates)
                meta["ibov_source"] = "demo-fallback"
            else:
                ibov = initial_cash * (raw / float(raw.iloc[0]))
                meta["ibov_source"] = "yfinance:^BVSP"
            meta["ibov_available"] = True

    # --- CDI ---
    if provider.name == "demo":
        cdi = demo_cdi_like(dates)
        meta["cdi_source"] = "demo"
        meta["cdi_available"] = len(cdi) > 0
    else:
        factors = fetch_cdi_daily_factors(start, end)
        if factors.empty:
            cdi = demo_cdi_like(dates)
            meta["cdi_source"] = "demo-fallback"
            meta["cdi_available"] = len(cdi) > 0
        else:
            # reindex trading days: ffill factors; missing days use 1.0
            f = factors.reindex(dates).fillna(1.0)
            # first day level = initial; then compound subsequent day factors
            levels = np.empty(len(dates))
            levels[0] = initial_cash
            for i in range(1, len(dates)):
                levels[i] = levels[i - 1] * float(f.iloc[i])
            cdi = pd.Series(levels, index=dates)
            meta["cdi_source"] = "BCB:SGS.12"
            meta["cdi_available"] = True

    # normaliza índices demo para initial_cash
    if len(ibov) and abs(float(ibov.iloc[0]) - initial_cash) > 1:
        ibov = initial_cash * (ibov / float(ibov.iloc[0]))
    if len(cdi) and abs(float(cdi.iloc[0]) - initial_cash) > 1:
        cdi = initial_cash * (cdi / float(cdi.iloc[0]))

    out = pd.DataFrame(
        {
            "date": dates,
            "ibovespa": ibov.reindex(dates).to_numpy() if len(ibov) else np.nan,
            "cdi": cdi.reindex(dates).to_numpy() if len(cdi) else np.nan,
        }
    )
    return out, meta
