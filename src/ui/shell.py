"""Bootstrap compartilhado das páginas (tema, paths)."""

from __future__ import annotations

import base64
import sys
from pathlib import Path

import streamlit as st

from src.ui.paths import ICON_PATH, LOGO_PATH, ROOT
from src.ui.theme import apply_theme

# Cor de borda do logo TD (~RGB 8,7,20) para blend com a sidebar
LOGO_BG = "#080714"


def ensure_root_on_path() -> None:
    root = str(ROOT)
    if root not in sys.path:
        sys.path.insert(0, root)


def _logo_data_uri() -> str | None:
    path = LOGO_PATH if LOGO_PATH.exists() else (ICON_PATH if ICON_PATH.exists() else None)
    if path is None or not path.exists():
        return None
    mime = "image/png"
    b64 = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{b64}"


def inject_branding() -> None:
    """Um único logo grande no topo da sidebar, fundido ao fundo (sem st.logo)."""
    apply_theme()
    uri = _logo_data_uri()

    # CSS: esconde qualquer logo nativo residual + fundo da sidebar = cor do logo
    hide_native = """
<style>
/* Remove o logo nativo pequeno do Streamlit (st.logo / header da nav) */
[data-testid="stSidebarHeader"],
[data-testid="stLogo"],
[data-testid="stSidebar"] [data-testid="stLogoLink"],
div[data-testid="stSidebarContent"] > div:has(> [data-testid="stLogo"]),
[data-testid="stSidebar"] a[href="/"] img {
  display: none !important;
  height: 0 !important;
  margin: 0 !important;
  padding: 0 !important;
  overflow: hidden !important;
}

/* Sidebar na mesma cor do fundo do logo */
[data-testid="stSidebar"],
[data-testid="stSidebar"] > div,
section[data-testid="stSidebar"] > div {
  background: #080714 !important;
  background-color: #080714 !important;
}

[data-testid="stSidebarNav"] {
  background: transparent !important;
  padding-top: 0.25rem !important;
}

/* Bloco do logo no topo */
.td-sidebar-brand {
  display: block;
  width: 100%;
  margin: 0 0 0.75rem 0;
  padding: 1.1rem 1rem 0.35rem 1rem;
  background: #080714;
  text-align: center;
  box-sizing: border-box;
}
.td-sidebar-brand img {
  width: min(100%, 240px);
  height: auto;
  display: block;
  margin: 0 auto;
  background: #080714;
  border: none;
  outline: none;
  box-shadow: none;
}
</style>
"""
    st.markdown(hide_native, unsafe_allow_html=True)

    if uri:
        # Inserido na sidebar no início do script — aparece acima dos controles das páginas
        st.sidebar.markdown(
            f'<div class="td-sidebar-brand"><img src="{uri}" alt="TradingDash" /></div>',
            unsafe_allow_html=True,
        )


def page_setup() -> None:
    """Chamado no início de cada página de conteúdo."""
    ensure_root_on_path()
    apply_theme()
