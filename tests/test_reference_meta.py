"""Cadastro B3: nomes ticker-primeiro e setores do universo histórico."""

from __future__ import annotations

from src.config import B3_HISTORICAL_EXTRA
from src.data.reference import (
    control_label,
    format_ticker_display,
    get_ticker_meta,
    is_known_sector,
    is_tradable,
    listing_segment,
    lookup_company_name,
    resolve_sector,
    tag_along_pct,
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


def test_historical_tickers_are_not_live_tradable():
    assert is_tradable("LAME3") is False
    assert is_tradable("ITUB4") is True


def test_live_universe_skips_historical_unless_requested():
    from src.data.universe import get_universe

    live = get_universe(include_historical=False)
    assert "LAME3" not in live
    hist = get_universe(include_historical=True)
    assert "LAME3" in hist


def test_listing_segment_and_tag_along():
    assert listing_segment("AALR3") == "Novo Mercado"
    assert tag_along_pct("AALR3") == 1.0
    assert listing_segment("WEGE3") == "Novo Mercado"
    assert listing_segment("ITUB4") == "Nível 1"
    assert listing_segment("PETR4") == "Nível 2"
    assert tag_along_pct("PETR4") == 1.0
    assert control_label("WEGE3") is None


def test_resolve_sector_prefers_cadastro():
    assert resolve_sector("Consumer Cyclical", "Unknown") == "Consumer Cyclical"
    assert resolve_sector("Unknown", "Utilities") == "Utilities"
    assert resolve_sector(None, "Unknown", "") == "Unknown"
