"""Componentes de carteira estilo wallet (Exodus-like)."""

from __future__ import annotations

import html
from collections.abc import Sequence

import streamlit as st

# stat: (rótulo, valor) ou (rótulo, valor, dica curta)
StatItem = tuple[str, str] | tuple[str, str, str]


def render_wallet_balance(
    total: str,
    delta: str,
    delta_positive: bool,
    stats: Sequence[StatItem],
    badge: str = "Conta de treino",
    *,
    label: str = "Dinheiro total na conta de treino",
    hint: str | None = None,
    show_delta_arrow: bool = True,
) -> None:
    """Card principal estilo carteira (valor em destaque).

    ``label`` define o que o número grande representa — nunca reutilize o card
    de patrimônio para renda sem trocar o rótulo.
    """
    cls = "up" if delta_positive else ("down" if delta_positive is False else "neutral")
    arrow = ""
    if show_delta_arrow and delta:
        if delta_positive is True:
            arrow = "▲ "
        elif delta_positive is False:
            arrow = "▼ "
    stats_html = "".join(_stat_html(item) for item in stats)
    hint_html = (
        f'<div class="td-wallet-hint">{html.escape(hint)}</div>' if hint else ""
    )
    delta_html = ""
    if delta:
        delta_html = (
            f'<div class="td-wallet-delta {cls}">{arrow}{html.escape(delta)}</div>'
        )
    st.markdown(
        f"""
<div class="td-wallet">
  <div class="td-wallet-top">
    <div>
      <div class="td-wallet-label">{html.escape(label)}</div>
      <div class="td-wallet-balance">{html.escape(total)}</div>
      {delta_html}
      {hint_html}
    </div>
    <div class="td-wallet-badge">{html.escape(badge)}</div>
  </div>
  <div class="td-wallet-grid">{stats_html}</div>
</div>
""",
        unsafe_allow_html=True,
    )


def _stat_html(item: StatItem) -> str:
    if len(item) == 3:
        label, value, tip = item  # type: ignore[misc]
        tip_html = f'<div class="s-tip">{html.escape(tip)}</div>'
    else:
        label, value = item  # type: ignore[misc]
        tip_html = ""
    return f"""
<div class="td-wallet-stat">
  <div class="s-label">{html.escape(label)}</div>
  <div class="s-value">{html.escape(value)}</div>
  {tip_html}
</div>
"""


def render_asset_rows(
    rows: Sequence[tuple[str, str, str, str, str, str, bool, str]],
) -> None:
    """Lista de ativos estilo wallet.

    each row: (ticker, display_name, shares_label, price_label, market_value, pnl_label, pnl_positive, bucket_label)
    """
    parts = ['<div class="td-asset-list">']
    for ticker, display_name, shares_label, price_label, mv, pnl, pos, bucket_label in rows:
        cls = "up" if pos else "down"
        avatar = html.escape((ticker[:4] if ticker else "?").upper())
        parts.append(
            f"""
<div class="td-asset-row">
  <div class="td-asset-avatar">{avatar}</div>
  <div class="td-asset-name">
    <strong>{html.escape(display_name)}</strong>
    {f'<span>{html.escape(bucket_label)}</span>' if bucket_label else ''}
  </div>
  <div class="td-asset-mid">
    {html.escape(shares_label)}
    <small>{html.escape(price_label)}</small>
  </div>
  <div class="td-asset-right">
    <div class="mv">{html.escape(mv)}</div>
    <div class="pnl {cls}">{html.escape(pnl)}</div>
  </div>
</div>
"""
        )
    parts.append("</div>")
    st.markdown("".join(parts), unsafe_allow_html=True)


def render_stock_detail_card(
    ticker: str,
    scored_row: dict,
    holdings_row: dict,
    price: float | None = None,
) -> None:
    """Renderiza card detalhado de uma ação dentro de um expander."""
    import streamlit as st

    import numpy as np

    def _score_val(k: str) -> float | None:
        v = scored_row.get(k)
        if v is None:
            return None
        try:
            f = float(v)
            return None if np.isnan(f) or np.isinf(f) else f
        except (ValueError, TypeError):
            return None

    score_total = _score_val("score_total") or 0.0
    score_quality = _score_val("score_quality")
    score_dividends = _score_val("score_dividends")
    score_health = _score_val("score_financial_health")
    score_valuation = _score_val("score_valuation")
    bucket = str(scored_row.get("bucket") or "")
    quality_level = str(scored_row.get("quality_level") or "treino")
    quality_label = str(scored_row.get("quality_label") or "")
    sector = str(scored_row.get("sector") or "—")
    name = str(scored_row.get("name") or ticker)

    def _bar_color(score: float) -> str:
        if score >= 70:
            return "#4ADE80"
        if score >= 50:
            return "#FACC15"
        if score >= 30:
            return "#FB923C"
        return "#F87171"

    def _pill(label: str, value: float | None) -> str:
        if value is None:
            return (
                f'<div class="td-score-pill">'
                f'<div class="label">{html.escape(label)}</div>'
                f'<div class="value" style="color:#94A3B8">—</div>'
                f'<div class="td-score-bar"><div class="fill" style="width:0%;background:#94A3B8"></div></div>'
                f'</div>'
            )
        color = _bar_color(value)
        return (
            f'<div class="td-score-pill">'
            f'<div class="label">{html.escape(label)}</div>'
            f'<div class="value" style="color:{color}">{value:.0f}</div>'
            f'<div class="td-score-bar"><div class="fill" style="width:{min(value,100):.0f}%;background:{color}"></div></div>'
            f'</div>'
        )

    # Quality badge
    badge_cls = {"treino": "training", "boa": "good", "parcial": "partial", "fraca": "weak"}.get(quality_level, "training")
    badge_icon = {"treino": "🎓", "boa": "✅", "parcial": "⚠️", "fraca": "❌"}.get(quality_level, "🎓")
    badge_html = f'<span class="td-quality-badge {badge_cls}">{badge_icon} {html.escape(quality_label or quality_level)}</span>'

    # Why selected
    bucket_pt = "Base (mais estável)" if bucket == "core" else ("Complemento" if bucket == "satellite" else "")
    strengths = []
    if score_quality and score_quality >= 65:
        strengths.append("negócio lucrativo e consistente")
    if score_dividends and score_dividends >= 65:
        strengths.append("bom histórico de dividendos")
    if score_health and score_health >= 65:
        strengths.append("saúde financeira sólida")
    if score_valuation and score_valuation >= 65:
        strengths.append("preço atrativo")

    has_valid_fundamentals = (
        score_total > 0
        and ((score_quality or 0) > 0 or (score_dividends or 0) > 0 or (score_health or 0) > 0 or (score_valuation or 0) > 0)
        and quality_level != "fraca"
    )

    if has_valid_fundamentals:
        why_text = f"<strong>{html.escape(name)}</strong> ({html.escape(ticker)})"
        if bucket_pt:
            why_text += f" · classificada como <strong>{html.escape(bucket_pt)}</strong>"
        why_text += f" · nota geral <strong>{score_total:.0f}/100</strong>."
        why_text += (
            " <em>Qualidade</em> aqui é o negócio (ROE, margens, caixa) — "
            "o Q de Quality Dividend, não a nota geral."
        )
        if score_quality and score_quality < 50:
            why_text += (
                " A nota de qualidade está baixa: a tese exige lucro sustentável, "
                "não só dividendo alto."
            )
        if strengths:
            why_text += f" Destaque: {', '.join(strengths)}."
    else:
        why_text = f"<strong>{html.escape(name)}</strong> ({html.escape(ticker)}) · Ação em carteira. Os dados de balanço detalhados estão sendo atualizados da bolsa."

    # Indicators
    def _fmt(val, fmt_str=".1f", suffix="", prefix=""):
        if val is None or (isinstance(val, float) and (val != val)):
            return "—"
        try:
            return f"{prefix}{float(val):{fmt_str}}{suffix}"
        except (ValueError, TypeError):
            return "—"

    indicators = [
        ("Setor", html.escape(sector)),
        ("ROE", _fmt(scored_row.get("roe"), ".1f", "%")),
        ("Div. Yield", _fmt(scored_row.get("dividend_yield"), ".1f", "%")),
        ("P/L", _fmt(scored_row.get("pe"), ".1f", "x")),
        ("P/VP", _fmt(scored_row.get("pb"), ".2f", "x")),
        ("Dív.Líq/EBITDA", _fmt(scored_row.get("net_debt_ebitda"), ".1f", "x")),
        ("Payout", _fmt(scored_row.get("payout"), ".0f", "%")),
        ("FCF Yield", _fmt(scored_row.get("fcf_yield"), ".1f", "%")),
        ("Margem Líq.", _fmt(scored_row.get("net_margin"), ".1f", "%")),
        ("Anos Pagando Div.", _fmt(scored_row.get("years_paying_dividend"), ".0f")),
        ("CAGR Div. 5a", _fmt(scored_row.get("dividend_cagr_5y"), ".1f", "%")),
        ("EV/EBITDA", _fmt(scored_row.get("ev_ebitda"), ".1f", "x")),
    ]
    ind_html = "".join(
        f'<div class="td-ind"><div class="ind-label">{lbl}</div><div class="ind-value">{val}</div></div>'
        for lbl, val in indicators
    )

    # Genuine Fundamental Risks Detection
    risk_tags = []
    
    # High leverage risk
    debt_val = scored_row.get("net_debt_ebitda")
    if debt_val is not None:
        try:
            if float(debt_val) > 3.5:
                risk_tags.append(f"Alavancagem alta (Dív. Líq/EBITDA {float(debt_val):.1f}x)")
        except (ValueError, TypeError):
            pass
            
    # High payout risk
    payout_val = scored_row.get("payout")
    if payout_val is not None:
        try:
            p_flt = float(payout_val)
            if p_flt > 0.95:
                risk_tags.append(f"Payout elevado ({p_flt*100 if p_flt<=1.0 else p_flt:.0f}%)")
        except (ValueError, TypeError):
            pass

    # Negative ROE (loss)
    roe_val = scored_row.get("roe")
    if roe_val is not None:
        try:
            if float(roe_val) < 0:
                risk_tags.append("Prejuízo recente (ROE negativo)")
        except (ValueError, TypeError):
            pass

    # Dividend trap risk
    dy_val = scored_row.get("dividend_yield")
    if dy_val is not None and payout_val is not None:
        try:
            if float(dy_val) > 0.14 and float(payout_val) > 0.90:
                risk_tags.append("Possível armadilha de dividendos (yield alto com payout esticado)")
        except (ValueError, TypeError):
            pass

    # Negative FCF
    fcf_val = scored_row.get("fcf_yield")
    if fcf_val is not None:
        try:
            if float(fcf_val) < 0:
                risk_tags.append("Fluxo de caixa livre negativo")
        except (ValueError, TypeError):
            pass

    # Stretched valuation
    pe_val = scored_row.get("pe")
    if pe_val is not None:
        try:
            if float(pe_val) > 35:
                risk_tags.append(f"Múltiplo P/L esticado ({float(pe_val):.1f}x)")
        except (ValueError, TypeError):
            pass

    if not has_valid_fundamentals:
        risks_html = (
            '<div style="font-size:0.78rem;color:#FACC15;background:rgba(250,204,21,0.08);'
            'border:1px solid rgba(250,204,21,0.2);border-radius:8px;padding:0.4rem 0.6rem;margin-top:0.5rem;">'
            '⚠️ <strong>Dados de balanço pendentes ou parciais na fonte atual.</strong> '
            'Clique em <em>Atualizar dados</em> na barra lateral para recarregar as informações da bolsa.'
            '</div>'
        )
    elif risk_tags:
        tags = "".join(f'<span class="td-risk-tag">{html.escape(t)}</span>' for t in risk_tags[:4])
        risks_html = f'<div class="td-risks" style="margin-top:0.5rem;"><span style="font-size:0.75rem;color:#FCA5A5;font-weight:600;margin-right:0.3rem;">Pontos de atenção:</span>{tags}</div>'
    else:
        risks_html = (
            '<div style="font-size:0.75rem;color:#4ADE80;margin-top:0.4rem;">'
            "Nenhum alerta crítico nos <strong>fundamentos da tese</strong> "
            "(isso não fala do lucro ou prejuízo da sua compra de treino)."
            "</div>"
        )

    full_html = f"""
<div class="td-stock-detail">
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:0.5rem;">
    <span style="font-size:0.8rem;color:#94A3B8;">Nota geral da tese: <strong style="color:#F8FAFC;font-size:1rem;">{score_total:.0f}</strong>/100</span>
    {badge_html}
  </div>
  <div class="td-score-row">
    {_pill("Qualidade (ROE/caixa)", score_quality)}
    {_pill("Dividendos", score_dividends)}
    {_pill("Saúde Fin.", score_health)}
    {_pill("Preço Justo", score_valuation)}
  </div>
  <div class="td-why">{why_text}</div>
  <div class="td-indicators">{ind_html}</div>
  {risks_html}
</div>
"""
    st.markdown(full_html, unsafe_allow_html=True)

