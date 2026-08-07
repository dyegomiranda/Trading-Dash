"""Universo de tickers B3 e utilitários de normalização."""

from __future__ import annotations

from src.config import B3_UNIVERSE


def normalize_ticker(ticker: str) -> str:
    t = ticker.strip().upper()
    if t.endswith(".SA"):
        t = t[:-3]
    return t


def to_yf_symbol(ticker: str) -> str:
    t = normalize_ticker(ticker)
    if t.endswith("34") or t.endswith("35"):  # BDRs já no formato comum
        return f"{t}.SA"
    return f"{t}.SA"


def get_universe(extra: list[str] | None = None) -> list[str]:
    """Retorna universo amplo único (sem .SA)."""
    items = list(B3_UNIVERSE)
    if extra:
        items.extend(extra)
    seen: set[str] = set()
    out: list[str] = []
    for t in items:
        n = normalize_ticker(t)
        if n and n not in seen:
            seen.add(n)
            out.append(n)
    return out
