"""Silencia o spam do yfinance no terminal.

Yahoo registra ERROR para ticker sem calendário (`possibly delisted; no timezone found`).
Isso é esperado para papéis que saíram da B3 ou que o Yahoo não cobre — não é falha do app.
"""

from __future__ import annotations

import logging
import warnings

_SILENCED = False


class _DropDelisted(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage().lower()
        if "possibly delisted" in msg or "no timezone found" in msg:
            return False
        if "no price data found" in msg:
            return False
        return "failed download" not in msg


def silence_yfinance() -> None:
    global _SILENCED
    if _SILENCED:
        return
    _SILENCED = True
    warnings.filterwarnings("ignore", message=r".*possibly delisted.*")
    warnings.filterwarnings("ignore", message=r".*no timezone found.*")
    warnings.filterwarnings("ignore", message=r".*no price data found.*")
    log = logging.getLogger("yfinance")
    log.setLevel(logging.CRITICAL)
    log.addFilter(_DropDelisted())
    for name in ("yfinance.utils", "yfinance.scrapers", "yfinance.data", "yfinance.multi"):
        child = logging.getLogger(name)
        child.setLevel(logging.CRITICAL)
        child.addFilter(_DropDelisted())
