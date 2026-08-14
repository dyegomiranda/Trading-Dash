"""Tese Quality Dividend — filtros e score composto."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from src.config import (
    CORE_SECTORS,
    SCORE_WEIGHTS,
    THESIS_ID,
    THESIS_VERSION,
    Settings,
    get_settings,
)
from src.data.quality import enrich_fundamentals_quality, row_completeness

# Colunas produzidas pelo motor (nunca devem ser entrada de rescore)
_SCORE_OUTPUT_COLS = (
    "score_quality",
    "score_dividends",
    "score_financial_health",
    "score_valuation",
    "score_total",
    "bucket",
    "rank",
    "rank_filtered",
    "reject_reason",
    "target_weight",
)


@dataclass
class ScoreResult:
    scored: pd.DataFrame
    filtered: pd.DataFrame
    rejected: pd.DataFrame
    meta: dict[str, Any]


def _clip01(x: float) -> float:
    return float(np.clip(x, 0.0, 1.0))


def _unwrap(val: Any) -> Any:
    """Se o valor veio de coluna duplicada (Series), pega o último."""
    if isinstance(val, pd.Series):
        if val.empty:
            return None
        return val.iloc[-1]
    return val


def _safe(val: Any, default: float | None = None) -> float | None:
    val = _unwrap(val)
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return default
    try:
        f = float(val)
        if np.isnan(f) or np.isinf(f):
            return default
        return f
    except (TypeError, ValueError):
        return default


def _row_get(row: pd.Series, key: str, default: Any = None) -> Any:
    if key not in row.index:
        return default
    return _unwrap(row[key])


def _unique_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Garante nomes de coluna únicos (mantém a última ocorrência)."""
    if df is None or df.empty:
        return df.copy() if df is not None else pd.DataFrame()
    out = df.copy()
    if out.columns.duplicated().any():
        out = out.loc[:, ~out.columns.duplicated(keep="last")].copy()
    return out


def _strip_score_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Remove qualquer coluna de score/meta gerada, inclusive duplicadas."""
    out = _unique_columns(df)
    to_drop = [
        c
        for c in out.columns
        if c in _SCORE_OUTPUT_COLS or str(c).startswith("score_")
    ]
    if to_drop:
        out = out.drop(columns=to_drop)
    # drop por nome pode deixar duplicatas de outros nomes; limpa de novo
    return _unique_columns(out)


def _series(df: pd.DataFrame, col: str) -> pd.Series:
    """Acessa uma coluna com segurança mesmo se o nome estiver duplicado."""
    if col not in df.columns:
        raise KeyError(col)
    block = df.loc[:, df.columns == col]
    if isinstance(block, pd.DataFrame):
        if block.shape[1] == 1:
            return block.iloc[:, 0]
        return block.iloc[:, -1]
    return block


def score_quality(row: pd.Series) -> float:
    """0–100: ROE/ROIC, margens, FCF."""
    roe = _safe(_row_get(row, "roe"))
    roic = _safe(_row_get(row, "roic"), roe)
    net_margin = _safe(_row_get(row, "net_margin"))
    ebitda_m = _safe(_row_get(row, "ebitda_margin"))
    fcf_pos = _row_get(row, "fcf_positive")

    parts = []
    if roe is not None:
        parts.append(_clip01((roe - 0.05) / 0.25) * 100)
    if roic is not None:
        parts.append(_clip01((roic - 0.05) / 0.22) * 100)
    if net_margin is not None:
        parts.append(_clip01(net_margin / 0.25) * 100)
    if ebitda_m is not None:
        parts.append(_clip01(ebitda_m / 0.35) * 100)
    if fcf_pos is True:
        parts.append(80.0)
    elif fcf_pos is False:
        parts.append(25.0)

    return float(np.mean(parts)) if parts else 50.0


def score_dividends(row: pd.Series, settings: Settings) -> float:
    """0–100: DY sustentável, payout, histórico. Penaliza armadilha de yield alto."""
    dy = _safe(_row_get(row, "dividend_yield"))
    payout = _safe(_row_get(row, "payout"))
    div_cagr = _safe(_row_get(row, "dividend_cagr_5y"))
    years = _safe(_row_get(row, "years_paying_dividend"))
    fcf_pos = _row_get(row, "fcf_positive")
    debt = _safe(_row_get(row, "net_debt_ebitda"))

    parts = []
    if dy is not None:
        if dy < settings.preferred_dy_min:
            parts.append(_clip01(dy / settings.preferred_dy_min) * 55)
        elif dy <= settings.preferred_dy_max:
            mid = 0.065
            dist = abs(dy - mid) / 0.05
            parts.append(100 * (1 - _clip01(dist) * 0.25))
        else:
            # Acima da faixa preferida: cai rápido (tese = renda sustentável, não o maior DY)
            parts.append(max(12.0, 65 - (dy - settings.preferred_dy_max) * 350))
    if payout is not None:
        if settings.min_payout <= payout <= settings.max_payout:
            parts.append(90.0)
        elif payout < settings.min_payout:
            parts.append(50.0)
        else:
            parts.append(max(10.0, 80 - (payout - settings.max_payout) * 150))
    if div_cagr is not None:
        parts.append(_clip01((div_cagr + 0.05) / 0.20) * 100)
    if years is not None:
        parts.append(_clip01(years / 10.0) * 100)

    base = float(np.mean(parts)) if parts else 45.0

    # Armadilha de yield: DY alto + sinais fracos de sustentabilidade
    trap = float(getattr(settings, "high_yield_trap", 0.14) or 0.14)
    if dy is not None and dy >= trap:
        penalty = 18.0
        if payout is not None and payout > settings.max_payout:
            penalty += 12.0
        if fcf_pos is False:
            penalty += 12.0
        if debt is not None and debt > settings.max_net_debt_ebitda:
            penalty += 10.0
        base = max(5.0, base - penalty)

    return base


def score_financial_health(row: pd.Series, settings: Settings) -> float:
    debt = _safe(_row_get(row, "net_debt_ebitda"))
    de = _safe(_row_get(row, "debt_equity"))
    cr = _safe(_row_get(row, "current_ratio"))
    ic = _safe(_row_get(row, "interest_coverage"))
    fcf_y = _safe(_row_get(row, "fcf_yield"))

    parts = []
    if debt is not None:
        if debt <= 0:
            parts.append(100.0)
        else:
            parts.append(_clip01(1 - debt / (settings.max_net_debt_ebitda + 1.5)) * 100)
    if de is not None:
        parts.append(_clip01(1 - de / 3.0) * 100)
    if cr is not None:
        parts.append(_clip01(cr / 2.0) * 100)
    if ic is not None:
        parts.append(_clip01(ic / 8.0) * 100)
    if fcf_y is not None:
        parts.append(_clip01((fcf_y + 0.02) / 0.12) * 100)

    return float(np.mean(parts)) if parts else 50.0


def score_valuation(row: pd.Series) -> float:
    pe = _safe(_row_get(row, "pe"))
    pb = _safe(_row_get(row, "pb"))
    ev = _safe(_row_get(row, "ev_ebitda"))
    fcf_y = _safe(_row_get(row, "fcf_yield"))
    peg = _safe(_row_get(row, "peg"))

    parts = []
    if pe is not None and pe > 0:
        if pe < 6:
            parts.append(75.0)
        elif pe <= 16:
            parts.append(100 - (pe - 6) * 4)
        else:
            parts.append(max(10.0, 60 - (pe - 16) * 3))
    if pb is not None and pb > 0:
        parts.append(_clip01(1 - (pb - 0.8) / 3.5) * 100)
    if ev is not None and ev > 0:
        if ev <= 8:
            parts.append(90.0)
        elif ev <= 14:
            parts.append(70.0)
        else:
            parts.append(max(15.0, 55 - (ev - 14) * 4))
    if fcf_y is not None:
        parts.append(_clip01(fcf_y / 0.10) * 100)
    if peg is not None and peg > 0:
        parts.append(_clip01(1.5 / max(peg, 0.3)) * 80)

    return float(np.mean(parts)) if parts else 50.0


def composite_score(row: pd.Series, settings: Settings | None = None) -> dict[str, float]:
    settings = settings or get_settings()
    q = score_quality(row)
    d = score_dividends(row, settings)
    h = score_financial_health(row, settings)
    v = score_valuation(row)
    total = (
        q * SCORE_WEIGHTS["quality"]
        + d * SCORE_WEIGHTS["dividends"]
        + h * SCORE_WEIGHTS["financial_health"]
        + v * SCORE_WEIGHTS["valuation"]
    )
    # Dados muito incompletos → nota menos confiante (não inventa qualidade)
    completeness = row_completeness(row)
    if completeness < 0.45:
        total *= 0.75 + 0.25 * (completeness / 0.45)
    elif completeness < 0.65:
        total *= 0.88 + 0.12 * ((completeness - 0.45) / 0.20)

    # Sem preço válido não deve aparecer como “ótima sugestão”
    price = _safe(_row_get(row, "price"))
    if price is None or price <= 0:
        total = min(total, 40.0)

    return {
        "score_quality": round(q, 2),
        "score_dividends": round(d, 2),
        "score_financial_health": round(h, 2),
        "score_valuation": round(v, 2),
        "score_total": round(float(total), 2),
        "data_completeness": round(completeness * 100, 1),
    }


def classify_bucket(row: pd.Series) -> str:
    sector = str(_row_get(row, "sector") or "")
    if sector in CORE_SECTORS:
        return "core"
    if _safe(_row_get(row, "score_quality"), 0) >= 70 and _safe(
        _row_get(row, "score_dividends"), 0
    ) >= 65:
        return "core"
    return "satellite"


def apply_filters(
    df: pd.DataFrame,
    settings: Settings | None = None,
    min_score: float | None = None,
    require_dividend: bool = True,
    strict: bool = False,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Filtra universo amplo. Retorna (aprovados, rejeitados com motivo)."""
    settings = settings or get_settings()
    min_score = settings.rebalance_min_score if min_score is None else min_score

    if df is None or df.empty:
        empty = df.copy() if df is not None else pd.DataFrame()
        return empty, empty.copy()

    work = _unique_columns(df)
    reasons: list[str] = []

    for _, row in work.iterrows():
        why: list[str] = []
        dy = _safe(_row_get(row, "dividend_yield"))
        roe = _safe(_row_get(row, "roe"))
        debt = _safe(_row_get(row, "net_debt_ebitda"))
        payout = _safe(_row_get(row, "payout"))
        score = _safe(_row_get(row, "score_total"), 0) or 0
        price = _safe(_row_get(row, "price"))

        if price is not None and price <= 0:
            why.append("sem preço")
        if require_dividend and (dy is None or dy <= 0):
            why.append("sem dividendo")
        if strict and roe is not None and roe < settings.min_roe:
            why.append(f"ROE<{settings.min_roe:.0%}")
        if strict and debt is not None and debt > settings.max_net_debt_ebitda:
            why.append("alavancagem alta")
        if strict and payout is not None and payout > settings.max_payout:
            why.append("payout alto")
        if score < min_score:
            why.append(f"score<{min_score}")
        # Armadilha de yield no filtro rigoroso
        trap = float(getattr(settings, "high_yield_trap", 0.14) or 0.14)
        if strict and dy is not None and dy >= trap:
            if payout is not None and payout > settings.max_payout:
                why.append("possível armadilha de dividendo alto")
        reasons.append("; ".join(why) if why else "")

    work = work.copy()
    work["reject_reason"] = reasons
    rejected = work[work["reject_reason"] != ""].copy()
    approved = work[work["reject_reason"] == ""].copy()
    return approved, rejected


def score_universe(
    fundamentals: pd.DataFrame,
    settings: Settings | None = None,
    min_score: float | None = None,
    strict_filters: bool = False,
) -> ScoreResult:
    settings = settings or get_settings()
    if fundamentals is None or fundamentals.empty:
        empty = fundamentals.copy() if fundamentals is not None else pd.DataFrame()
        return ScoreResult(empty, empty.copy(), empty.copy(), {"count": 0})

    # Base limpa: sem scores antigos e sem colunas duplicadas
    base = _strip_score_columns(fundamentals).reset_index(drop=True)

    score_dicts = [composite_score(row, settings) for _, row in base.iterrows()]
    score_df = pd.DataFrame(score_dicts)
    # Atribuição explícita (evita pd.concat com nomes repetidos)
    df = base.copy()
    for col in score_df.columns:
        df[col] = score_df[col].to_numpy()

    df["bucket"] = [classify_bucket(row) for _, row in df.iterrows()]
    df = df.sort_values(by="score_total", ascending=False, kind="mergesort").reset_index(
        drop=True
    )
    df["rank"] = np.arange(1, len(df) + 1)

    filtered, rejected = apply_filters(
        df, settings=settings, min_score=min_score, strict=strict_filters
    )
    filtered = _unique_columns(filtered)
    if not filtered.empty and "score_total" in filtered.columns:
        filtered = filtered.sort_values(
            by="score_total", ascending=False, kind="mergesort"
        ).reset_index(drop=True)
        filtered["rank_filtered"] = np.arange(1, len(filtered) + 1)

    df = _unique_columns(df)
    rejected = _unique_columns(rejected)

    df = enrich_fundamentals_quality(df)
    if not filtered.empty:
        filtered = enrich_fundamentals_quality(filtered)

    return ScoreResult(
        scored=df,
        filtered=filtered,
        rejected=rejected,
        meta={
            "universe_size": len(df),
            "filtered_size": len(filtered),
            "rejected_size": len(rejected),
            "weights": SCORE_WEIGHTS,
            "min_score": min_score
            if min_score is not None
            else settings.rebalance_min_score,
            "thesis_id": THESIS_ID,
            "thesis_version": THESIS_VERSION,
        },
    )


def recommend_weights(
    ranked: pd.DataFrame,
    top_n: int = 15,
    core_weight: float = 0.70,
    satellite_weight: float = 0.30,
    max_position_pct: float = 0.10,
    max_sector_pct: float | None = None,
) -> pd.DataFrame:
    """Distribui pesos core/satélite entre top N, com teto por ação e por setor.

    Mantém a montagem automática da tese amigável, mas evita concentração excessiva
    (mais realista e mais segura para iniciantes).
    """
    if ranked is None or ranked.empty:
        return ranked.copy() if ranked is not None else pd.DataFrame()

    settings = get_settings()
    if max_sector_pct is None:
        max_sector_pct = float(getattr(settings, "max_sector_pct", 0.30) or 0.30)

    # Prefere linhas com preço e dados melhores quando empata score
    work = _unique_columns(ranked).copy()
    if "price" in work.columns:
        prices = pd.to_numeric(work["price"], errors="coerce")
        work = work[prices.notna() & (prices > 0)]
    if work.empty:
        work = _unique_columns(ranked).copy()

    if "score_total" in work.columns:
        work = work.sort_values(by="score_total", ascending=False, kind="mergesort")
    # Evita muitas do mesmo setor no top (diversificação na seleção)
    if "sector" in work.columns and max_sector_pct > 0:
        max_per_sector = max(2, int(np.ceil(top_n * max_sector_pct * 1.5)))
        selected_idx: list[int] = []
        sector_count: dict[str, int] = {}
        for idx, row in work.iterrows():
            sec = str(row.get("sector") or "Outros")
            if sector_count.get(sec, 0) >= max_per_sector:
                continue
            selected_idx.append(idx)
            sector_count[sec] = sector_count.get(sec, 0) + 1
            if len(selected_idx) >= top_n:
                break
        if selected_idx:
            picks = work.loc[selected_idx].copy()
        else:
            picks = work.head(top_n).copy()
    else:
        picks = work.head(top_n).copy()

    if "bucket" not in picks.columns:
        picks["bucket"] = "satellite"
    if "score_total" not in picks.columns:
        picks["score_total"] = 50.0
    if "ticker" not in picks.columns:
        raise ValueError("DataFrame de ranking precisa da coluna 'ticker'.")

    bucket = _series(picks, "bucket")
    score_total = pd.to_numeric(_series(picks, "score_total"), errors="coerce").fillna(50.0)
    ticker = _series(picks, "ticker").astype(str)

    core_mask = bucket.eq("core")
    sat_mask = ~core_mask

    cw, sw = core_weight, satellite_weight
    if not core_mask.any() and sat_mask.any():
        cw, sw = 0.0, 1.0
    elif core_mask.any() and not sat_mask.any():
        cw, sw = 1.0, 0.0

    weights: dict[str, float] = {}
    if core_mask.any() and cw > 0:
        raw = score_total[core_mask].clip(lower=1)
        w = (raw / raw.sum()) * cw
        for t, val in zip(ticker[core_mask], w):
            weights[str(t)] = float(val)
    if sat_mask.any() and sw > 0:
        raw = score_total[sat_mask].clip(lower=1)
        w = (raw / raw.sum()) * sw
        for t, val in zip(ticker[sat_mask], w):
            weights[str(t)] = float(val)

    picks = picks.copy()
    picks["target_weight"] = ticker.map(weights).fillna(0.0).astype(float)

    # Itera: teto por ação + teto por setor + renormaliza para baixo se preciso
    for _ in range(12):
        picks["target_weight"] = picks["target_weight"].clip(lower=0.0, upper=max_position_pct)
        if "sector" in picks.columns and max_sector_pct > 0 and len(picks) > 1:
            sector_key = picks["sector"].fillna("Outros").astype(str)
            sector_sums = picks.groupby(sector_key)["target_weight"].transform("sum")
            over = sector_sums > max_sector_pct + 1e-9
            if over.any():
                factor = (max_sector_pct / sector_sums).clip(upper=1.0)
                picks.loc[over, "target_weight"] = (
                    picks.loc[over, "target_weight"] * factor[over]
                )
        total = float(picks["target_weight"].sum())
        if total <= 0:
            break
        # Só reescala para baixo se passou de 100% — residual vira caixa (mais seguro)
        if total > 1.0 + 1e-9:
            picks["target_weight"] = picks["target_weight"] / total
            continue
        # Dentro do orçamento e caps ok?
        if float(picks["target_weight"].max()) <= max_position_pct + 1e-9:
            if "sector" not in picks.columns or max_sector_pct <= 0:
                break
            sec_max = float(
                picks.groupby(picks["sector"].fillna("Outros").astype(str))[
                    "target_weight"
                ]
                .sum()
                .max()
            )
            if sec_max <= max_sector_pct + 1e-9:
                break
        else:
            # reescala se alguma posição estourou por FP
            picks["target_weight"] = picks["target_weight"].clip(upper=max_position_pct)

    picks["target_weight"] = picks["target_weight"].clip(lower=0.0, upper=max_position_pct)
    total = float(picks["target_weight"].sum())
    if total > 1.0:
        picks["target_weight"] = picks["target_weight"] / total
        picks["target_weight"] = picks["target_weight"].clip(upper=max_position_pct)
    return _unique_columns(picks)
