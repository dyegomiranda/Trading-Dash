"""Compat: reexporta tema + componentes.

Prefira importar de:
- src.ui.theme
- src.ui.components
- src.ui.wallet
"""

from __future__ import annotations

from src.ui.components import (  # noqa: F401
    chart_card_close,
    chart_card_open,
    plotly_layout,
    render_brand,
    render_disclaimer_bar,
    render_feature_cards,
    render_guide_box,
    render_hero,
    render_kpi_row,
    render_page_header,
    render_section_label,
    render_steps_card,
    style_plotly_fig,
)
from src.ui.theme import COLORS, apply_theme  # noqa: F401
from src.ui.wallet import render_asset_rows, render_wallet_balance  # noqa: F401

__all__ = [
    "COLORS",
    "apply_theme",
    "chart_card_close",
    "chart_card_open",
    "plotly_layout",
    "render_asset_rows",
    "render_brand",
    "render_disclaimer_bar",
    "render_feature_cards",
    "render_guide_box",
    "render_hero",
    "render_kpi_row",
    "render_page_header",
    "render_section_label",
    "render_steps_card",
    "render_wallet_balance",
    "style_plotly_fig",
]
