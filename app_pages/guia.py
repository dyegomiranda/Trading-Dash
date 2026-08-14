"""Guia do iniciante — jornada + dicionário em português claro."""

from __future__ import annotations

import streamlit as st

from src.config import SCORE_WEIGHTS, THESIS_LABEL, THESIS_VERSION, get_settings
from src.ui.components import (
    render_journey,
    render_page_header,
    render_plain_help,
    render_section_label,
)
from src.ui.friendly import GLOSSARY, JOURNEY_STEPS
from src.ui.shell import page_setup
from src.ui.trust import render_friendly_safety_note

page_setup()
render_page_header(
    "Guia do iniciante",
    f"Do zero até uma carteira de treino · {THESIS_LABEL} v{THESIS_VERSION}",
)

s = get_settings()

render_section_label("Jornada recomendada")
render_journey(JOURNEY_STEPS, current=0, completed_through=-1)

render_plain_help(
    "Faça nesta ordem",
    f"""
1. **Início** — entenda o panorama e o dinheiro da conta de treino  
2. **Descubra ações** — veja notas, setores e o gráfico de preço (1 mês → máximo)  
3. **Minha carteira → Montar carteira** — defina o capital e clique em *Montar carteira com a tese*  
4. **Minha carteira → Renda esperada** — veja renda mensal/anual estimada, vantagens e riscos  
5. **Teste no passado** (opcional) — “e se eu tivesse seguido a ideia desde tal data?”  

**Meta da tese:** cerca de **{s.core_weight:.0%}** em empresas mais estáveis (base) e  
**{s.satellite_weight:.0%}** em um complemento um pouco mais flexível — visando **renda com qualidade**,  
não o maior dividendo a qualquer custo.
""",
)

render_section_label("A estratégia em uma frase")
with st.container(border=True):
    st.markdown(
        f"""
Preferir **empresas boas**, que **paguem dividendos de forma sustentável**,  
colocando cerca de **{s.core_weight:.0%}** do dinheiro em nomes mais estáveis (**base**)  
e **{s.satellite_weight:.0%}** em um **complemento** um pouco mais flexível.

O objetivo é **renda com qualidade**, não caçar o maior dividendo do momento a qualquer preço.
"""
    )

st.markdown("##### Como o app dá nota às ações")
st.markdown(
    f"""
| Ideia | Peso | Em português |
|-------|------|--------------|
| Qualidade | {SCORE_WEIGHTS['quality']:.0%} | O negócio lucra bem e com consistência? |
| Dividendos | {SCORE_WEIGHTS['dividends']:.0%} | A renda é atraente **e** sustentável? |
| Saúde financeira | {SCORE_WEIGHTS['financial_health']:.0%} | A dívida está sob controle? |
| Preço justo | {SCORE_WEIGHTS['valuation']:.0%} | A ação não está absurdamente cara? |

**Faixa de dividendo preferida pela tese:** cerca de {s.preferred_dy_min:.0%} a {s.preferred_dy_max:.0%} ao ano  
(muito acima disso pode ser sinal de risco, não de “melhor negócio”).
"""
)

st.markdown("##### O que cada número da carteira significa")
with st.container(border=True):
    st.markdown(
        """
| O que você vê | Significado simples |
|---------------|---------------------|
| **Dinheiro total na conta de treino** | Caixa livre + valor das ações |
| **Livre no caixa** | Ainda não aplicado — pode comprar |
| **Aplicado em ações** | Valor de mercado das posições (sem o caixa) |
| **Renda estimada (por mês)** | Quanto os dividendos poderiam pagar / mês (estimativa) |
| **Em % do seu total** | Renda anual ÷ dinheiro total da conta |
| **Nota do app (0–100)** | Encaixe na tese (maior = melhor encaixe) |
| **Base / complemento** | Parte mais estável vs. parte um pouco mais flexível |

Se dois cartões grandes parecerem “patrimônio”, confira o **rótulo**:  
um é o **total da conta**; o outro (na aba Renda) é **renda de dividendos**, não o mesmo dinheiro.
"""
    )

st.markdown("##### Dicionário")
for term, meaning in GLOSSARY:
    with st.container(border=True):
        st.markdown(f"**{term}**")
        st.markdown(meaning)

st.markdown("##### Como o app tenta ser realista (sem complicar)")
with st.container(border=True):
    st.markdown(
        f"""
- **Montar carteira com a tese** continua fácil — mas limita peso por ação (~{s.max_position_pct:.0%})
  e por setor (~{s.max_sector_pct:.0%})
- **Dividendos altos demais** com sinais fracos perdem nota (evita “armadilha de yield”)
- **Renda esperada** mostra **3 cenários** (cauteloso / base / animado) e a conta capital × taxa
- Você pode simular com **qualquer capital inicial**, independente do valor da conta de treino
- Dados incompletos baixam a confiança da nota; o app avisa a **cobertura** do ranking
- Fontes gratuitas podem falhar: use o app como **guia amigável da tese**, e confira fora antes
  de dinheiro real

Versão da tese: **{THESIS_VERSION}**
"""
    )

render_friendly_safety_note()
