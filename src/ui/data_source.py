"""Widget compartilhado: seletor de fonte de dados com explicação."""

from __future__ import annotations

import streamlit as st


PROVIDER_OPTIONS = ("demo", "yfinance")


def format_provider_label(x: str) -> str:
    return (
        "Modo treino (rápido, dados simulados)"
        if x == "demo"
        else "Bolsa real (Yahoo Finance)"
    )


def render_provider_help() -> None:
    with st.expander("O que significa Modo treino vs Bolsa real?", icon=":material/help:"):
        st.markdown(
            """
| | **Modo treino** | **Bolsa real** |
|--|-----------------|----------------|
| **O que é** | Mercado **simulado** no app (números realistas, mas inventados) | Preços e (quando possível) fundamentals da B3 via **Yahoo Finance** |
| **Quando usar** | Aprender o fluxo, testar botões, primeira experiência | Experimentar com histórico mais próximo do mercado |
| **Velocidade** | Rápido / offline | Pode demorar e falhar (fonte gratuita) |
| **Limitação** | **Não** é a B3 de verdade | Dados incompletos às vezes; score fundamental do MVP ainda não é 100% histórico |

**Dica:** comece no **Modo treino**. Só mude para Bolsa real quando o fluxo já estiver claro.
"""
        )


def provider_selectbox(
    *,
    key: str,
    label: str = "Fonte de dados",
    default: str = "demo",
    show_help: bool = True,
) -> str:
    """Selectbox padrão + ajuda opcional logo abaixo (na sidebar)."""
    idx = 0 if default == "demo" else 1
    provider = st.selectbox(
        label,
        options=list(PROVIDER_OPTIONS),
        format_func=format_provider_label,
        index=idx,
        key=key,
        help=(
            "Modo treino = simulado e rápido. "
            "Bolsa real = Yahoo Finance (mais lento, dados de mercado)."
        ),
    )
    if show_help:
        render_provider_help()
    return provider  # type: ignore[return-value]
