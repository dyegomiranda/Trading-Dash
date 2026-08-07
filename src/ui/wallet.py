"""Componentes de carteira estilo wallet (Exodus-like)."""

from __future__ import annotations

import html
from typing import Sequence

import streamlit as st


def render_wallet_balance(
    total: str,
    delta: str,
    delta_positive: bool,
    stats: Sequence[tuple[str, str]],
    badge: str = "Conta de treino",
) -> None:
    """Card principal estilo carteira (saldo em destaque)."""
    cls = "up" if delta_positive else "down"
    arrow = "▲" if delta_positive else "▼"
    stats_html = "".join(
        f"""
<div class="td-wallet-stat">
  <div class="s-label">{html.escape(label)}</div>
  <div class="s-value">{html.escape(value)}</div>
</div>
"""
        for label, value in stats
    )
    st.markdown(
        f"""
<div class="td-wallet">
  <div class="td-wallet-top">
    <div>
      <div class="td-wallet-label">Patrimônio total</div>
      <div class="td-wallet-balance">{html.escape(total)}</div>
      <div class="td-wallet-delta {cls}">{arrow} {html.escape(delta)}</div>
    </div>
    <div class="td-wallet-badge">{html.escape(badge)}</div>
  </div>
  <div class="td-wallet-grid">{stats_html}</div>
</div>
""",
        unsafe_allow_html=True,
    )


def render_asset_rows(
    rows: Sequence[tuple[str, str, str, str, str, str, bool]],
) -> None:
    """Lista de ativos estilo wallet.

    each row: (ticker, subtitle, shares_label, price_label, market_value, pnl_label, pnl_positive)
    """
    if not rows:
        return
    parts = ['<div class="td-asset-list">']
    for ticker, subtitle, shares_label, price_label, mv, pnl, pos in rows:
        cls = "up" if pos else "down"
        avatar = html.escape((ticker[:4] if ticker else "?").upper())
        parts.append(
            f"""
<div class="td-asset-row">
  <div class="td-asset-avatar">{avatar}</div>
  <div class="td-asset-name">
    <strong>{html.escape(ticker)}</strong>
    <span>{html.escape(subtitle)}</span>
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
