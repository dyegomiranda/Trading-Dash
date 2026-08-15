"""Configuração compartilhada dos testes."""

from __future__ import annotations

import shutil

import pytest

from src.config import CACHE_DIR


@pytest.fixture(autouse=True)
def _clear_cache():
    """Limpa o cache em disco antes de cada teste.

    Os providers usam _read_cache/_write_cache em CACHE_DIR; sem limpeza,
    um teste que grava um payload de mock pode "envenenar" outro teste que
    espere chamadas de rede (side_effect) ou requeira dados frescos.
    """
    if CACHE_DIR.exists():
        shutil.rmtree(CACHE_DIR, ignore_errors=True)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    yield
    if CACHE_DIR.exists():
        shutil.rmtree(CACHE_DIR, ignore_errors=True)