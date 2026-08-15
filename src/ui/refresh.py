"""Refresh centralizado — evita `st.cache_data.clear()` solto em cada página.

Dois níveis, para não pagar re-fetch desnecessário:

- ``force_refresh_data`` — botão "Atualizar dados" dos usuários: apaga o cache
  em memória (``cache_data``/``cache_resource``) **e** o cache em disco
  (``data/cache/*.json`` via ``providers.clear_disk_cache``), forçando busca
  nova de mercado (ignora o TTL).
- ``soft_refresh`` — após operações locais (montar carteira, rebalancear):
  apaga só o cache em memória, mantendo o disco (TTL respeitado). Não há
  necessidade de re-buscar mercado para uma ação local.

Ambos registram quantos arquivos foram limpos (observabilidade) e, ao servir
a UI, nunca quebram a página.
"""

from __future__ import annotations

import contextlib

from src.data.providers import clear_disk_cache


def _report(op: str, *, removed: int) -> None:
    try:
        from src.monitoring import write_event

        write_event({"op": op, "disk_files_removed": removed})
    except Exception:
        pass


def soft_refresh() -> None:
    """Limpa os caches em memória do Streamlit (sem tocar o disco)."""
    import streamlit as st

    try:
        st.cache_data.clear()
        st.cache_resource.clear()
    except Exception:
        pass


def force_refresh_data() -> None:
    """Refresh completo: memória + disco (mercado com dados novos sempre)."""
    removed = 0
    with contextlib.suppress(Exception):
        removed = clear_disk_cache()
    soft_refresh()
    _report("refresh.force", removed=removed)