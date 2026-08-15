"""Pacote: retry/backoff nas chamadas de rede (yfinance).

Valida o helper central: tenta de novo em erros retryáveis (rate-limit,
timeout, conexão), respeita o teto de tentativas e relança a última exceção
para o chamador decidir o fallback.
"""

from __future__ import annotations

import pytest

from src.data.yf_retry import (
    fetch_with_retry,
    is_retryable,
    set_retry_sleep,
)

set_retry_sleep(False)  # testes rápidos


class _RateLimited(RuntimeError):
    pass


def _flaky(failures_left, exc):
    calls = {"n": 0}

    def fn():
        calls["n"] += 1
        if calls["n"] <= failures_left:
            raise exc(f"n={calls['n']} — 429 Too Many Requests")
        return "ok"

    return calls, fn


@pytest.fixture(autouse=True)
def _sleep_off():
    set_retry_sleep(False)
    yield
    set_retry_sleep(False)


def test_is_retryable_known_cases():
    assert is_retryable(_RateLimited("too many requests"))
    assert is_retryable(Exception("HTTP 429"))
    assert is_retryable(TimeoutError("timed out"))
    # valores não-retryáveis (ex.: vazio) não devem entrar em loop
    assert is_retryable(ValueError("something is wrong")) is False


def test_retries_then_succeeds():
    calls, fn = _flaky(2, _RateLimited)
    assert fetch_with_retry(fn, max_attempts=4) == "ok"
    assert calls["n"] == 3  # 2 falhas + sucesso


def test_exhausts_and_raises():
    calls, fn = _flaky(5, _RateLimited)
    with pytest.raises(RuntimeError):
        fetch_with_retry(fn, max_attempts=3)
    assert calls["n"] == 3


def test_non_retryable_error_no_retry():
    calls = {"n": 0}

    def fn():
        calls["n"] += 1
        raise ValueError("bad data")

    with pytest.raises(ValueError):
        fetch_with_retry(fn, max_attempts=3)
    assert calls["n"] == 1