"""TradingDash — entrada multipage com sidebar custom (logo acima do menu)."""

from __future__ import annotations

import sys

import streamlit as st

from src.config import ROOT_DIR, get_settings

# Garante pastas graváveis (cache/carteiras) sem bloquear a UI na rede.
get_settings()

# --- Caminhos e configuração ---
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.ui.paths import ICON_PATH  # noqa: E402
from src.ui.shell import inject_branding, render_sidebar_nav, page_setup  # noqa: E402


_page_icon = str(ICON_PATH) if ICON_PATH.exists() else ":material/savings:"
st.set_page_config(
    page_title="TradingDash",
    page_icon=_page_icon,
    layout="wide",
    initial_sidebar_state="expanded",
)

inject_branding()
page_setup()

# Páginas na ordem do menu
page_inicio = st.Page(
    "app_pages/inicio.py",
    title="Início",
    icon=":material/home:",
    default=True,
)
page_descobrir = st.Page(
    "app_pages/descobrir_acoes.py",
    title="Descubra ações",
    icon=":material/travel_explore:",
)
page_carteira = st.Page(
    "app_pages/minha_carteira.py",
    title="Minha carteira",
    icon=":material/account_balance_wallet:",
)
page_sim = st.Page(
    "app_pages/teste_no_passado.py",
    title="Teste no passado",
    icon=":material/history:",
)
page_guia = st.Page(
    "app_pages/guia.py",
    title="Guia do iniciante",
    icon=":material/menu_book:",
)
page_config = st.Page(
    "app_pages/configuracoes.py",
    title="Configurações",
    icon=":material/settings:",
)

pages = [page_inicio, page_descobrir, page_carteira, page_sim, page_guia, page_config]

# Menu nativo oculto — montamos o menu manualmente (logo → links)
pg = st.navigation(pages, position="hidden")
render_sidebar_nav(pages)
pg.run()
