"""Bootstrap compartilhado das páginas (tema, paths)."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

from src.ui.paths import ICON_PATH, LOGO_PATH, ROOT
from src.ui.theme import apply_theme


def ensure_root_on_path() -> None:
    root = str(ROOT)
    if root not in sys.path:
        sys.path.insert(0, root)


def inject_branding() -> None:
    """Logo grande na sidebar + favicon/logo nativo do Streamlit."""
    apply_theme()
    logo = str(LOGO_PATH) if LOGO_PATH.exists() else None
    icon = str(ICON_PATH) if ICON_PATH.exists() else None

    # Logo legível (st.logo sozinho fica pequeno demais)
    with st.sidebar:
        if logo:
            st.image(logo, width=220)
        elif icon:
            st.image(icon, width=96)
        st.markdown(
            "<div style='text-align:center;margin:-0.35rem 0 0.85rem 0;"
            "font-weight:700;letter-spacing:-0.02em;color:#E8EDF7;'>TradingDash</div>",
            unsafe_allow_html=True,
        )

    # Mantém ícone nativo (header / collapsed)
    if logo:
        try:
            st.logo(logo, icon_image=icon or logo, size="large")
        except Exception:
            try:
                st.logo(logo, size="large")
            except Exception:
                pass
    elif icon:
        try:
            st.logo(icon, size="large")
        except Exception:
            pass


def page_setup() -> None:
    """Chamado no início de cada página de conteúdo."""
    ensure_root_on_path()
    apply_theme()
