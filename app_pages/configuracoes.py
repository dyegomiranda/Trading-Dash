"""Configurações — ajustes que valem no app inteiro."""

from __future__ import annotations

import streamlit as st

from src.ui.components import render_page_header
from src.ui.data_source import (
    MACRO_CHOICES,
    get_session_macro,
    get_session_provider,
    request_session_provider,
)
from src.ui.refresh import render_refresh_control
from src.ui.shell import page_setup
from src.thesis.macro import macro_header_info

page_setup()
render_page_header("Configurações", "Um lugar só para os ajustes do programa")

provider = get_session_provider()
treino = provider == "demo"

st.markdown("##### De onde vêm os números")
c1, c2 = st.columns(2)
with c1, st.container(border=True):
    st.markdown(":material/school: **Modo treino**")
    st.caption("Números ilustrativos para aprender. Sem espera da bolsa.")
    if st.button(
        "Usar modo treino",
        type="primary" if treino else "secondary",
        width="stretch",
        key="cfg_treino",
        disabled=treino,
    ):
        request_session_provider("demo")
        st.rerun()
with c2, st.container(border=True):
    st.markdown(":material/monitoring: **Bolsa real**")
    st.caption("Preço e indicadores do Yahoo. Podem atrasar ou faltar.")
    if st.button(
        "Usar bolsa real",
        type="primary" if not treino else "secondary",
        width="stretch",
        key="cfg_bolsa",
        disabled=not treino and provider == "yfinance",
    ):
        request_session_provider("yfinance")
        st.rerun()

st.caption("O interruptor **Modo treino** na barra faz a mesma coisa — vale em todas as páginas.")

st.markdown("##### Fonte extra da B3 (opcional)")
with st.container(border=True):
    left, right = st.columns([1.4, 1], gap="large")
    with left:
        st.markdown(":material/science: **brapi.dev**")
        st.caption(
            "Empresa que junta dados da bolsa brasileira. "
            "No plano grátis: preço e dividendo. Quase sem ROE nem dívida — "
            "a nota de qualidade da tese fica pela metade."
        )
        if treino:
            st.caption("Desligue o modo treino para escolher esta fonte.")
        elif provider == "brapi":
            if st.button("Voltar para Yahoo", width="stretch", key="cfg_brapi_off"):
                request_session_provider("yfinance")
                st.rerun()
        else:
            if st.button("Ativar fonte B3", width="stretch", key="cfg_brapi_on"):
                request_session_provider("brapi")
                st.rerun()
    with right:
        if treino:
            st.caption("Modo treino manda agora.")
        elif provider == "brapi":
            st.success("Ativa agora", icon=":material/science:")
        else:
            st.caption("Desligada · o app usa Yahoo")

st.markdown("##### Juros e setores")
with st.container(border=True):
    st.caption(
        "Quando os juros estão altos, o app pode dar um pouco mais de peso "
        "a setores mais estáveis (energia, bancos). Quando estão baixos, "
        "um pouco mais a crescimento. **Não cria nem tira ações** — só inclina."
    )
    if "cfg_macro_pills" not in st.session_state:
        st.session_state["cfg_macro_pills"] = get_session_macro()
    picked = st.pills(
        "Inclinação",
        options=list(MACRO_CHOICES.keys()),
        format_func=lambda k: MACRO_CHOICES[k],
        key="cfg_macro_pills",
    )
    if picked:
        st.session_state["app_macro"] = picked
    macro = get_session_macro()
    if macro == "off":
        st.caption("Sem inclinação. A carteira segue só a tese.")
    else:
        info = macro_header_info(macro)
        st.caption(info.get("label") or "")
        if info.get("detail"):
            st.caption(info["detail"])

st.markdown("##### Números guardados")
with st.container(border=True):
    st.caption(
        "O app guarda preços e indicadores por algumas horas para não travar. "
        "Se a lista parecer antiga, peça números novos."
    )
    render_refresh_control(key="cfg_refresh", compact=False)
