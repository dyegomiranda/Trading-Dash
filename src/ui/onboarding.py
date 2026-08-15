"""Onboarding amigável na primeira visita (session_state)."""

from __future__ import annotations

import streamlit as st

from src.config import THESIS_LABEL, THESIS_VERSION
from src.ui.data_source import request_session_provider


def _done() -> bool:
    return bool(st.session_state.get("onboarding_done"))


def mark_onboarding_done() -> None:
    st.session_state["onboarding_done"] = True


def render_onboarding_if_needed() -> bool:
    """Mostra o guia de 4 passos se ainda não concluiu.

    Returns
    -------
    True se o onboarding está ativo (páginas podem encurtar o resto).
    """
    if _done():
        return False

    st.markdown("### Bem-vindo ao TradingDash")
    st.caption(
        f"{THESIS_LABEL} v{THESIS_VERSION} · conta de treino com dinheiro de mentira"
    )

    step = int(st.session_state.get("onboarding_step", 0))
    steps = [
        "A ideia em 30 segundos",
        "De onde vêm os números",
        "Seu caminho no app",
        "Pronto para começar",
    ]

    st.progress((step + 1) / len(steps), text=f"Passo {step + 1} de {len(steps)}: {steps[step]}")

    with st.container(border=True):
        if step == 0:
            st.markdown(
                """
**O que este app faz por você**

Ajuda a **estudar e treinar** uma carteira de ações brasileiras focada em:

1. Empresas de **qualidade** (negócio sólido)
2. **Dividendos** sustentáveis (renda possível sem vender a ação)
3. **Diversificação** (várias empresas, limite por setor)
4. Tudo primeiro em **conta de treino** (sem corretora)

Não é promessa de lucro — é um **guia guiado** para aprender a tese com calma.
"""
            )
        elif step == 1:
            st.markdown(
                """
**Duas fontes de dados**

| Fonte | Quando usar |
|-------|-------------|
| **Bolsa real** | Estudar com preços/indicadores de mercado (podem falhar ou atrasar) |
| **Modo treino** | Aprender a interface na hora, com números ilustrativos |

O app mostra **qualidade dos dados** e **premissas**.  
Se algo estiver incompleto, a nota da empresa perde força — de propósito.
"""
            )
        elif step == 2:
            st.markdown(
                """
**Caminho recomendado**

1. Fique no **Modo treino** nesta primeira visita (já está ligado)  
2. **Descubra ações** — notas, radar dos 4 pilares e o porquê de cada nome  
3. **Minha carteira** → clique em **Montar carteira com a tese** (R$ 10 mil de treino)  
4. **Renda esperada** — 3 cenários, sem mágica

Depois, se quiser: **Teste no passado** (ensaio com o retrato de hoje) e o **Guia**.
"""
            )
        else:
            st.markdown(
                """
**Checklist rápido**

- [ ] Entendi que é **treino** até eu validar fora do app  
- [ ] Vou começar no **Modo treino** e só depois pedir Bolsa real  
- [ ] O botão que monta o livro é **Montar carteira com a tese**

Reabra este tour no **Início** (barra lateral) ou no **Guia do iniciante**.
"""
            )
            st.success(
                "Ao concluir, o app libera o painel completo. Você pode repetir o tour depois.",
                icon=":material/celebration:",
            )

    c1, c2, c3 = st.columns([1, 1, 1])
    with c1:
        if step > 0 and st.button("Voltar", width="stretch", key="ob_back"):
            st.session_state["onboarding_step"] = step - 1
            st.rerun()
    with c2:
        if step < len(steps) - 1:
            if st.button("Continuar", type="primary", width="stretch", key="ob_next"):
                st.session_state["onboarding_step"] = step + 1
                st.rerun()
        else:
            if st.button(
                "Começar no modo treino",
                type="primary",
                width="stretch",
                key="ob_done",
            ):
                mark_onboarding_done()
                st.session_state["onboarding_step"] = 0
                request_session_provider("demo")
                st.rerun()
    with c3:
        if st.button("Pular tour", width="stretch", key="ob_skip"):
            mark_onboarding_done()
            request_session_provider("demo")
            st.rerun()

    return True


def render_onboarding_reset_button() -> None:
    """Botão discreto para refazer o tour."""
    if st.button("Refazer tour de boas-vindas", key="ob_reset"):
        st.session_state["onboarding_done"] = False
        st.session_state["onboarding_step"] = 0
        st.rerun()
