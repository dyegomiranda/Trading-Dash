"""Cadastro B3: nomes ticker-primeiro e setores do universo histórico."""

from __future__ import annotations

from src.config import B3_HISTORICAL_EXTRA
from src.data.reference import (
    format_ticker_display,
    get_ticker_meta,
    is_known_sector,
    lookup_company_name,
    resolve_sector,
)


def test_format_ticker_display_ticker_first():
    text = format_ticker_display("LREN3")
    assert text.startswith("LREN3")
    assert "Renner" in text
    assert text.index("LREN3") < text.index("Renner")


def test_lookup_lren_is_lojas_renner():
    name = lookup_company_name("LREN3")
    assert "Renner" in name


def test_historical_extras_have_known_sector():
    missing = []
    for t in B3_HISTORICAL_EXTRA:
        meta = get_ticker_meta(t)
        if not is_known_sector(meta.get("sector")):
            missing.append(t)
    assert missing == [], f"setor Unknown em {missing}"


def test_resolve_sector_prefers_cadastro():
    assert resolve_sector("Consumer Cyclical", "Unknown") == "Consumer Cyclical"
    assert resolve_sector("Unknown", "Utilities") == "Utilities"
    assert resolve_sector(None, "Unknown", "") == "Unknown"
