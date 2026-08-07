"""TradingDash — entrada multipage com navegação estilizada."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.ui.paths import ICON_PATH, LOGO_PATH
from src.ui.shell import inject_branding

# set_page_config deve ser a primeira chamada Streamlit do entrypoint
_page_icon = str(ICON_PATH) if ICON_PATH.exists() else ":material/savings:"
st.set_page_config(
    page_title="TradingDash",
    page_icon=_page_icon,
    layout="wide",
    initial_sidebar_state="expanded",
)

inject_branding()

pages = {
    "Menu": [
        st.Page(
            "app_pages/inicio.py",
            title="Início",
            icon=":material/home:",
            default=True,
        ),
        st.Page(
            "app_pages/descobrir_acoes.py",
            title="Descubra ações",
            icon=":material/travel_explore:",
        ),
        st.Page(
            "app_pages/minha_carteira.py",
            title="Minha carteira",
            icon=":material/account_balance_wallet:",
        ),
        st.Page(
            "app_pages/teste_no_passado.py",
            title="Teste no passado",
            icon=":material/history:",
        ),
        st.Page(
            "app_pages/guia.py",
            title="Guia do iniciante",
            icon=":material/menu_book:",
        ),
    ]
}

pg = st.navigation(pages, position="sidebar")
pg.run()
