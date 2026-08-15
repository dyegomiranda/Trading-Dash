"""Utilidades comuns: timestamps, datas e formatação.

Centraliza helpers de tempo para evitar ``datetime.utcnow()`` (deprecado
em Python 3.12+) e fornece formatadores reutilizados pelo app.
"""

from __future__ import annotations

from datetime import datetime, timezone


def utcnow() -> datetime:
    """Datetime atual em UTC com timezone (substituto de ``utcnow()``)."""
    return datetime.now(timezone.utc)


def utcnow_iso() -> str:
    """Timestamp atual em UTC ISO 8601 (ex.: ``2026-08-14T18:00:00+00:00``)."""
    return utcnow().isoformat()


def utcnow_date() -> str:
    """Data atual em UTC no formato YYYY-MM-DD."""
    return utcnow().date().isoformat()


def utcnow_stamp() -> str:
    """Data/hora UTC legível (ex.: ``2026-08-14 18:00 UTC``)."""
    return utcnow().strftime("%Y-%m-%d %H:%M UTC")