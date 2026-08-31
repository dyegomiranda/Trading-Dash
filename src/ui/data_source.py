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
    return "Números ilustrativos (testes)"


ALLOW_DEMO_KEY = "allow_demo_provider"


def get_session_provider() -> str:
    _apply_pending_provider()
    val = st.session_state.get(SESSION_PROVIDER_KEY)
    # Modo treino saiu da UI: sessões antigas em demo migram para a bolsa,
    # salvo testes/preflight que marcam allow_demo_provider.
    if val == "demo" and not st.session_state.get(ALLOW_DEMO_KEY):
        val = st.session_state.get(REAL_PROVIDER_KEY) or "yfinance"
        st.session_state[SESSION_PROVIDER_KEY] = val
        return str(val)
    if val in PROVIDER_OPTIONS:
        return str(val)
    st.session_state[SESSION_PROVIDER_KEY] = "yfinance"
    return "yfinance"


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


def get_provider_badge(provider: str) -> tuple[str, str]:
    """Retorna (texto_badge, tipo_badge) para o cabeçalho."""
    if provider == "demo":
        return ("Ilustrativo", "demo")
    elif provider == "brapi":
        return ("🔬 Brapi (B3)", "warn")
    return ("● Bolsa Real (B3)", "live")


def render_clean_header(
    title: str,
    subtitle: str = "",
    provider: str | None = None,
    extra_badges: list[tuple[str, str]] | None = None,
) -> None:
    """Renderiza o cabeçalho com badges de status integrados (substitui banners volumosos)."""
    from src.ui.components import render_page_header

    badges: list[tuple[str, str]] = []
    p = provider or get_session_provider()
    badges.append(get_provider_badge(p))
    if extra_badges:
        badges.extend(extra_badges)

    render_page_header(title, subtitle=subtitle, badges=badges)


def render_data_quality_banner(provider: str) -> None:
    """Caption curto sob o cabeçalho — o badge já diz a fonte."""
    if provider == "demo":
        st.caption(
            "Números ilustrativos (só testes/offline). No app o padrão é a bolsa real."
        )
    elif provider == "brapi":
        st.caption(
            "Fonte experimental da B3: quase não traz ROE nem dívida. Notas podem ficar incompletas."
        )
    else:
        st.caption(
            "Conta de treino com dinheiro fictício, usando preços e indicadores da bolsa."
        )


def render_global_mode_toggle() -> str:
    """Caption da fonte na barra — o dinheiro no app é sempre fictício."""
    provider = get_session_provider()
    if provider == "brapi":
        st.caption("Bolsa · fonte experimental B3")
    elif provider == "demo":
        st.caption("Números ilustrativos · só testes")
    else:
        st.caption("Bolsa real · Yahoo Finance")
    return provider


def render_sidebar_mode_footer() -> None:
    """Renderiza no rodapé da barra lateral: Toggle Modo Treino e botão Atualizar Dados logo abaixo."""
    st.divider()
    curr_prov = get_session_provider()
    is_demo = curr_prov == "demo"
    new_treino = st.toggle(
        "Modo treino",
        value=is_demo,
        key="sidebar_treino_toggle",
        help="Ligado: usa números ilustrativos offline para treino rápido. Desligado: usa dados reais da Bolsa (B3).",
    )
    if new_treino != is_demo:
        target = "demo" if new_treino else (st.session_state.get(REAL_PROVIDER_KEY) or "yfinance")
        st.session_state[ALLOW_DEMO_KEY] = new_treino
        st.session_state[SESSION_PROVIDER_KEY] = target
        st.session_state[PENDING_PROVIDER_KEY] = target
        st.rerun()

    from src.ui.cache_button import render_refresh_control

    render_refresh_control(key="sidebar_footer_refresh")



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
    """Texto do Guia: de onde vêm os números."""
    with st.container(border=True):
        st.markdown(":material/monitoring: **Bolsa real (Yahoo Finance)**")
        st.caption(
            "Preço, dividendo e indicadores de mercado. Podem atrasar, faltar ou divergir da CVM. "
            "O dinheiro da carteira continua fictício — você treina com dados reais, sem corretora."
        )
    with st.container(border=True):
        st.markdown(":material/science: **Fonte experimental da B3 (brapi.dev)**")
        st.caption(
            "A brapi junta dados da bolsa brasileira. No plano grátis entrega preço e dividendo, "
            "mas quase não traz ROE nem dívida — e a tese precisa desses dois. Opcional, em Configurações."
        )
