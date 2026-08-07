"""Guia do iniciante."""

from __future__ import annotations

import streamlit as st

from src.config import SCORE_WEIGHTS, get_settings
from src.ui.components import render_page_header, render_section_label
from src.ui.friendly import GLOSSARY
from src.ui.shell import page_setup

page_setup()
render_page_header("Guia do iniciante", "Dicionário e estratégia")

s = get_settings()

render_section_label("Fundamentos")
st.subheader("A estratégia em uma frase")
with st.container(border=True):
    st.markdown(
        f"""
Preferir **empresas boas**, que **paguem dividendos de forma sustentável**,  
colocando cerca de **{s.core_weight:.0%}** do dinheiro em nomes mais estáveis (**base**)  
e **{s.satellite_weight:.0%}** em um **complemento** um pouco mais flexível.

O objetivo é **renda com qualidade**, não caçar o maior dividendo do momento a qualquer custo.
"""
    )

st.subheader("Como o app dá nota às ações")
st.markdown(
    f"""
| Ideia | Peso | Em português |
|-------|------|--------------|
| Qualidade | {SCORE_WEIGHTS['quality']:.0%} | Lucra bem e com consistência? |
| Dividendos | {SCORE_WEIGHTS['dividends']:.0%} | Renda atraente e sustentável? |
| Saúde financeira | {SCORE_WEIGHTS['financial_health']:.0%} | Dívida sob controle? |
| Preço justo | {SCORE_WEIGHTS['valuation']:.0%} | Não está absurdamente cara? |

**Faixa de dividendo preferida:** cerca de {s.preferred_dy_min:.0%} a {s.preferred_dy_max:.0%} ao ano.
"""
)

st.subheader("Dicionário")
for term, meaning in GLOSSARY:
    with st.container(border=True):
        st.markdown(f"**{term}**")
        st.markdown(meaning)

st.caption("Ferramenta de estudo · não é recomendação de investimento.")
