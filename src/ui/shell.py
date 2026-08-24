"""Bootstrap compartilhado das páginas (tema, paths, sidebar)."""

from __future__ import annotations

import base64
import sys
from collections.abc import Sequence

import streamlit as st

from src.ui.paths import ICON_PATH, LOGO_PATH, ROOT
from src.ui.theme import apply_theme

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
    """Apenas CSS de fundo / esconde chrome nativo. Logo vem em render_sidebar_nav."""
    apply_theme()
    st.markdown(
        f"""
<style>
/* Esconde logo nativo e header residual */
[data-testid="stSidebarHeader"],
[data-testid="stLogo"],
[data-testid="stSidebar"] [data-testid="stLogoLink"] {{
  display: none !important;
  height: 0 !important;
  min-height: 0 !important;
  overflow: hidden !important;
  margin: 0 !important;
  padding: 0 !important;
}}

/* Sidebar = cor do logo */
[data-testid="stSidebar"],
[data-testid="stSidebar"] > div,
[data-testid="stSidebarContent"],
[data-testid="stSidebarUserContent"] {{
  background: {LOGO_BG} !important;
  background-color: {LOGO_BG} !important;
}}

/* Logo no topo */
.td-sidebar-brand {{
  display: block;
  width: 100%;
  margin: 0 0 0.9rem 0;
  padding: 0.85rem 0.75rem 0.25rem 0.75rem;
  background: {LOGO_BG};
  text-align: center;
  box-sizing: border-box;
}}
.td-sidebar-brand img {{
  width: min(100%, 230px);
  height: auto;
  display: block;
  margin: 0 auto;
  background: {LOGO_BG};
  border: 0;
}}

/* page_link como botões do menu */
[data-testid="stSidebar"] [data-testid="stPageLink-NavLink"],
[data-testid="stSidebar"] a[data-testid="stPageLink-NavLink"] {{
  display: flex !important;
  align-items: center !important;
  gap: 0.65rem !important;
  border-radius: 14px !important;
  padding: 0.72rem 0.9rem !important;
  margin: 0 0 0.4rem 0 !important;
  background: linear-gradient(145deg, rgba(17, 24, 39, 0.95), rgba(15, 23, 42, 0.7)) !important;
  border: 1px solid rgba(167, 139, 250, 0.16) !important;
  box-shadow: 0 8px 22px rgba(0, 0, 0, 0.22) !important;
  color: #E2E8F0 !important;
  font-weight: 600 !important;
  text-decoration: none !important;
}}
[data-testid="stSidebar"] [data-testid="stPageLink-NavLink"]:hover {{
  border-color: rgba(167, 139, 250, 0.45) !important;
  background: linear-gradient(145deg, rgba(49, 46, 129, 0.45), rgba(15, 23, 42, 0.85)) !important;
}}
/* item ativo (aria-current / selected) */
[data-testid="stSidebar"] [data-testid="stPageLink-NavLink"][aria-current="page"],
[data-testid="stSidebar"] a[aria-current="page"] {{
  background: linear-gradient(135deg, rgba(139, 92, 246, 0.45), rgba(59, 130, 246, 0.28)) !important;
  border-color: rgba(167, 139, 250, 0.55) !important;
}}
</style>
""",
        unsafe_allow_html=True,
    )


def render_sidebar_nav(pages: Sequence[st.Page]) -> None:
    """Logo no topo + links de página (ordem controlada por nós)."""
    uri = _logo_data_uri()
    with st.sidebar:
        if uri:
            st.markdown(
                f'<div class="td-sidebar-brand"><img src="{uri}" alt="TradingDash" /></div>',
                unsafe_allow_html=True,
            )
        for page in pages:
            try:
                icon = page.icon or None
            except Exception:
                icon = None
            if icon:
                st.page_link(page, icon=icon, width="stretch")
            else:
                st.page_link(page, width="stretch")
        st.divider()
        from src.ui.data_source import render_global_mode_toggle
        from src.ui.cache_button import render_refresh_control

        render_global_mode_toggle()
        render_refresh_control(key="global_refresh")


def page_setup() -> None:
    ensure_root_on_path()
    _apply_active_locale_from_settings()
    apply_theme()


def _apply_active_locale_from_settings() -> None:
    """Aplica o locale das settings ao hook global de formatação."""
    try:
        from src.config import get_settings

        locale = str(getattr(get_settings(), "locale", "pt_BR") or "pt_BR")
        if locale not in ("pt_BR", "en_US"):
            locale = "pt_BR"
        from src.format_hooks import set_active_locale

        set_active_locale(locale)  # type: ignore[arg-type]
    except Exception:
        pass  # nunca quebra a página por causa de locale


def page_setup_with_data_banner(provider: str | None = None) -> None:
    """page_setup + banner de qualidade de dados (se provider informado)."""
    page_setup()
    if provider:
        from src.ui.data_source import render_data_quality_banner

        render_data_quality_banner(provider)
