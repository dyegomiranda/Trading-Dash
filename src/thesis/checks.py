"""Checagens verificáveis (CVM PIT + cadastro B3) — não é nota de convicção.

Três itens, cada um ok / aviso / sem dado. Fonte explícita. Não entra no score 0–100.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd

from src.config import CORE_SECTORS
from src.data.pit_loader import get_pit_origin, load_pit_fundamentals
from src.data.reference import (
    control_label,
    get_ticker_meta,
    listing_segment,
    tag_along_pct,
    translate_sector,
)
from src.data.universe import normalize_ticker

CheckStatus = Literal["ok", "warn", "unknown"]

_COMMODITY_SECTORS = {
    "Energy",
    "Basic Materials",
    "Oil & Gas Integrated",
    "Other Industrial Metals & Mining",
}


@dataclass(frozen=True)
class CheckItem:
    id: str
    title: str
    status: CheckStatus
    detail: str
    source: str


@dataclass(frozen=True)
class QualityChecks:
    ticker: str
    items: tuple[CheckItem, ...]

    @property
    def n_ok(self) -> int:
        return sum(1 for i in self.items if i.status == "ok")

    @property
    def n_known(self) -> int:
        return sum(1 for i in self.items if i.status != "unknown")


def _pit_source_caption() -> str:
    origin = get_pit_origin()
    if origin.startswith("cvm"):
        return "CVM DFP (ano-calendário, PIT)"
    return "semente PIT (não é DFP/ITR oficial)"


def _annual_series(ticker: str) -> pd.DataFrame:
    """Uma linha por ano-calendário (31/12), preferindo DFP quando houver ITR no mesmo ano."""
    t = normalize_ticker(ticker)
    snaps = load_pit_fundamentals()
    best: dict[int, dict] = {}
    for dt, df in snaps.items():
        ts = pd.Timestamp(dt)
        if ts.month != 12:
            continue
        if df is None or df.empty or "ticker" not in df.columns:
            continue
        sub = df[df["ticker"].astype(str) == t]
        if sub.empty:
            continue
        rec = sub.iloc[-1].to_dict()
        year = int(ts.year)
        prev = best.get(year)
        src = str(rec.get("source") or "")
        if prev is None or (src == "cvm_dfp" and str(prev.get("source") or "") != "cvm_dfp"):
            rec["_year"] = year
            best[year] = rec
    if not best:
        return pd.DataFrame()
    out = pd.DataFrame([best[y] for y in sorted(best)])
    return out


def _as_float(val: object) -> float | None:
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return None
    try:
        f = float(val)
    except (TypeError, ValueError):
        return None
    if np.isnan(f) or np.isinf(f):
        return None
    return f


def _lucro_caixa_item(ticker: str) -> CheckItem:
    src = _pit_source_caption()
    annual = _annual_series(ticker)
    if annual.empty or "lucro" not in annual.columns:
        return CheckItem(
            "lucro_caixa",
            "Lucro e caixa",
            "unknown",
            "Sem série anual de lucro na base point-in-time.",
            src,
        )
    lucros: list[tuple[int, float]] = []
    for rec in annual.to_dict(orient="records"):
        year = int(rec.get("_year") or 0)
        lucro = _as_float(rec.get("lucro"))
        if year and lucro is not None:
            lucros.append((year, lucro))
    if len(lucros) < 3:
        return CheckItem(
            "lucro_caixa",
            "Lucro e caixa",
            "unknown",
            f"Só {len(lucros)} ano(s) com lucro na CVM — pouco para falar em recorrência.",
            src,
        )
    lucros.sort()
    streak = 0
    for _year, lucro in reversed(lucros):
        if lucro > 0:
            streak += 1
        else:
            break

    last = annual.iloc[-1]
    fcf = _as_float(last.get("fcf"))
    ni = _as_float(last.get("lucro"))
    ratio = None
    if fcf is not None and ni is not None and ni > 0:
        ratio = fcf / ni

    parts: list[str] = []
    status: CheckStatus = "ok"
    if streak >= 5:
        parts.append(f"{streak} anos seguidos sem prejuízo (ano-calendário)")
    elif streak >= 1:
        parts.append(f"só {streak} ano(s) recente(s) no azul")
        status = "warn"
    else:
        parts.append("prejuízo no último ano-calendário da base")
        status = "warn"

    if ratio is None:
        parts.append("FCF/lucro indisponível no último DFP")
        if status == "ok":
            status = "warn"
    elif ratio >= 0.70:
        parts.append(f"FCF/lucro {ratio:.0%} (caixa acompanha o lucro)")
    elif ratio >= 0.30:
        parts.append(f"FCF/lucro {ratio:.0%} (conversão moderada)")
        if status == "ok":
            status = "warn"
    else:
        parts.append(f"FCF/lucro {ratio:.0%} (lucro pouco convertido em caixa)")
        status = "warn"

    if len(lucros) >= 4:
        vals = np.array([v for _, v in lucros], dtype=float)
        mean = float(vals.mean())
        if mean > 0:
            cv = float(vals.std(ddof=0) / mean)
            if cv > 0.80:
                parts.append(f"lucro oscila (CV {cv:.1f})")
                if status == "ok":
                    status = "warn"

    return CheckItem("lucro_caixa", "Lucro e caixa", status, " · ".join(parts), src)


def _setor_item(ticker: str) -> CheckItem:
    meta = get_ticker_meta(ticker)
    sector = str(meta.get("sector") or "").strip()
    label = translate_sector(sector) if sector else "—"
    if not sector or sector.lower() in {"unknown", "outros"}:
        return CheckItem(
            "setor",
            "Setor",
            "unknown",
            "Setor não cadastrado.",
            "cadastro B3",
        )
    if sector in CORE_SECTORS:
        return CheckItem(
            "setor",
            "Setor",
            "ok",
            f"{label} — demanda mais previsível (energia, bancos, saneamento, telecom, consumo básico).",
            "cadastro B3",
        )
    if sector in _COMMODITY_SECTORS:
        return CheckItem(
            "setor",
            "Setor",
            "warn",
            f"{label} — cíclico de commodity: o dividendo de pico não é renda estável.",
            "cadastro B3",
        )
    return CheckItem(
        "setor",
        "Setor",
        "warn",
        f"{label} — fora do núcleo defensivo da tese; não é falha, só outro perfil.",
        "cadastro B3",
    )


def _governanca_item(ticker: str) -> CheckItem:
    seg = listing_segment(ticker)
    tag = tag_along_pct(ticker)
    control = control_label(ticker)
    bits: list[str] = []
    if seg:
        bits.append(seg)
    if tag is not None:
        bits.append(f"tag along {tag:.0%}")
    if control:
        bits.append(control)
    if not bits:
        return CheckItem(
            "governanca",
            "Governança visível",
            "unknown",
            "Sem segmento (NM/N1/N2) no cadastro — não inventamos tag along.",
            "cadastro B3 (sufixo do nome)",
        )
    detail = " · ".join(bits)
    if control and control.startswith("estatal"):
        status: CheckStatus = "warn"
        detail += " — risco político; não é desconto automático no preço."
    elif seg in {"Novo Mercado", "Nível 2"}:
        status = "ok"
    else:
        status = "warn"
    return CheckItem(
        "governanca",
        "Governança visível",
        status,
        detail,
        "cadastro B3 (sufixo NM/N1/N2) + lista curada de controle",
    )


def build_quality_checks(ticker: str) -> QualityChecks:
    t = normalize_ticker(ticker)
    items = (_lucro_caixa_item(t), _setor_item(t), _governanca_item(t))
    return QualityChecks(ticker=t, items=items)
