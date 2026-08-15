"""Narrativa da tese em português claro — "por que essa ação?".

Gera um texto curto (2–4 frases) explicando **em linguagem de iniciante** o
motivo de uma empresa ter entrado na lista. Não usa IA nem LLM: é um modelo
determinístico que olha os pilares do score (qualidade, dividendos, saúde,
preço) e os dados disponíveis, e monta frases com honestidade sobre o que
está (ou não) presente.

Regras:
- Nunca inventa dado. Se não há ROE/DY/dívida, diz "não temos esse dado".
- É isento: fala do que é forte e do que falta, sem parecer publicidade.
- As frases são curtas o suficiente para caber num card/expander na UI.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from src.thesis.scoring import _safe, _row_get


def _pct(x: float | None, nd: int = 1) -> str:
    if x is None:
        return "—"
    return f"{x * 100:.{nd}f}%"


def _has(val: Any) -> bool:
    if val is None:
        return False
    try:
        if pd.isna(val):
            return False
    except (TypeError, ValueError):
        pass
    return not (isinstance(val, str) and not val.strip())


def _strength_score(x: float | None, good: float) -> str:
    """'forte' | 'razoável' | 'fraco' | 'sem dado' — maior = melhor."""
    if x is None:
        return "sem dado"
    if x >= good:
        return "forte"
    if x >= good * 0.6:
        return "razoável"
    return "fraco"


def _debt_label(debt: float) -> str:
    """Dívida: menor é melhor. Nunca chamar 3x de 'forte'."""
    if debt <= 0:
        return "forte (caixa líquido)"
    if debt <= 1.5:
        return "confortável"
    if debt <= 3.0:
        return "esticada"
    return "preocupante"


def build_stock_narrative(row: pd.Series | dict[str, Any]) -> str:
    """Monta a narrativa de uma linha de fundamentals/score (uma empresa).

    Devolve um texto multilinha (frases separadas por ``\\n``). Se a linha não
    tem nada, devolve um fallback honesto.
    """
    if row is None:
        return "Sem dados suficientes para descrever esta empresa."

    name = str(_row_get(row, "name") or _row_get(row, "ticker") or "a empresa")
    ticker = str(_row_get(row, "ticker") or "")
    sector = str(_row_get(row, "sector") or "—")
    score = _safe(_row_get(row, "score_total"))

    dy = _safe(_row_get(row, "dividend_yield"))
    roe = _safe(_row_get(row, "roe"))
    payout = _safe(_row_get(row, "payout"))
    debt = _safe(_row_get(row, "net_debt_ebitda"))
    fcf_pos = _row_get(row, "fcf_positive")
    pe = _safe(_row_get(row, "pe"))
    bucket = str(_row_get(row, "bucket") or "")
    quality_label = str(_row_get(row, "quality_label") or "")
    completeness = _safe(_row_get(row, "data_completeness_pct"))

    lines: list[str] = []

    # Abertura: o que é + setor
    opening = f"**{name}**{f' ({ticker})' if ticker else ''} — setor **{sector}**."
    lines.append(opening)

    # Nota e papel na carteira
    if score is not None:
        bucket_txt = ""
        if bucket == "core":
            bucket_txt = ", parte da **base** da tese (mais estável)"
        elif bucket == "satellite":
            bucket_txt = ", parte do **complemento** (um pouco mais flexível)"
        lines.append(f"Nota do app: **{score:.0f}/100**{bucket_txt}.")

    # Só narra pilar quando o input existe — nota 50 de dado faltando não vira texto.
    if roe is not None:
        q_txt = _strength_score(roe, 0.15)
        lines.append(
            f"Qualidade **{q_txt}**: ROE de {_pct(roe)} no último dado disponível."
        )
    else:
        lines.append("Qualidade: **sem dado de ROE** — não dá para afirmar consistência.")

    if dy is not None:
        dy_txt = _strength_score(dy, 0.05)
        extra = ""
        if payout is not None:
            if payout > 1.0:
                extra = " — atenção: paga mais do que lucra (payout acima de 100%)"
            elif payout >= 0.8:
                extra = " — payout alto, acompanhe"
        lines.append(
            f"Dividendos **{dy_txt}**: yield recente de {_pct(dy)} ao ano{extra} "
            "(não é garantia de pagamento futuro)."
        )
    else:
        lines.append("Sem dado de dividendo — não entrou por causa de renda.")

    if debt is not None:
        lines.append(f"Dívida **{_debt_label(debt)}** ({debt:.1f}x o EBITDA).")
    else:
        lines.append("Saúde financeira: **sem dado de dívida**.")

    if pe is not None and pe > 0:
        pe_txt = "convidativo" if pe < 12 else ("razoável" if pe < 20 else "cara")
        lines.append(f"Preço {pe_txt} em relação ao lucro (P/L {pe:.1f}).")
    else:
        lines.append("Preço: **sem P/L** — não estimamos “preço justo”.")

    # Ressalvas honestas
    ressalvas: list[str] = []
    if fcf_pos is False:
        ressalvas.append("o caixa livre está negativo (menos folga para dividendo)")
    if dy is not None and dy >= 0.14:
        ressalvas.append("o dividendo está bem alto — confira se é sustentável")
    if quality_label:
        label = quality_label.lower()
        if "treino" in label:
            ressalvas.append("os números são de treino, não de mercado real")
        elif "parcial" in label or "fraca" in label:
            ressalvas.append("alguns dados podem estar incompletos")
    if completeness is not None and completeness < 45:
        ressalvas.append("muitos dados faltando")

    if ressalvas:
        lines.append("Ressalva: " + "; ".join(ressalvas) + ".")

    # Fecho
    if score is not None:
        if score >= 70:
            lines.append("Bom encaixe na tese de renda com qualidade — ainda assim, confira antes de decidir.")
        elif score >= 55:
            lines.append("Encaixe razoável: tem pontos bons e pontos a vigiar.")
        else:
            lines.append("Encaixe abaixo do ideal — estude antes de incluir.")

    return "\n".join(lines)


def build_portfolio_summary(
    recs: pd.DataFrame,
    *,
    thesis_label: str,
    thesis_version: str,
) -> str:
    """Narrativa curta da carteira sugerida (usada na página Descobrir).

    Explica, em 2–3 frases, o que a lista de recomendados representa.
    """
    if recs is None or recs.empty:
        return "Nenhuma sugestão no momento."

    n = len(recs)
    core = int((recs.get("bucket").astype(str).eq("core")).sum()) if "bucket" in recs.columns else 0
    sat = n - core
    top = str(recs.iloc[0].get("ticker") or "—") if "ticker" in recs.columns else "—"
    top_score = _safe(recs.iloc[0].get("score_total"))
    top_score_txt = f"{top_score:.0f}/100" if top_score is not None else "sem nota"

    return (
        f"Lista **{thesis_label} v{thesis_version}** com **{n} sugestões** "
        f"({core} na base, {sat} no complemento). "
        f"A primeira sugestão é **{top}** ({top_score_txt}) — o app prioriza "
        "qualidade e dividendos sustentáveis, não o maior rendimento do momento."
    )
