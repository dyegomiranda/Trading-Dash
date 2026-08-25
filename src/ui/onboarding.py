"""Onboarding amigável na primeira visita (session_state) com trilha de aprendizado."""

from __future__ import annotations

import streamlit as st

from src.config import THESIS_LABEL, THESIS_VERSION
from src.ui.data_source import request_session_provider
from src.ui.friendly import GLOSSARY


def _done() -> bool:
    return bool(st.session_state.get("onboarding_done"))


def mark_onboarding_done() -> None:
    st.session_state["onboarding_done"] = True


def _get_learning_milestones() -> dict[str, bool]:
    """Obtém ou inicializa os marcos de aprendizado do usuário."""
    if "learning_milestones" not in st.session_state:
        st.session_state["learning_milestones"] = {
            "understand_training": False,
            "know_data_sources": False,
            "built_first_portfolio": False,
            "viewed_income_estimates": False,
            "ran_backtest": False,
            "understood_risk": False,
        }
    return st.session_state["learning_milestones"]


def _update_milestone(milestone_id: str, achieved: bool = True) -> None:
    """Atualiza um marco de aprendizado específico."""
    milestones = _get_learning_milestones()
    if milestone_id in milestones:
        milestones[milestone_id] = achieved
        st.session_state["learning_milestones"] = milestones


def _has_portfolio_positions() -> bool:
    """Verifica se a carteira padrão já tem posições."""
    try:
        from src.portfolio.paper import load_portfolio
        p = load_portfolio("paper-main")
        return bool(p.positions)
    except Exception:
        return False


def render_onboarding_if_needed() -> bool:
    """Mostra o guia de onboarding com trilha de aprendizado se ainda não concluiu.

    Returns
    -------
    True se o onboarding está ativo (páginas podem encurtar o resto).
    """
    if _done():
        return False
    if _has_portfolio_positions():
        mark_onboarding_done()
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
**De onde vêm os números**

O app usa **preços e indicadores da bolsa** (Yahoo Finance). A carteira é de **dinheiro fictício**: você treina o fluxo sem corretora, mas com dados de mercado.

A fonte pode atrasar ou faltar — é gratuita. Se um indicador não vier, a nota da empresa perde força, de propósito.
"""
            )
        elif step == 2:
            st.markdown(
                """
**Caminho recomendado**

1. **Descubra ações** — as 4 notas da tese e o porquê de cada nome
2. **Minha carteira** → clique em **Montar carteira com a tese** (R$ 10 mil fictícios)
3. **Renda esperada** — 3 cenários, sem mágica
4. **Teste no passado** (opcional) — como a tese se comportaria com preços reais

Depois, o **Guia** se alguma palavra escapar.
"""
            )
        else:
            st.markdown(
                """
**Checklist rápido**

- [ ] Entendi que o dinheiro é **fictício** e os preços são da **bolsa**
- [ ] O botão que monta o livro é **Montar carteira com a tese**
- [ ] Vou validar qualquer nome em RI/CVM antes de dinheiro real

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
                "Começar com a bolsa",
                type="primary",
                width="stretch",
                key="ob_done",
            ):
                mark_onboarding_done()
                st.session_state["onboarding_step"] = 0
                request_session_provider("yfinance")
                st.rerun()
    with c3:
        if st.button("Pular tour", width="stretch", key="ob_skip"):
            mark_onboarding_done()
            request_session_provider("yfinance")
            st.rerun()

    return True


def render_onboarding_reset_button() -> None:
    """Botão discreto para refazer o tour."""
    if st.button("Refazer tour de boas-vindas", key="ob_reset"):
        st.session_state["onboarding_done"] = False
        st.session_state["onboarding_step"] = 0
        # Reset learning milestones too
        if "learning_milestones" in st.session_state:
            del st.session_state["learning_milestones"]
        st.rerun()


def render_learning_dashboard() -> None:
    """Renderiza o painel de aprendizado com marcos alcançados."""
    milestones = _get_learning_milestones()

    st.markdown("### 🎯 Sua jornada de aprendizado")

    # Define os marcos com descrições e ícones
    milestone_definitions = {
        "understand_training": {
            "title": "Entende a conta de treino",
            "description": "Soube que o dinheiro é fictício e os preços vêm da bolsa",
            "icon": ":material/school:",
        },
        "know_data_sources": {
            "title": "Conhece as fontes de dados",
            "description": "Entende onde os números vêm e suas limitações",
            "icon": ":material/database:",
        },
        "built_first_portfolio": {
            "title": "Primeira carteira construída",
            "description": "Montou sua primeira carteira usando a tese Quality Dividend",
            "icon": ":material/business_center:",
        },
        "viewed_income_estimates": {
            "title": "Visualizou renda esperada",
            "description": "Analisou os cenários de renda de dividendos projetados",
            "icon": ":material/savings:",
        },
        "ran_backtest": {
            "title": "Executou primeiro backtest",
            "description": "Testou como sua estratégia teria se comportado no passado",
            "icon": ":material/insights:",
        },
        "understood_risk": {
            "title": "Entende o conceito de risco",
            "description": "Compreende drawdown, volatilidade e a importância da diversificação",
            "icon": ":material/shield:",
        },
    }

    # Cria cards para cada marco
    cols = st.columns(3)
    for i, (milestone_id, achieved) in enumerate(milestones.items()):
        milestone = milestone_definitions.get(milestone_id, {
            "title": milestone_id.replace("_", " ").title(),
            "description": "Marco de aprendizado",
            "icon": ":material/flag:",
        })

        with cols[i % 3]:
            if achieved:
                st.success(
                    f"{milestone['icon']} **{milestone['title']}**\n\n{milestone['description']}",
                    icon=":material/check_circle:"
                )
            else:
                st.info(
                    f"{milestone['icon']} **{milestone['title']}**\n\n{milestone['description']}",
                    icon=":material/radio_button_unchecked:"
                )


def render_contextual_help(term: str, key: str | None = None) -> None:
    """Renderiza ajuda contextual para um termo técnico usando o glossário amigável.

    Args:
        term: O termo técnico para explicar
        key: Chave única para o elemento (opcional)
    """
    # Procura no glossário amigável
    for friendly_term, explanation in GLOSSARY:
        if friendly_term.lower() == term.lower():
            with st.popover(f"💡 {friendly_term}", use_container_width=False):
                st.markdown(explanation)
            return

    # Se não encontrou no glossário, cria um popover genérico
    with st.popover(f"💡 {term}", use_container_width=False):
        st.markdown("Termo técnico - consulte o glossário para mais detalhes.")