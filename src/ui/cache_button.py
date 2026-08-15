"""Botão de atualizar cache — sem imports de src no carregamento do módulo."""

from __future__ import annotations


def render_refresh_control(*, key: str, compact: bool = True) -> None:
    """Apaga o cache e busca números de novo. Import tardio evita ciclo no Streamlit."""
    import streamlit as st

    flash_key = f"{key}_flash"
    if st.session_state.pop(flash_key, False):
        st.toast("Cache limpo. A tela busca números novos agora.", icon=":material/check:")

    help_txt = (
        "Apaga os números guardados e busca de novo na fonte. "
        "Use se a lista parecer velha ou depois de mudar o modo treino."
    )
    clicked = st.button(
        "Atualizar dados",
        icon=":material/refresh:",
        width="stretch",
        key=key,
        help=help_txt,
    )
    if not compact:
        st.caption(help_txt)
    if clicked:
        from src.ui.refresh import force_refresh_data

        force_refresh_data()
        st.session_state[flash_key] = True
        st.rerun()
