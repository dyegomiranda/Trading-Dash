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
) -> list[str]:
    """Retorna universo de tickers (sem .SA).

    mode:
      - full: lista ampla B3_UNIVERSE
      - core: B3_CORE_SCAN (líquidos, scan rápido)
    """
    from src.config import B3_CORE_SCAN

    items = list(B3_CORE_SCAN if mode == "core" else B3_UNIVERSE)
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

        out = active_universe(out)
    return out
