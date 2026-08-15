"""Pacote: TTL por tipo de dado no cache.

Valida que o resolver central (``ttl_for``) decide a validade por tipo e que
preços/brapi quotes vencem mais rápido que benchmarks.
"""

from __future__ import annotations

from src.config import Settings
from src.data.ttl import ttl_for


def _settings(**kw) -> Settings:
    base = dict(
        cache_ttl_hours=12,
        cache_ttl_kind_hours={
            "benchmark": 24,
            "macro": 6,
            "fundamentals": 12,
            "prices": 6,
            "dividends": 24,
            "brapi_quote": 6,
        },
    )
    base.update(kw)
    return Settings(**base)


def test_kind_override_wins():
    s = _settings()
    assert ttl_for("prices", s) == 6
    assert ttl_for("benchmark", s) == 24
    assert ttl_for("fundamentals", s) == 12


def test_unknown_kind_falls_back_global():
    s = _settings()
    assert ttl_for("news_feed", s) == 12  # sem override → cache_ttl_hours


def test_explicit_default_beats_override():
    s = _settings()
    assert ttl_for("prices", s, default=99) == 99


def test_returns_int():
    s = _settings()
    assert isinstance(ttl_for("prices", s), int)