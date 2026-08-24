"""F-score de Piotroski reduzido, a partir das contas CVM disponíveis.

Nove sinais clássicos; os que faltarem dado são pulados (não inventamos 0).
Usado como *veto* no ensaio: se houver sinais suficientes e a nota for baixa,
o papel não entra. Não substitui a tese Quality Dividend.
"""

from __future__ import annotations

from typing import Any

import pandas as pd


def _num(row: pd.Series | dict[str, Any], key: str) -> float | None:
    if row is None:
        return None
    try:
        val = row[key] if isinstance(row, dict) else row.get(key)
    except Exception:
        return None
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    try:
        f = float(val)
    except (TypeError, ValueError):
        return None
    if pd.isna(f):
        return None
    return f


def _boolish(row: pd.Series | dict[str, Any], key: str) -> bool | None:
    if row is None:
        return None
    try:
        val = row[key] if isinstance(row, dict) else row.get(key)
    except Exception:
        return None
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    if isinstance(val, str) and val.strip().lower() in {"", "nan", "none"}:
        return None
    return bool(val)


def piotroski_signals(
    curr: pd.Series | dict[str, Any],
    prev: pd.Series | dict[str, Any] | None = None,
) -> dict[str, bool | None]:
    """Nove flags (True/False/None). None = sem dado para aquele sinal."""
    roa = _num(curr, "roa")
    if roa is None:
        roa = _num(curr, "roe")
    cfo = _num(curr, "cfo")
    fcf_pos = _boolish(curr, "fcf_positive")
    lucro = _num(curr, "lucro")
    debt = _num(curr, "debt_equity")
    cr = _num(curr, "current_ratio")
    nm = _num(curr, "net_margin")
    rec = _num(curr, "receita")
    ativo = _num(curr, "ativo")
    turnover = (rec / ativo) if rec is not None and ativo and ativo != 0 else None

    prev_roa = _num(prev, "roa") if prev is not None else None
    if prev_roa is None and prev is not None:
        prev_roa = _num(prev, "roe")
    prev_debt = _num(prev, "debt_equity") if prev is not None else None
    prev_cr = _num(prev, "current_ratio") if prev is not None else None
    prev_nm = _num(prev, "net_margin") if prev is not None else None
    prev_rec = _num(prev, "receita") if prev is not None else None
    prev_ativo = _num(prev, "ativo") if prev is not None else None
    prev_to = (
        (prev_rec / prev_ativo)
        if prev_rec is not None and prev_ativo and prev_ativo != 0
        else None
    )

    cfo_pos = (cfo > 0) if cfo is not None else fcf_pos
    accrual = None
    if cfo is not None and lucro is not None:
        accrual = cfo > lucro

    return {
        "roa_positive": (roa > 0) if roa is not None else None,
        "cfo_positive": cfo_pos,
        "roa_up": (roa > prev_roa) if roa is not None and prev_roa is not None else None,
        "accrual_ok": accrual,
        "leverage_down": (debt < prev_debt) if debt is not None and prev_debt is not None else None,
        "current_up": (cr > prev_cr) if cr is not None and prev_cr is not None else None,
        "margin_up": (nm > prev_nm) if nm is not None and prev_nm is not None else None,
        "turnover_up": (
            (turnover > prev_to) if turnover is not None and prev_to is not None else None
        ),
        # Emissão de ações: a DMPL livre não traz isso com confiança — omitido.
    }


def f_score(
    curr: pd.Series | dict[str, Any],
    prev: pd.Series | dict[str, Any] | None = None,
) -> tuple[int | None, int, int]:
    """Retorna (pontos, sinais_disponíveis, sinais_positivos)."""
    flags = piotroski_signals(curr, prev)
    known = [v for v in flags.values() if v is not None]
    if not known:
        return None, 0, 0
    n_ok = sum(1 for v in known if v)
    return n_ok, len(known), n_ok


def passes_veto(
    curr: pd.Series | dict[str, Any],
    prev: pd.Series | dict[str, Any] | None,
    *,
    minimum: int = 5,
    min_signals: int = 4,
) -> bool:
    """False = vetar. Sem sinais suficientes, não veta (não inventa rejeição)."""
    score, n_known, _ = f_score(curr, prev)
    if score is None or n_known < min_signals:
        return True
    return int(score) >= int(minimum)
