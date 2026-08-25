"""Coach amigável da tese Quality Dividend.

Usa SpaceXAI (API xAI, OpenAI-compatible) quando há ``XAI_API_KEY``.
Sem chave, devolve textos claros baseados nas métricas (sempre funciona offline).
"""

from __future__ import annotations

import os
from typing import Any

import pandas as pd

from src.config import THESIS_LABEL, THESIS_VERSION, get_settings


def _has_xai_key() -> bool:
    return bool(os.environ.get("XAI_API_KEY") or os.environ.get("XAI_KEY"))


def _client():
    from openai import OpenAI

    key = os.environ.get("XAI_API_KEY") or os.environ.get("XAI_KEY")
    return OpenAI(api_key=key, base_url="https://api.x.ai/v1")


def _chat(system: str, user: str, *, max_tokens: int = 500) -> str | None:
    if not _has_xai_key():
        return None
    try:
        client = _client()
        # Prefer chat.completions for broad compatibility
        resp = client.chat.completions.create(
            model=os.environ.get("XAI_MODEL", "grok-4-1-fast-non-reasoning"),
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            max_tokens=max_tokens,
            temperature=0.4,
        )
        text = (resp.choices[0].message.content or "").strip()
        return text or None
    except Exception:
        try:
            # fallback responses API
            client = _client()
            resp = client.responses.create(
                model=os.environ.get("XAI_MODEL", "grok-4.5"),
                input=f"{system}\n\n{user}",
            )
            text = getattr(resp, "output_text", None) or ""
            return str(text).strip() or None
        except Exception:
            return None


def _fmt_pct(x: Any) -> str:
    try:
        if x is None or (isinstance(x, float) and x != x):
            return "—"
        return f"{float(x) * 100:.1f}%"
    except (TypeError, ValueError):
        return "—"


def _fmt_num(x: Any, nd: int = 1) -> str:
    try:
        if x is None or (isinstance(x, float) and x != x):
            return "—"
        return f"{float(x):.{nd}f}"
    except (TypeError, ValueError):
        return "—"


def _row_dict(row: pd.Series | dict[str, Any]) -> dict[str, Any]:
    if isinstance(row, pd.Series):
        return row.to_dict()
    return dict(row or {})


def explain_ticker_fallback(row: pd.Series | dict[str, Any]) -> str:
    """Explicação em português sem IA (sempre disponível)."""
    d = _row_dict(row)
    ticker = d.get("ticker") or "?"
    name = d.get("name") or ticker
    sector = d.get("sector") or "setor não informado"
    score = d.get("score_total")
    dy = d.get("dividend_yield")
    roe = d.get("roe")
    payout = d.get("payout")
    debt = d.get("net_debt_ebitda")
    bucket = d.get("bucket") or ""
    qlabel = d.get("quality_label") or ""

    bucket_pt = (
        "base (mais estável)"
        if bucket == "core"
        else ("complemento" if bucket == "satellite" else bucket or "—")
    )

    lines = [
        f"**{ticker}** — {name} ({sector})",
        f"- Papel na tese: **{bucket_pt}**",
        f"- Nota da tese: **{_fmt_num(score, 0)}/100**",
        f"- Quanto paga de dividendo ao ano (aprox.): **{_fmt_pct(dy)}**",
        f"- Lucratividade (ROE): **{_fmt_pct(roe)}**",
        f"- Parte do lucro paga em dividendos: **{_fmt_pct(payout)}**",
        f"- Endividamento (dívida líquida/EBITDA): **{_fmt_num(debt, 1)}**",
    ]
    if qlabel:
        lines.append(f"- Qualidade dos dados: **{qlabel}**")

    # Julgamento amigável
    tips = []
    try:
        settings = get_settings()
        if dy is not None and float(dy) >= float(settings.high_yield_trap):
            tips.append(
                "O % de dividendo está alto — a tese desconfia de “renda boa demais” "
                "se payout/dívida não ajudarem."
            )
        if score is not None and float(score) >= 70:
            tips.append("Encaixa bem na ideia de renda com qualidade.")
        elif score is not None and float(score) < 55:
            tips.append("Nota baixa para a tese atual — costuma ficar de fora da montagem automática.")
        if debt is not None and float(debt) > float(settings.max_net_debt_ebitda):
            tips.append("Endividamento elevado para o filtro rigoroso da tese.")
    except Exception:
        pass

    if tips:
        lines.append("")
        lines.append("**Em português claro:**")
        for t in tips:
            lines.append(f"- {t}")

    lines.append("")
    lines.append(
        f"_Isto é um guia da {THESIS_LABEL} v{THESIS_VERSION}, não uma ordem de compra._"
    )
    return "\n".join(lines)


def explain_ticker(row: pd.Series | dict[str, Any]) -> dict[str, Any]:
    """Retorna texto + se veio da IA ou do template local."""
    d = _row_dict(row)
    fallback = explain_ticker_fallback(d)
    system = (
        "Você é um coach de investimentos para iniciantes no Brasil. "
        "Explique com linguagem simples, sem jargão desnecessário. "
        "Foco na tese Quality Dividend: qualidade + dividendos sustentáveis + "
        "saúde financeira + preço razoável. "
        "Nunca diga que é garantia de lucro. Máximo 180 palavras. "
        "Use bullet points curtos."
    )
    user = (
        f"Explique por que esta ação pode (ou não) encaixar na tese:\n"
        f"ticker={d.get('ticker')}, nome={d.get('name')}, setor={d.get('sector')}, "
        f"nota={d.get('score_total')}, dy={d.get('dividend_yield')}, roe={d.get('roe')}, "
        f"payout={d.get('payout')}, divida_ebitda={d.get('net_debt_ebitda')}, "
        f"bucket={d.get('bucket')}, qualidade_dados={d.get('quality_label')}"
    )
    ai = _chat(system, user)
    if ai:
        return {"text": ai, "source": "ia", "fallback": fallback}
    return {"text": fallback, "source": "local", "fallback": fallback}


def narrative_thesis(
    *,
    n_suggestions: int,
    avg_score: float | None,
    top_tickers: list[str],
    provider: str,
) -> dict[str, Any]:
    settings = get_settings()
    tops = ", ".join(top_tickers[:5]) if top_tickers else "—"
    local = (
        f"**{THESIS_LABEL}** (v{THESIS_VERSION}) em uma frase: preferir empresas que lucram bem, "
        f"pagam dividendos de forma sustentável e não estão excessivamente endividadas, "
        f"com cerca de {settings.core_weight:.0%} em nomes mais estáveis (base) e "
        f"{settings.satellite_weight:.0%} em complemento.\n\n"
        f"Agora o app encontrou **{n_suggestions} sugestões**"
        + (f" (nota média ~{avg_score:.0f})" if avg_score is not None else "")
        + f". Exemplos no topo: **{tops}**.\n\n"
        f"Fonte: **{'números ilustrativos' if provider == 'demo' else 'bolsa (Yahoo + cadastro B3)'}**. "
        "Use **Montar carteira com a tese** para aplicar em dinheiro de treino."
    )
    system = (
        "Coach amigável para iniciantes. Resuma a tese Quality Dividend e o momento do ranking "
        "em até 120 palavras, tom encorajador e prudente. Não prometa retorno."
    )
    user = (
        f"n_sugestoes={n_suggestions}, nota_media={avg_score}, top={tops}, "
        f"provider={provider}, core={settings.core_weight}, sat={settings.satellite_weight}"
    )
    ai = _chat(system, user, max_tokens=350)
    if ai:
        return {"text": ai, "source": "ia"}
    return {"text": local, "source": "local"}


def summarize_headlines(titles: list[str], *, tickers: list[str] | None = None) -> dict[str, Any]:
    titles = [t for t in titles if t][:8]
    if not titles:
        return {
            "text": "Sem manchetes no momento. Atualize o overview ou tente mais tarde.",
            "source": "local",
        }
    local_lines = ["**Manchetes recentes (resumo local):**"]
    for t in titles[:5]:
        local_lines.append(f"- {t}")
    local_lines.append(
        "_Leia a fonte completa antes de qualquer decisão; notícias não são recomendações._"
    )
    local = "\n".join(local_lines)

    system = (
        "Resuma notícias da B3/empresas para um iniciante em português do Brasil. "
        "5 bullets no máximo, linguagem simples, sem alarmismo nem hype. "
        "Diga se algo parece relevante para quem busca dividendos de qualidade."
    )
    user = "Títulos:\n" + "\n".join(f"- {t}" for t in titles)
    if tickers:
        user += "\nTickers de interesse: " + ", ".join(tickers[:8])
    ai = _chat(system, user, max_tokens=400)
    if ai:
        return {"text": ai, "source": "ia"}
    return {"text": local, "source": "local"}
