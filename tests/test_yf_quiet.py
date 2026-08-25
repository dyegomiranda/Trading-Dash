"""Filtro do logger yfinance: não vaza 'possibly delisted' no terminal."""

from __future__ import annotations

import logging

from src.data.yf_quiet import _DropDelisted, silence_yfinance


def test_drop_delisted_filter():
    f = _DropDelisted()
    rec = logging.LogRecord(
        "yfinance", logging.ERROR, __file__, 1,
        "$LAME3.SA: possibly delisted; no timezone found", (), None,
    )
    assert f.filter(rec) is False
    ok = logging.LogRecord(
        "yfinance", logging.ERROR, __file__, 1, "connection timed out", (), None,
    )
    assert f.filter(ok) is True


def test_silence_yfinance_is_idempotent():
    silence_yfinance()
    silence_yfinance()
    assert logging.getLogger("yfinance").level == logging.CRITICAL
