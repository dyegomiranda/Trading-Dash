"""Resolução de TTL por tipo de dado.

Centraliza a regra: kind → horas de validade do cache. Para a maioria dos
usos basta ``ttl_for(settings, "prices")``; a API pública deixa um override
explícito para testes e chamadas pontuais.
"""

from __future__ import annotations

from src.config import Settings, get_settings


def ttl_for(kind: str, settings: Settings | None = None, *, default: int | None = None) -> int:
    """Horas de TTL para um tipo de dado.

    Ordem de precedência: ``default`` explícito → override por tipo →
    ``cache_ttl_hours`` global.
    """
    if default is not None:
        return default
    st = settings or get_settings()
    overrides: dict[str, int] = dict(getattr(st, "cache_ttl_kind_hours", None) or {})
    if kind in overrides:
        return int(overrides[kind])
    return int(getattr(st, "cache_ttl_hours", 12) or 12)


__all__ = ["ttl_for"]