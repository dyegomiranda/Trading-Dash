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
    _wipe_provider_cache()
    yield
    _wipe_provider_cache()


def _wipe_provider_cache() -> None:
    """Apaga JSON de cotação; preserva data/cache/cvm (ZIPs pesados da CVM)."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    for p in CACHE_DIR.iterdir():
        if p.name == "cvm":
            continue
        if p.is_dir():
            shutil.rmtree(p, ignore_errors=True)
        else:
            p.unlink(missing_ok=True)