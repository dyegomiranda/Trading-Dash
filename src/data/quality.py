"""Qualidade e cobertura dos dados — para o iniciante confiar no que vê."""

from __future__ import annotations

from typing import Any

import pandas as pd

from src.utils import utcnow

# Campos importantes para a tese (quanto mais preenchidos, melhor a nota de confiança)
_KEY_FIELDS = (
    "price",
    "dividend_yield",
    "roe",
    "payout",
    "net_debt_ebitda",
    "pe",
    "sector",
    "name",
)


def _has_value(val: Any) -> bool:
    if val is None:
        return False
    try:
        if pd.isna(val):
            return False
    except (TypeError, ValueError):
        pass
    if isinstance(val, str) and not val.strip():
        return False
    return True


def _safe_float(val: Any) -> float | None:
    if not _has_value(val):
        return None
    try:
        f = float(val)
        if pd.isna(f) or f != f:  # NaN
            return None
        return f
    except (TypeError, ValueError):
        return None


def row_completeness(row: pd.Series | dict[str, Any], fields: tuple[str, ...] = _KEY_FIELDS) -> float:
    """0–1: fração de campos-chave preenchidos."""
    if row is None:
        return 0.0
    ok = 0
    for f in fields:
        try:
            val = row[f] if not isinstance(row, dict) else row.get(f)
        except Exception:
            val = None
        if _has_value(val):
            ok += 1
    return ok / len(fields) if fields else 0.0


def assess_row_quality(row: pd.Series | dict[str, Any]) -> dict[str, Any]:
    """Avalia uma linha de fundamentals para exibição amigável."""
    if isinstance(row, pd.Series):
        data = row.to_dict()
    else:
        data = dict(row or {})

    source = str(data.get("source") or data.get("data_quality") or "unknown")
    dq = str(data.get("data_quality") or "")
    is_synthetic = "synthetic" in dq.lower() or "demo" in source.lower()
    completeness = row_completeness(data)
    price = _safe_float(data.get("price"))
    dy = _safe_float(data.get("dividend_yield"))
    payout = _safe_float(data.get("payout"))
    debt = _safe_float(data.get("net_debt_ebitda"))

    flags: list[str] = []
    if is_synthetic:
        flags.append("números de treino (não use para decidir dinheiro real)")
    if price is None or price <= 0:
        flags.append("sem preço válido")
    if dy is None:
        flags.append("sem dado de dividendo")
    elif dy > 0.18:
        flags.append("dividendo % muito alto — conferir se não é armadilha")
    if payout is not None and payout > 1.0:
        flags.append("payout acima de 100% do lucro")
    if debt is not None and debt > 4.0:
        flags.append("endividamento elevado")
    if completeness < 0.5:
        flags.append("muitos dados faltando")

    if is_synthetic:
        level = "treino"
        label = "Modo treino"
    elif completeness >= 0.75 and price and price > 0 and dy is not None:
        level = "boa"
        label = "Dados ok"
    elif completeness >= 0.45 and price and price > 0:
        level = "parcial"
        label = "Dados parciais"
    else:
        level = "fraca"
        label = "Dados fracos"

    return {
        "quality_level": level,
        "quality_label": label,
        "completeness": completeness,
        "flags": flags,
        "is_synthetic": is_synthetic,
        "source": source,
    }


def enrich_fundamentals_quality(df: pd.DataFrame) -> pd.DataFrame:
    """Adiciona colunas de qualidade amigáveis ao DataFrame de fundamentals/score."""
    if df is None or df.empty:
        return df if df is not None else pd.DataFrame()
    out = df.copy()
    levels, labels, comps, flag_txt = [], [], [], []
    for _, row in out.iterrows():
        q = assess_row_quality(row)
        levels.append(q["quality_level"])
        labels.append(q["quality_label"])
        comps.append(round(q["completeness"] * 100, 0))
        flag_txt.append("; ".join(q["flags"]) if q["flags"] else "")
    out["quality_level"] = levels
    out["quality_label"] = labels
    out["data_completeness_pct"] = comps
    out["quality_flags"] = flag_txt
    return out


def coverage_summary(df: pd.DataFrame) -> dict[str, Any]:
    """Resumo de cobertura para banner de confiança no ranking."""
    if df is None or df.empty:
        return {
            "n": 0,
            "with_price": 0,
            "with_dy": 0,
            "with_roe": 0,
            "good_quality": 0,
            "partial_quality": 0,
            "weak_quality": 0,
            "synthetic": 0,
            "price_coverage": 0.0,
            "dy_coverage": 0.0,
            "avg_completeness": 0.0,
            "trust_label": "Sem dados",
            "trust_level": "fraca",
            "as_of": utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        }

    work = df
    if "quality_level" not in work.columns:
        work = enrich_fundamentals_quality(work)

    n = len(work)
    with_price = int(
        pd.to_numeric(work.get("price"), errors="coerce").fillna(0).gt(0).sum()
    )
    with_dy = int(
        pd.to_numeric(work.get("dividend_yield"), errors="coerce").fillna(-1).ge(0).sum()
        if "dividend_yield" in work.columns
        else 0
    )
    # dy ge 0 counts zeros; better: notna
    if "dividend_yield" in work.columns:
        with_dy = int(pd.to_numeric(work["dividend_yield"], errors="coerce").notna().sum())
    with_roe = (
        int(pd.to_numeric(work["roe"], errors="coerce").notna().sum())
        if "roe" in work.columns
        else 0
    )
    good = int((work["quality_level"] == "boa").sum()) if "quality_level" in work.columns else 0
    partial = int((work["quality_level"] == "parcial").sum()) if "quality_level" in work.columns else 0
    weak = int((work["quality_level"] == "fraca").sum()) if "quality_level" in work.columns else 0
    synthetic = int((work["quality_level"] == "treino").sum()) if "quality_level" in work.columns else 0
    avg_comp = (
        float(work["data_completeness_pct"].mean()) / 100.0
        if "data_completeness_pct" in work.columns
        else 0.0
    )

    price_cov = with_price / n if n else 0.0
    dy_cov = with_dy / n if n else 0.0

    if synthetic == n:
        trust_level, trust_label = "treino", "Modo treino — números ilustrativos"
    elif price_cov >= 0.8 and dy_cov >= 0.6 and avg_comp >= 0.55:
        trust_level, trust_label = "boa", "Cobertura boa para estudar a tese"
    elif price_cov >= 0.5 and dy_cov >= 0.35:
        trust_level, trust_label = "parcial", "Cobertura parcial — confira alertas"
    else:
        trust_level, trust_label = "fraca", "Poucos dados sólidos — use com cautela"

    return {
        "n": n,
        "with_price": with_price,
        "with_dy": with_dy,
        "with_roe": with_roe,
        "good_quality": good,
        "partial_quality": partial,
        "weak_quality": weak,
        "synthetic": synthetic,
        "price_coverage": price_cov,
        "dy_coverage": dy_cov,
        "avg_completeness": avg_comp,
        "trust_label": trust_label,
        "trust_level": trust_level,
        "as_of": utcnow().strftime("%Y-%m-%d %H:%M UTC"),
    }
