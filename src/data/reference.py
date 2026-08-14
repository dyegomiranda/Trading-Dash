"""Cadastro de referência B3 (nome, setor, status, renomeações).

Fonte: `data/reference/b3_tickers.json` (gerado/atualizado via
`scripts/refresh_b3_metadata.py` + overrides manuais).

Regra: **nunca inventar setor/nome no demo** — usar este arquivo.
Números fundamentalistas no demo continuam sintéticos e NÃO servem para decisão real.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from src.config import DATA_DIR

REFERENCE_PATH = DATA_DIR / "reference" / "b3_tickers.json"


def _norm(ticker: str) -> str:
    t = ticker.strip().upper()
    return t[:-3] if t.endswith(".SA") else t

# Overrides manuais prioritários (renomeações / gaps conhecidos)
MANUAL_OVERRIDES: dict[str, dict[str, Any]] = {
    "AXIA3": {
        "name": "AXIA ENERGIA ON",
        "sector": "Utilities",
        "industry": "Utilities - Renewable",
        "status": "active",
        "notes": "ex-ELET3 (Eletrobras)",
    },
    "AXIA6": {
        "name": "AXIA ENERGIA PNB",
        "sector": "Utilities",
        "industry": "Utilities - Renewable",
        "status": "active",
        "notes": "ex-ELET6",
    },
    "ELET3": {
        "status": "delisted_or_renamed",
        "name": "ELETROBRAS ON (ticker antigo)",
        "sector": "Utilities",
        "industry": "Utilities - Renewable",
        "successor": "AXIA3",
        "notes": "Migrado para AXIA3",
    },
    "ELET6": {
        "status": "delisted_or_renamed",
        "name": "ELETROBRAS PNB (ticker antigo)",
        "sector": "Utilities",
        "industry": "Utilities - Renewable",
        "successor": "AXIA6",
        "notes": "Migrado para AXIA6",
    },
    "KEPL3": {
        "name": "KEPLER WEBER ON",
        "sector": "Industrials",
        "industry": "Farm & Heavy Construction Machinery",
        "status": "active",
    },
    "BMGB11": {
        "name": "BANCO BMG UNIT",
        "sector": "Financial Services",
        "industry": "Banks - Regional",
        "status": "active",
    },
    "JHSF3": {
        "name": "JHSF PARTICIPACOES ON",
        "sector": "Real Estate",
        "industry": "Real Estate - Development",
        "status": "active",
    },
    "LREN3": {
        "name": "LOJAS RENNER ON",
        "sector": "Consumer Cyclical",
        "industry": "Department Stores",
        "status": "active",
    },
    "BBDC4": {
        "name": "BRADESCO PN",
        "sector": "Financial Services",
        "industry": "Banks - Regional",
        "status": "active",
    },
    "BBDC3": {
        "name": "BRADESCO ON",
        "sector": "Financial Services",
        "industry": "Banks - Regional",
        "status": "active",
    },
    "TAEE11": {
        "name": "TAESA UNT",
        "sector": "Utilities",
        "industry": "Utilities - Regulated Electric",
        "status": "active",
    },
    "ITUB4": {
        "name": "ITAU UNIBANCO PN",
        "sector": "Financial Services",
        "industry": "Banks - Regional",
        "status": "active",
    },
    "WEGE3": {
        "name": "WEG ON",
        "sector": "Industrials",
        "industry": "Specialty Industrial Machinery",
        "status": "active",
    },
    "VALE3": {
        "name": "VALE ON",
        "sector": "Basic Materials",
        "industry": "Other Industrial Metals & Mining",
        "status": "active",
    },
    "PETR4": {
        "name": "PETROBRAS PN",
        "sector": "Energy",
        "industry": "Oil & Gas Integrated",
        "status": "active",
    },
}


@lru_cache(maxsize=1)
def load_ticker_reference() -> dict[str, dict[str, Any]]:
    """Carrega JSON + aplica overrides manuais (manual vence em campos definidos)."""
    data: dict[str, dict[str, Any]] = {}
    if REFERENCE_PATH.exists():
        try:
            payload = json.loads(REFERENCE_PATH.read_text(encoding="utf-8"))
            raw = payload.get("tickers") or {}
            for k, v in raw.items():
                data[_norm(k)] = dict(v)
        except Exception:
            data = {}
    for k, ov in MANUAL_OVERRIDES.items():
        t = _norm(k)
        base = data.get(t, {"ticker": t})
        base.update(ov)
        base["ticker"] = t
        data[t] = base
    return data


def get_ticker_meta(ticker: str) -> dict[str, Any]:
    t = _norm(ticker)
    ref = load_ticker_reference()
    if t in ref:
        return dict(ref[t])
    return {
        "ticker": t,
        "name": t,
        "sector": "Unknown",
        "industry": None,
        "status": "unknown",
        "source": "fallback",
    }


def resolve_successor(ticker: str) -> str:
    """Se o ticker foi renomeado, retorna o sucessor; senão o próprio."""
    meta = get_ticker_meta(ticker)
    succ = meta.get("successor")
    if succ and meta.get("status") == "delisted_or_renamed":
        return _norm(str(succ))
    return _norm(ticker)


def is_tradable(ticker: str) -> bool:
    meta = get_ticker_meta(ticker)
    status = meta.get("status") or "unknown"
    return status not in ("delisted_or_renamed",)


def active_universe(tickers: list[str]) -> list[str]:
    """Filtra delisted/renomeados e troca por sucessor quando houver."""
    out: list[str] = []
    seen: set[str] = set()
    for t in tickers:
        nt = _norm(t)
        meta = get_ticker_meta(nt)
        if meta.get("status") == "delisted_or_renamed":
            nt = resolve_successor(nt)
            meta = get_ticker_meta(nt)
        if meta.get("status") == "delisted_or_renamed":
            continue
        if nt not in seen:
            seen.add(nt)
            out.append(nt)
    return out
