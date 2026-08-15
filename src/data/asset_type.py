"""Detecção de tipo de ativo B3 (ação vs FII) e retenção de IR simplificada.

Ajusta a tributação dos dividendos creditados no paper:

- **Ações**: dividendos são isentos de IR na fonte no Brasil.
- **JCP** (Juros sobre Capital Próprio): retido 15% na fonte.
  A fonte (Yahoo) não separa JCP de dividendo de forma confiável; por isso o
  tratamento é **opcional/estimado**: quem quiser modelar JCP informa a fração
  ``jcp_share`` do provento e a taxa efetiva vira ``jcp_ir_rate * jcp_share``.
- **FII**: rendimentos distribuídos são **isentos de IR na fonte** para PF.

O sufixo ``11`` NÃO basta: units (TAEE11, SANB11, KLBN11…) são ações.
Classificamos FII por cadastro/nome, lista conhecida, ou ``*11`` fora do
universo de ações da tese.
"""

from __future__ import annotations

import re

# FII comuns (não estão no universo de ações da tese).
_KNOWN_FII = {
    "MXRF11",
    "KNRI11",
    "HGLG11",
    "XPML11",
    "HGRE11",
    "VISC11",
    "XPLG11",
    "BTLG11",
    "KNCR11",
    "HGBS11",
    "IRDM11",
    "CPTS11",
    "MALL11",
    "HSML11",
    "PVBI11",
    "RECR11",
    "VGIR11",
    "KNIP11",
    "BCFF11",
}

_RE_UNIT_OR_FII = re.compile(r"^[A-Z]{4}11$")


def asset_kind(ticker: str) -> str:
    """Retorna 'fii' | 'acao'."""
    t = ticker.upper().strip()
    if t.endswith(".SA"):
        t = t[:-3]
    name = ""
    quote_type = ""
    try:
        from src.data.reference import get_ticker_meta

        meta = get_ticker_meta(t)
        name = str(meta.get("name") or "").upper()
        quote_type = str(meta.get("quote_type") or "").upper()
    except Exception:
        pass

    if "FII" in name or "FUNDO IMOB" in name or quote_type in {"REIT", "FII"}:
        return "fii"
    if t in _KNOWN_FII:
        return "fii"

    # Units e papéis do universo da tese são ação (SANB11, TAEE11, …).
    try:
        from src.config import B3_CORE_SCAN, B3_UNIVERSE

        if t in B3_UNIVERSE or t in B3_CORE_SCAN:
            return "acao"
    except Exception:
        pass

    if _RE_UNIT_OR_FII.match(t) and quote_type not in {"EQUITY", "ETF"}:
        return "fii"
    return "acao"


def is_fii(ticker: str) -> bool:
    return asset_kind(ticker) == "fii"


def dividend_tax_rate(
    ticker: str,
    *,
    jcp_ir_rate: float = 0.15,
    jcp_share: float = 0.0,
) -> float:
    """Taxa de retenção aplicável ao provento (0 = isento).

    - Ação: ``jcp_ir_rate * jcp_share`` (default 0 = tudo tratado como dividendo isento).
    - FII: 0 (renda isenta de IR na fonte).
    """
    if is_fii(ticker):
        return 0.0
    return jcp_ir_rate * max(0.0, min(jcp_share, 1.0))