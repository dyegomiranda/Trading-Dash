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
<div class="td-wallet" style="margin-bottom: 1.25rem !important;">
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
