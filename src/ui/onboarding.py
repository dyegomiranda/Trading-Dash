"""Onboarding amigável na primeira visita (session_state)."""

from __future__ import annotations

import streamlit as st

from src.config import THESIS_LABEL, THESIS_VERSION


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
**Caminho recomendado (4 cliques mentais)**

1. **Descubra ações** — veja notas e gráficos  
2. **Minha carteira → Montar carteira** — defina capital e clique em **Montar carteira com a tese**  
3. **Receber dividendos da bolsa** — veja renda caindo no caixa (real ou estimativa do mês)  
4. **Renda esperada** — aportes + 3 cenários (cauteloso / base / animado)

Depois, se quiser: **Teste no passado** e o **Guia do iniciante**.
"""
            )
        else:
            st.markdown(
                """
**Checklist rápido**

- [ ] Entendi que é **treino** até eu validar fora do app  
- [ ] Vou começar por **Descubra ações** ou **Montar carteira com a tese**  
- [ ] Vou olhar a **Renda esperada** com aportes mensais  

Quando quiser, reabra este guia no menu **Guia do iniciante**.
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
            if st.button("Começar a usar", type="primary", width="stretch", key="ob_done"):
                mark_onboarding_done()
                st.session_state["onboarding_step"] = 0
                st.rerun()
    with c3:
        if st.button("Pular tour", width="stretch", key="ob_skip"):
            mark_onboarding_done()
            st.rerun()

    return True


def render_onboarding_reset_button() -> None:
    """Botão discreto para refazer o tour."""
    if st.button("Refazer tour de boas-vindas", key="ob_reset"):
        st.session_state["onboarding_done"] = False
        st.session_state["onboarding_step"] = 0
        st.rerun()
