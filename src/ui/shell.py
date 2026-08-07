"""Bootstrap compartilhado das páginas (tema, paths)."""

from __future__ import annotations

import base64
import sys
from pathlib import Path

import streamlit as st

from src.ui.paths import ICON_PATH, LOGO_PATH, ROOT
from src.ui.theme import apply_theme

# Cor de borda do logo TD (~RGB 8,7,20)
LOGO_BG = "#080714"


def ensure_root_on_path() -> None:
    root = str(ROOT)
    if root not in sys.path:
        sys.path.insert(0, root)


def _logo_data_uri() -> str | None:
    path = LOGO_PATH if LOGO_PATH.exists() else (ICON_PATH if ICON_PATH.exists() else None)
    if path is None or not path.exists():
        return None
    b64 = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{b64}"


def inject_branding() -> None:
    """Logo grande **acima** do menu de navegação (CSS no stSidebarNav).

    O st.navigation renderiza o menu no topo da sidebar; conteúdo via st.sidebar
    fica *abaixo*. Por isso o logo é injetado como ::before do nav.
    """
    apply_theme()
    uri = _logo_data_uri()
    bg = uri or "none"

    st.markdown(
        f"""
<style>
/* Remove logo nativo pequeno do Streamlit */
[data-testid="stSidebarHeader"],
[data-testid="stLogo"],
[data-testid="stSidebar"] [data-testid="stLogoLink"],
[data-testid="stSidebar"] a[href="/"] > img {{
  display: none !important;
  height: 0 !important;
  min-height: 0 !important;
  max-height: 0 !important;
  margin: 0 !important;
  padding: 0 !important;
  overflow: hidden !important;
  opacity: 0 !important;
  pointer-events: none !important;
}}

/* Sidebar na cor do fundo do logo */
[data-testid="stSidebar"],
[data-testid="stSidebar"] > div,
[data-testid="stSidebarContent"],
[data-testid="stSidebarUserContent"] {{
  background: {LOGO_BG} !important;
  background-color: {LOGO_BG} !important;
}}

/* Logo ACIMA dos itens do menu */
[data-testid="stSidebarNav"] {{
  background: {LOGO_BG} !important;
  padding-top: 0 !important;
  margin-top: 0 !important;
}}

[data-testid="stSidebarNav"]::before {{
  content: "";
  display: block;
  width: 100%;
  height: 150px;
  margin: 0.35rem 0 0.85rem 0;
  padding: 0;
  box-sizing: border-box;
  background-color: {LOGO_BG};
  background-image: url("{bg}");
  background-repeat: no-repeat;
  background-position: center top;
  background-size: contain;
}}

/* Lista do menu logo abaixo do logo */
[data-testid="stSidebarNav"] ul {{
  margin-top: 0 !important;
}}

/* Remove bloco antigo de logo em st.sidebar (se existir em cache visual) */
.td-sidebar-brand {{
  display: none !important;
}}
</style>
""",
        unsafe_allow_html=True,
    )


def page_setup() -> None:
    """Chamado no início de cada página de conteúdo."""
    ensure_root_on_path()
    apply_theme()
