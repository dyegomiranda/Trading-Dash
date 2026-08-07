"""UI package — imports estáveis e pequenos."""

from src.ui.charts import holdings_donut, sector_bars, sector_breakdown_from_holdings
from src.ui.components import (
    apply_theme,
    render_brand,
    render_feature_cards,
    render_hero,
    render_kpi_row,
    render_page_header,
    render_section_label,
)
from src.ui.friendly import (
    COLUMN_LABELS,
    GLOSSARY,
    friendly_dataframe,
    render_disclaimer,
    render_sidebar_brand,
)
from src.ui.wallet import render_asset_rows, render_wallet_balance

__all__ = [
    "COLUMN_LABELS",
    "GLOSSARY",
    "apply_theme",
    "friendly_dataframe",
    "holdings_donut",
    "render_asset_rows",
    "render_brand",
    "render_disclaimer",
    "render_feature_cards",
    "render_hero",
    "render_kpi_row",
    "render_page_header",
    "render_section_label",
    "render_sidebar_brand",
    "render_wallet_balance",
    "sector_bars",
    "sector_breakdown_from_holdings",
]
