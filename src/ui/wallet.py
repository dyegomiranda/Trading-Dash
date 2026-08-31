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

    score_total = float(scored_row.get("score_total") or 0)
    score_quality = float(scored_row.get("score_quality") or 0)
    score_dividends = float(scored_row.get("score_dividends") or 0)
    score_health = float(scored_row.get("score_financial_health") or 0)
    score_valuation = float(scored_row.get("score_valuation") or 0)
    bucket = str(scored_row.get("bucket") or "")
    quality_level = str(scored_row.get("quality_level") or "treino")
    quality_label = str(scored_row.get("quality_label") or "")
    quality_flags = scored_row.get("quality_flags") or ""
    reject_reason = str(scored_row.get("reject_reason") or "")
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

    def _pill(label: str, value: float) -> str:
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
    if score_quality >= 65:
        strengths.append("negócio lucrativo e consistente")
    if score_dividends >= 65:
        strengths.append("bom histórico de dividendos")
    if score_health >= 65:
        strengths.append("saúde financeira sólida")
    if score_valuation >= 65:
        strengths.append("preço atrativo")
    why_text = f"<strong>{html.escape(name)}</strong> ({html.escape(ticker)})"
    if bucket_pt:
        why_text += f" · classificada como <strong>{html.escape(bucket_pt)}</strong>"
    why_text += f" · nota geral <strong>{score_total:.0f}/100</strong>."
    if strengths:
        why_text += f" Destaque: {', '.join(strengths)}."

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

    # Risks
    risks_html = ""
    risk_tags = []
    if quality_flags:
        for flag in str(quality_flags).split(","):
            flag = flag.strip()
            if flag:
                risk_tags.append(flag)
    if reject_reason and reject_reason != "nan":
        for reason in reject_reason.split(","):
            reason = reason.strip()
            if reason:
                risk_tags.append(reason)
    if risk_tags:
        tags = "".join(f'<span class="td-risk-tag">{html.escape(t)}</span>' for t in risk_tags[:6])
        risks_html = f'<div class="td-risks">{tags}</div>'

    full_html = f"""
<div class="td-stock-detail">
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:0.5rem;">
    <span style="font-size:0.8rem;color:#94A3B8;">Nota geral: <strong style="color:#F8FAFC;font-size:1rem;">{score_total:.0f}</strong>/100</span>
    {badge_html}
  </div>
  <div class="td-score-row">
    {_pill("Qualidade", score_quality)}
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

