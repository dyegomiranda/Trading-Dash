"""Fonte de dados e ajustes globais da sessão (um estado para o app inteiro)."""

from __future__ import annotations

import streamlit as st

PROVIDER_OPTIONS = ("demo", "yfinance", "brapi")
SESSION_PROVIDER_KEY = "app_provider"
PENDING_PROVIDER_KEY = "pending_data_provider"
REAL_PROVIDER_KEY = "app_provider_real"
PENDING_TREINO_KEY = "pending_sidebar_treino"
SIDEBAR_TREINO_KEY = "sidebar_treino"
SESSION_MACRO_KEY = "app_macro"
APPLY_THESIS_LABEL = "Montar carteira com a tese"

MACRO_CHOICES = {
    "off": "Desligado",
    "auto": "Automático (Selic do Banco Central)",
    "restrictive": "Juros altos — mais defensivas",
    "expansionary": "Juros baixos — mais crescimento",
    "cautious": "Neutro / cauteloso",
}


def request_session_provider(name: str) -> None:
    """Marca a fonte para o próximo run, antes de qualquer widget nascer."""
    if name not in PROVIDER_OPTIONS:
        return
    st.session_state[PENDING_PROVIDER_KEY] = name
    st.session_state[PENDING_TREINO_KEY] = name == "demo"


def _apply_pending_provider() -> None:
    pending = st.session_state.pop(PENDING_PROVIDER_KEY, None)
    if pending in PROVIDER_OPTIONS:
        st.session_state[SESSION_PROVIDER_KEY] = pending
        if pending != "demo":
            st.session_state[REAL_PROVIDER_KEY] = pending
    pending_t = st.session_state.pop(PENDING_TREINO_KEY, None)
    if pending_t is not None:
        st.session_state[SIDEBAR_TREINO_KEY] = bool(pending_t)


def format_provider_label(x: str) -> str:
    if x == "yfinance":
        return "Bolsa real (Yahoo Finance)"
    if x == "brapi":
        return "Experimental — dados da B3 (brapi.dev)"
    return "Modo treino (números ilustrativos)"


def get_session_provider() -> str:
    _apply_pending_provider()
    val = st.session_state.get(SESSION_PROVIDER_KEY)
    if val in PROVIDER_OPTIONS:
        return str(val)
    st.session_state[SESSION_PROVIDER_KEY] = "demo"
    return "demo"


def get_session_macro() -> str:
    val = st.session_state.get(SESSION_MACRO_KEY)
    if val in MACRO_CHOICES:
        return str(val)
    try:
        from src.config import get_settings

        env = str(getattr(get_settings(), "macro_override", "off") or "off")
        if env in MACRO_CHOICES:
            return env
    except Exception:
        pass
    return "off"


def render_data_quality_banner(provider: str) -> None:
    if provider == "demo":
        st.info(
            "**Modo treino.** As notas e os indicadores são ilustrativos. "
            "Desligue o interruptor **Modo treino** na barra para usar a bolsa.",
            icon=":material/school:",
        )
    elif provider == "brapi":
        st.warning(
            "**Fonte experimental da B3.** Tem preço e dividendo; quase não traz "
            "ROE nem dívida. A nota de qualidade fica incompleta.",
            icon=":material/science:",
        )
    else:
        st.caption(
            "Bolsa real (Yahoo). Números gratuitos — podem atrasar ou faltar. "
            "Valide fora do app antes de qualquer decisão."
        )


def render_global_mode_toggle() -> str:
    """Interruptor único na barra — vale em todas as páginas."""
    _apply_pending_provider()
    current = get_session_provider()
    if SIDEBAR_TREINO_KEY not in st.session_state:
        st.session_state[SIDEBAR_TREINO_KEY] = current == "demo"

    treino = st.toggle(
        "Modo treino",
        key=SIDEBAR_TREINO_KEY,
        help="Ligado: números ilustrativos para aprender. "
        "Desligado: preços e indicadores da bolsa (Yahoo).",
    )
    if treino and current != "demo":
        request_session_provider("demo")
        st.rerun()
    if not treino and current == "demo":
        request_session_provider(st.session_state.get(REAL_PROVIDER_KEY) or "yfinance")
        st.rerun()

    provider = get_session_provider()
    if provider == "demo":
        st.caption("Números de estudo · não são da bolsa")
    elif provider == "brapi":
        st.caption("Bolsa · fonte experimental B3")
    else:
        st.caption("Bolsa real · Yahoo Finance")
    return provider


def render_refresh_control(*, key: str, compact: bool = True) -> None:
    """Reexporta o controle de cache — implementação em ``src.ui.refresh``."""
    from src.ui.refresh import render_refresh_control as _render

    _render(key=key, compact=compact)


def provider_selectbox(
    *,
    key: str = SESSION_PROVIDER_KEY,
    label: str = "Fonte de dados",
    default: str = "demo",
    show_help: bool = True,
) -> str:
    """Compat: a fonte agora é global. Páginas devem só ler get_session_provider()."""
    del key, label, default, show_help
    return get_session_provider()


def macro_selectbox() -> str:
    if SESSION_MACRO_KEY not in st.session_state:
        st.session_state[SESSION_MACRO_KEY] = get_session_macro()
    return st.selectbox(
        "Como os juros inclinham a carteira",
        options=list(MACRO_CHOICES.keys()),
        format_func=lambda k: MACRO_CHOICES[k],
        key=SESSION_MACRO_KEY,
        help="Não cria nem tira ações — só muda um pouco o peso de cada setor.",
    )


def render_sources_guide() -> None:
    """Texto do Guia: o que é cada fonte, em linguagem de leigo."""
    c1, c2 = st.columns(2)
    with c1, st.container(border=True):
        st.markdown(":material/school: **Modo treino**")
        st.caption("Números inventados, estáveis, para aprender os botões. Nunca para dinheiro real.")
    with c2, st.container(border=True):
        st.markdown(":material/monitoring: **Bolsa real**")
        st.caption("Preço e indicadores do Yahoo. Podem atrasar, faltar ou divergir da CVM.")
    with st.container(border=True):
        st.markdown(":material/science: **Fonte experimental da B3 (brapi.dev)**")
        st.caption(
            "A brapi é uma empresa que junta dados da bolsa brasileira. "
            "No plano grátis ela entrega preço e dividendo, mas quase não traz "
            "ROE nem dívida — e a tese precisa desses dois. Por isso é opcional "
            "e fica em Configurações, não no interruptor principal."
        )
