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


def get_universe(
    extra: list[str] | None = None,
    *,
    resolve_renames: bool = True,
    mode: str = "full",
    include_historical: bool = False,
) -> list[str]:
    """Retorna universo de tickers (sem .SA).

    mode:
      - full: lista ampla B3_UNIVERSE
      - core: B3_CORE_SCAN (líquidos, scan rápido)
    include_historical: soma tickers que saíram/renomearam (ensaio no passado).
    """
    from src.config import B3_CORE_SCAN, B3_HISTORICAL_EXTRA

    items = list(B3_CORE_SCAN if mode == "core" else B3_UNIVERSE)
    if include_historical:
        items.extend(B3_HISTORICAL_EXTRA)
    if extra:
        items.extend(extra)
    seen: set[str] = set()
    out: list[str] = []
    for t in items:
        n = normalize_ticker(t)
        if n and n not in seen:
            seen.add(n)
            out.append(n)
    if resolve_renames:
        from src.data.reference import active_universe

        live = active_universe(out)
        if include_historical:
            extras = [t for t in out if t not in live]
            out = live + extras
        else:
            out = live
    return out
