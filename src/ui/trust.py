"""Componentes de confiança amigáveis (sem jargão de compliance pesado)."""

from __future__ import annotations

from typing import Any, Sequence

import streamlit as st

from src.config import THESIS_LABEL, THESIS_VERSION


def render_trust_strip(
    *,
    provider: str,
    coverage: dict[str, Any] | None = None,
    extra: str | None = None,
) -> None:
    """Faixa curta: de onde vêm os dados e quão completos estão."""
    if provider == "demo":
        st.warning(
            "**Modo treino:** as notas e rankings usam números **ilustrativos**. "
            "Sirvem para aprender o app. Para estudar com cara de mercado, mude para **Bolsa real**.",
            icon=":material/school:",
        )
        return

    cov = coverage or {}
    level = cov.get("trust_level") or "parcial"
    label = cov.get("trust_label") or "Dados de mercado"
    n = cov.get("n") or 0
    with_price = cov.get("with_price") or 0
    with_dy = cov.get("with_dy") or 0
    as_of = cov.get("as_of") or ""

    msg = (
        f"**{label}.** Empresas no radar: **{n}** · com preço: **{with_price}** · "
        f"com dividendo informado: **{with_dy}** · atualizado: {as_of}. "
        f"Tese {THESIS_LABEL} v{THESIS_VERSION}."
    )
    if extra:
        msg += f" {extra}"

    if level == "boa":
        st.success(msg, icon=":material/verified:")
    elif level == "fraca":
        st.error(msg + " Prefira conferir em outra fonte antes de qualquer decisão real.", icon=":material/warning:")
    else:
        st.info(msg, icon=":material/info:")


def render_premises_box(items: Sequence[str], *, title: str = "Premissas deste resultado") -> None:
    """Lista simples do que o cálculo assumiu (transparência sem assustar)."""
    with st.expander(title, icon=":material/rule:", expanded=False):
        for it in items:
            st.markdown(f"- {it}")
        st.caption(
            "Se mudar uma premissa (aporte, anos, reinvestir), os números mudam. "
            "Isto é um cenário de estudo da tese — não uma promessa de rendimento."
        )


def render_friendly_safety_note() -> None:
    """Rodapé leve e constante — mantém tom de guia, não de contrato jurídico."""
    st.caption(
        f"{THESIS_LABEL} v{THESIS_VERSION} · conta de treino e cenários de estudo · "
        "dados de mercado podem falhar ou atrasar · "
        "use como guia para aprender a tese, não como ordem de compra automática na corretora."
    )
