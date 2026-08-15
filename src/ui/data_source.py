"""Widget compartilhado: seletor de fonte de dados com explicação."""

from __future__ import annotations

import streamlit as st

# Primeira visita = treino. brapi fica experimental (sem ROE/dívida no plano grátis).
PROVIDER_OPTIONS = ("demo", "yfinance")
SESSION_PROVIDER_KEY = "data_provider"
PENDING_PROVIDER_KEY = "pending_data_provider"
SESSION_MACRO_KEY = "macro_override"
APPLY_THESIS_LABEL = "Montar carteira com a tese"


def request_session_provider(name: str) -> None:
    """Pede troca de fonte no *próximo* run, antes do selectbox nascer.

    Não escreve em ``data_provider`` depois que o widget existe — isso
    levanta StreamlitAPIException.
    """
    if name in ("demo", "yfinance", "brapi"):
        st.session_state[PENDING_PROVIDER_KEY] = name


def _apply_pending_provider() -> None:
    pending = st.session_state.pop(PENDING_PROVIDER_KEY, None)
    if pending in ("demo", "yfinance", "brapi"):
        st.session_state[SESSION_PROVIDER_KEY] = pending


def format_provider_label(x: str) -> str:
    if x == "yfinance":
        return "Bolsa real (Yahoo Finance)"
    if x == "brapi":
        return "Experimental — brapi.dev (sem ROE/dívida)"
    return "Modo treino (números ilustrativos)"


def get_session_provider() -> str:
    val = st.session_state.get(SESSION_PROVIDER_KEY)
    if val in ("demo", "yfinance", "brapi"):
        return str(val)
    return "demo"


def get_session_macro() -> str:
    val = st.session_state.get(SESSION_MACRO_KEY)
    if val in ("off", "auto", "expansionary", "cautious", "restrictive"):
        return str(val)
    try:
        from src.config import get_settings

        env = str(getattr(get_settings(), "macro_override", "off") or "off")
        if env in ("off", "auto", "expansionary", "cautious", "restrictive"):
            return env
    except Exception:
        pass
    return "off"


def render_provider_help() -> None:
    with st.expander("O que significa cada fonte de dados?", icon=":material/help:"):
        st.markdown(
            """
| | **Modo treino** | **Bolsa real (Yahoo)** |
|--|-----------------|------------------------|
| **Nome e setor** | Cadastro B3 local (não inventa setor) | Mercado + cadastro B3 |
| **Preços / indicadores** | **Números sintéticos** (fictícios) | Yahoo Finance (podem atrasar ou falhar) |
| **Quando usar** | Aprender a interface e a tese | Estudar com cara de mercado |
| **Dinheiro real?** | **Nunca** | Ainda **não** é consultoria; valide fora |

**brapi.dev** (experimental) tem preço e dividendo, mas **quase não traz ROE nem dívida** —
a nota de qualidade fica incompleta. Por isso não aparece no seletor principal.

O app **não substitui** Status Invest, Fundamentus, RI da empresa ou um profissional habilitado.
"""
        )


def render_data_quality_banner(provider: str) -> None:
    """Aviso forte no topo da página conforme a fonte."""
    if provider == "demo":
        st.error(
            "**Modo treino ativo:** indicadores (ROE, DY, P/L, notas) são "
            "**sintéticos/fictícios**. Nome e setor vêm do cadastro B3, mas "
            "**não use esta tela para colocar dinheiro real.** "
            "Quando quiser números de mercado, mude para **Bolsa real**.",
            icon=":material/dangerous:",
        )
    elif provider == "brapi":
        st.warning(
            "**Fonte experimental (brapi.dev):** preços e dividendos B3, mas o plano "
            "gratuito **não traz ROE nem dívida**. A nota de qualidade fica incompleta. "
            "Prefira Yahoo para estudar a tese.",
            icon=":material/science:",
        )
    else:
        st.warning(
            "**Bolsa real (Yahoo Finance):** dados gratuitos — podem estar "
            "atrasados, incompletos ou divergir de fontes oficiais. Use como apoio, "
            "não como única fonte de verdade.",
            icon=":material/info:",
        )


def provider_selectbox(
    *,
    key: str = SESSION_PROVIDER_KEY,
    label: str = "Fonte de dados",
    default: str = "demo",
    show_help: bool = True,
) -> str:
    """Uma fonte por sessão — o `key` por página é ignorado de propósito."""
    del key
    _apply_pending_provider()
    if SESSION_PROVIDER_KEY not in st.session_state:
        st.session_state[SESSION_PROVIDER_KEY] = default

    opts = list(PROVIDER_OPTIONS)
    show_brapi = bool(st.session_state.get("show_brapi"))
    current = st.session_state.get(SESSION_PROVIDER_KEY, default)
    if show_brapi or current == "brapi":
        opts = opts + ["brapi"]
    if current not in opts:
        st.session_state[SESSION_PROVIDER_KEY] = default

    provider = st.selectbox(
        label,
        options=opts,
        format_func=format_provider_label,
        key=SESSION_PROVIDER_KEY,
        help=(
            "Modo treino = interface e tese, com números fictícios. "
            "Bolsa real = Yahoo. A escolha vale em todas as páginas."
        ),
    )
    with st.expander("Fonte experimental (brapi.dev)", icon=":material/science:"):
        st.checkbox(
            "Mostrar brapi no seletor (incompleto para a tese)",
            key="show_brapi",
            help="Sem ROE/dívida no plano gratuito. Não use para a nota de qualidade.",
        )
        st.caption(
            "Mantemos a opção só para quem quer cruzar preço/dividendo B3. "
            "Não é a fonte principal."
        )
    if show_help:
        render_provider_help()
    return provider  # type: ignore[return-value]


def macro_selectbox() -> str:
    """Regime macro compartilhado na sessão (Descubra e carteira usam o mesmo)."""
    choices = {
        "off": "Desligado (sem inclinação setorial)",
        "auto": "Automático (meta Selic / IPCA do Banco Central)",
        "restrictive": "Manual — juros altos (mais defensivas)",
        "expansionary": "Manual — juros baixos (mais crescimento)",
        "cautious": "Manual — neutro/cauteloso",
    }
    if SESSION_MACRO_KEY not in st.session_state:
        st.session_state[SESSION_MACRO_KEY] = get_session_macro()
    return st.selectbox(
        "Regime macro",
        options=list(choices.keys()),
        format_func=lambda k: choices[k],
        key=SESSION_MACRO_KEY,
        help=(
            "Opcional: reorienta os pesos sugeridos conforme o ciclo de juros. "
            "Vale na lista e em Montar carteira com a tese. Não cria nem exclui nomes."
        ),
    )
