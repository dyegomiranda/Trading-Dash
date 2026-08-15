"""Retry/backoff para chamadas de rede do yfinance.

Yahoo encara volume como rate-limit (HTTP 429 / `Too Many Requests`) e, às vezes,
derruba conexões. Aqui centralizamos uma política simples e honesta:

- tenta até ``max_attempts`` vezes
- espera exponencial com jitter (evita "thundering herd" entre workers)
- só re-levanta a exceção depois de esgotar as tentativas (quem chamou decide
  o fallback)
- em ambiente de teste a espera real pode ser zerada (viva a IA que testa)

Uso:

    raw = fetch_with_retry(lambda: yf.download(...), what="preços Yahoo")

Sem dependência externa (tenacity está no requirements, mas a semântica aqui
é explícita demais para um decorator genérico — queremos mensagem PT e limite
por chamada).
"""

from __future__ import annotations

import random
import time
from typing import Any, Callable, TypeVar

T = TypeVar("T")

# tenta até 3x; depois disso devolve o erro pro chamador decidir fallback
DEFAULT_MAX_ATTEMPTS = 3
DEFAULT_BASE_DELAY = 1.0
DEFAULT_MAX_DELAY = 8.0

# Falso → testes não ficam lentos; não use em produção.
_RETRY_SLEEP_ENABLED = True


def set_retry_sleep(enabled: bool) -> None:
    """Liga/desliga o ``time.sleep`` real (testes)."""
    global _RETRY_SLEEP_ENABLED  # noqa: PLW0603
    _RETRY_SLEEP_ENABLED = enabled


def _delay_for(attempt: int, base: float, cap: float) -> float:
    exp = min(cap, base * (2 ** (attempt - 1)))
    # jitter 0.5–1.0 × exponencial
    return random.uniform(0.5, 1.0) * exp


def is_retryable(exc: BaseException) -> bool:
    """Erros de rede/rate-limit que valem nova tentativa."""
    name = type(exc).__name__.lower()
    msg = str(exc).lower()
    if any(k in msg for k in ("too many requests", "rate limit", "429", "timeout", "timed out")):
        return True
    if any(k in name for k in ("timeout", "connectionerror", "httperror", "oserror")):
        return True
    return False


def fetch_with_retry(
    fn: Callable[[], T],
    *,
    what: str = "dados Yahoo",
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    base_delay: float = DEFAULT_BASE_DELAY,
    max_delay: float = DEFAULT_MAX_DELAY,
) -> T:
    """Executa ``fn`` com backoff exponencial + jitter.

    A última exceção é relançada para o chamador tomar a decisão de fallback.
    """
    attempt = 0
    while True:
        attempt += 1
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001 — pegamos rede, HTTP, JSON…
            if attempt >= max_attempts or not is_retryable(exc):
                raise
            delay = _delay_for(attempt, base_delay, max_delay)
            if _RETRY_SLEEP_ENABLED:
                time.sleep(delay)
            # log leve (sem depender de logging configurado no app)
            import sys

            print(
                f"[yf-retry] {what}: tentativa {attempt}/{max_attempts} falhou "
                f"({type(exc).__name__}: {exc}); aguardando {delay:.1f}s.",
                file=sys.stderr,
            )


__all__ = [
    "fetch_with_retry",
    "is_retryable",
    "set_retry_sleep",
    "DEFAULT_MAX_ATTEMPTS",
    "DEFAULT_BASE_DELAY",
    "DEFAULT_MAX_DELAY",
]