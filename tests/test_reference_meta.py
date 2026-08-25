"""Cadastro B3: nomes ticker-primeiro e setores do universo histórico."""

from __future__ import annotations

from src.config import B3_HISTORICAL_EXTRA
from src.data.reference import (
    format_ticker_display,
    get_ticker_meta,
    is_known_sector,
    is_tradable,
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


def test_historical_tickers_are_not_live_tradable():
    assert is_tradable("LAME3") is False
    assert is_tradable("ITUB4") is True


def test_live_universe_skips_historical_unless_requested():
    from src.data.universe import get_universe

    live = get_universe(include_historical=False)
    assert "LAME3" not in live
    hist = get_universe(include_historical=True)
    assert "LAME3" in hist


def test_resolve_sector_prefers_cadastro():
    assert resolve_sector("Consumer Cyclical", "Unknown") == "Consumer Cyclical"
    assert resolve_sector("Unknown", "Utilities") == "Utilities"
    assert resolve_sector(None, "Unknown", "") == "Unknown"
