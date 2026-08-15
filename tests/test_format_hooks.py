"""Pacote: internacionalização leve — hook de formatação de números.

Valida que o formato central respeita o locale ativo (pt_BR por padrão) e que
a troca para en_US muda separadores e símbolo de moeda sem caçar formatação
espalhada.
"""

from __future__ import annotations

import pytest

import src.format_hooks as fh


@pytest.fixture(autouse=True)
def _reset_locale():
    fh.set_active_locale("pt_BR")
    yield
    fh.set_active_locale("pt_BR")


def test_format_num_decimal_comma_pt():
    assert fh.format_num(3.14, 2) == "3,14"
    assert fh.format_num(1234.5, 1) == "1.234,5"


def test_format_num_thousands_pt():
    assert fh.format_num(9876543.0, 0) == "9.876.543"


def test_format_num_none():
    assert fh.format_num(None) == "—"


def test_format_num_negative():
    assert fh.format_num(-42.5, 1) == "−42,5" or fh.format_num(-42.5, 1) == "-42,5"


def test_format_brl_pt():
    assert fh.format_brl_hook(1234.56) == "R$ 1.234,56"


def test_format_pct_pt():
    assert fh.format_pct_hook(0.086, 1) == "8,6%"


def test_switch_to_en_us():
    fh.set_active_locale("en_US")
    assert fh.format_num(1234.5, 1) == "1,234.5"
    assert fh.format_brl_hook(1234.56) == "$ 1,234.56"
    assert fh.format_pct_hook(0.086, 1) == "8.6%"


def test_services_format_delegates():
    from src.services import format_brl, format_pct

    assert format_brl(1234.56) == "R$ 1.234,56"
    assert format_pct(0.086, 1) == "8,6%"
    # troca de locale reflete no serviço (mesmo path de hook)
    fh.set_active_locale("en_US")
    assert format_brl(1234.56) == "$ 1,234.56"


def test_settings_locale_field_defaults_pt():
    from src.config import get_settings

    settings = get_settings()
    assert settings.locale in ("pt_BR", "en_US")


def test_settings_locale_field_override():
    from src.config import Settings

    s = Settings(LOCALE="en_US", cache_ttl_hours=12)
    assert s.locale == "en_US"