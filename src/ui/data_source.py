"""Widget compartilhado: seletor de fonte de dados com explicação."""

from __future__ import annotations

import streamlit as st


PROVIDER_OPTIONS = ("yfinance", "demo")  # bolsa real primeiro (mais sério)


def format_provider_label(x: str) -> str:
    return (
        "Bolsa real (Yahoo Finance — preferível)"
        if x == "yfinance"
        else "Modo treino (NÃO usar para decisão real)"
    )


def render_provider_help() -> None:
    with st.expander("O que significa cada fonte de dados?", icon=":material/help:"):
        st.markdown(
            """
| | **Bolsa real (Yahoo)** | **Modo treino** |
|--|------------------------|-----------------|
| **Nome e setor** | Mercado (com fallback no cadastro B3 local) | Cadastro B3 local (não inventa setor) |
| **Preços / indicadores** | Yahoo Finance (podem atrasar ou falhar) | **Números sintéticos** (fictícios) |
| **Quando usar** | Análise e simulação com cara de mercado | Só aprender a interface / testar botões |
| **Dinheiro real?** | Ainda **não** é consultoria; valide fora do app | **Nunca** para decidir compra/venda real |

**Importante:** mesmo na Bolsa real, o Yahoo é gratuito e **imperfeito**. Tickers renomeados
(ex.: ELET3 → AXIA3) e gaps de dados exigem checagem. O app **não substitui** Status Invest,
Fundamentus, RI da empresa ou um profissional habilitado.
"""
        )


def render_data_quality_banner(provider: str) -> None:
    """Aviso forte no topo da página conforme a fonte."""
    if provider == "demo":
        st.error(
            "**Modo treino ativo:** indicadores (ROE, DY, P/L, scores, rankings) são "
            "**sintéticos/fictícios**. Nome e setor vêm do cadastro de referência, mas "
            "**não use esta tela para colocar dinheiro real.** Mude para **Bolsa real**.",
            icon=":material/dangerous:",
        )
    else:
        st.warning(
            "**Bolsa real (Yahoo Finance):** dados de mercado gratuitos — podem estar "
            "atrasados, incompletos ou divergir de fontes oficiais. Use como apoio, "
            "não como única fonte de verdade. Valide no site de RI / CVM / casa de análise.",
            icon=":material/info:",
        )


def provider_selectbox(
    *,
    key: str,
    label: str = "Fonte de dados",
    default: str = "yfinance",
    show_help: bool = True,
) -> str:
    """Selectbox padrão + ajuda opcional. Default = bolsa real."""
    opts = list(PROVIDER_OPTIONS)
    idx = opts.index(default) if default in opts else 0
    provider = st.selectbox(
        label,
        options=opts,
        format_func=format_provider_label,
        index=idx,
        key=key,
        help=(
            "Bolsa real = Yahoo + cadastro B3. "
            "Modo treino = indicadores fictícios (só UI)."
        ),
    )
    if show_help:
        render_provider_help()
    return provider  # type: ignore[return-value]
