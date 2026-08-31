"""Onboarding amigável na primeira visita (session_state) com trilha de aprendizado."""

from __future__ import annotations

import streamlit as st

from src.ui.friendly import GLOSSARY


def _done() -> bool:
    return bool(st.session_state.get("onboarding_done"))


def mark_onboarding_done() -> None:
    st.session_state["onboarding_done"] = True
    st.session_state["tour_force_active"] = False


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
    """Verifica se qualquer carteira salva já tem posições."""
    try:
        from src.portfolio.paper import list_portfolios, load_portfolio
        for name in list_portfolios():
            p = load_portfolio(name)
            if p.positions:
                return True
        return False
    except Exception:
        return False



def render_onboarding_if_needed() -> bool:
    """Mostra o guia de onboarding com trilha de aprendizado se ainda não concluiu ou se foi forçado."""
    is_forced = bool(st.session_state.get("tour_force_active", False))
    if not is_forced:
        if _done():
            return False
        if _has_portfolio_positions():
            mark_onboarding_done()
            return False

    st.markdown(
        """
<div class="td-hero-glass" style="margin-bottom:1.5rem;">
  <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:1rem;">
    <div>
      <div style="font-size:0.8rem; font-weight:700; color:#818CF8; text-transform:uppercase; letter-spacing:0.05em;">Tour Guiado Rápido</div>
      <div style="font-size:1.75rem; font-weight:800; color:#F8FAFC; margin-top:0.2rem;">Bem-vindo ao TradingDash</div>
      <div style="font-size:0.9rem; color:#94A3B8; margin-top:0.25rem;">Aprenda a investir em dividendos na B3 com dinheiro de treino e inteligência visual</div>
    </div>
    <div style="background:rgba(56, 189, 248, 0.12); border:1px solid rgba(56, 189, 248, 0.3); border-radius:999px; padding:0.35rem 0.9rem; font-size:0.82rem; color:#38BDF8; font-weight:600;">
      🎮 100% Simulação Segura
    </div>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )

    step = int(st.session_state.get("onboarding_step", 0))
    steps = [
        "1. A ideia em 30 segundos",
        "2. De onde vêm os números",
        "3. Seu caminho guiado",
        "4. Pronto para começar",
    ]

    st.progress((step + 1) / len(steps), text=f"Etapa {step + 1} de {len(steps)}: {steps[step]}")

    with st.container(border=True):
        if step == 0:
            st.markdown(
                """
<div style="padding:0.5rem 0;">
  <h4 style="color:#F8FAFC; margin-bottom:0.5rem;">🎯 O que o TradingDash faz por você</h4>
  <p style="color:#94A3B8; font-size:0.9rem; margin-bottom:1.25rem;">
    Ele elimina a complexidade do mercado financeiro e ajuda você a montar uma <b>carteira de dividendos inteligentes</b> baseada em 4 pilares:
  </p>
  <div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(220px, 1fr)); gap:0.85rem;">
    <div style="background:rgba(17,24,39,0.7); border:1px solid rgba(255,255,255,0.08); border-radius:12px; padding:0.9rem;">
      <div style="font-size:1.25rem; margin-bottom:0.3rem;">🏢</div>
      <div style="font-weight:700; color:#34D399; font-size:0.95rem;">Qualidade Comprovada</div>
      <div style="font-size:0.8rem; color:#94A3B8; margin-top:0.25rem;">Negócios sólidos e lucrativos (bancos, energia, saneamento).</div>
    </div>
    <div style="background:rgba(17,24,39,0.7); border:1px solid rgba(255,255,255,0.08); border-radius:12px; padding:0.9rem;">
      <div style="font-size:1.25rem; margin-bottom:0.3rem;">💰</div>
      <div style="font-weight:700; color:#38BDF8; font-size:0.95rem;">Dividendos Sustentáveis</div>
      <div style="font-size:0.8rem; color:#94A3B8; margin-top:0.25rem;">Renda periódica pingando sem precisar vender suas ações.</div>
    </div>
    <div style="background:rgba(17,24,39,0.7); border:1px solid rgba(255,255,255,0.08); border-radius:12px; padding:0.9rem;">
      <div style="font-size:1.25rem; margin-bottom:0.3rem;">🛡️</div>
      <div style="font-weight:700; color:#818CF8; font-size:0.95rem;">Saúde Financeira</div>
      <div style="font-size:0.8rem; color:#94A3B8; margin-top:0.25rem;">Empresas com dívidas sob controle e caixas confortáveis.</div>
    </div>
    <div style="background:rgba(17,24,39,0.7); border:1px solid rgba(255,255,255,0.08); border-radius:12px; padding:0.9rem;">
      <div style="font-size:1.25rem; margin-bottom:0.3rem;">⚖️</div>
      <div style="font-weight:700; color:#FBBF24; font-size:0.95rem;">Preço Justo</div>
      <div style="font-size:0.8rem; color:#94A3B8; margin-top:0.25rem;">Evita comprar ações caras demais no topo do mercado.</div>
    </div>
  </div>
</div>
""",
                unsafe_allow_html=True,
            )
        elif step == 1:
            st.markdown(
                """
<div style="padding:0.5rem 0;">
  <h4 style="color:#F8FAFC; margin-bottom:0.5rem;">📊 De onde vêm os números?</h4>
  <p style="color:#94A3B8; font-size:0.9rem; margin-bottom:1.25rem;">
    Transparência total: você não precisa arriscar dinheiro real para aprender.
  </p>
  <div style="display:grid; grid-template-columns:1fr 1fr; gap:1rem;">
    <div style="background:rgba(17,24,39,0.75); border:1px solid rgba(56,189,248,0.25); border-radius:14px; padding:1.1rem;">
      <div style="font-size:1.1rem; font-weight:700; color:#38BDF8; margin-bottom:0.35rem;">🟢 Dados Reais da Bolsa (B3)</div>
      <div style="font-size:0.84rem; color:#CBD5E1; line-height:1.4;">
        Cotações diárias, dividendos históricos e balanços oficiais auditados das empresas listadas no Brasil.
      </div>
    </div>
    <div style="background:rgba(17,24,39,0.75); border:1px solid rgba(52,211,153,0.25); border-radius:14px; padding:1.1rem;">
      <div style="font-size:1.1rem; font-weight:700; color:#34D399; margin-bottom:0.35rem;">🎮 Dinheiro de Treino (Sem Risco)</div>
      <div style="font-size:0.84rem; color:#CBD5E1; line-height:1.4;">
        Você começa com <b>R$ 10.000 fictícios</b> para treinar montagem de carteira, aportes e simulações sem precisar vincular corretora.
      </div>
    </div>
  </div>
</div>
""",
                unsafe_allow_html=True,
            )
        elif step == 2:
            st.markdown(
                """
<div style="padding:0.5rem 0;">
  <h4 style="color:#F8FAFC; margin-bottom:0.5rem;">🚀 Seu caminho dentro do aplicativo</h4>
  <p style="color:#94A3B8; font-size:0.9rem; margin-bottom:1.25rem;">
    A navegação foi desenhada para ser simples e fluida:
  </p>
  <div style="display:flex; flex-direction:column; gap:0.75rem;">
    <div style="background:rgba(17,24,39,0.6); border:1px solid rgba(255,255,255,0.06); border-radius:12px; padding:0.85rem 1rem; display:flex; align-items:center; gap:1rem;">
      <span style="font-size:1.3rem; background:rgba(56,189,248,0.15); padding:0.4rem 0.7rem; border-radius:8px; font-weight:800; color:#38BDF8;">1</span>
      <div>
        <div style="color:#F8FAFC; font-weight:700; font-size:0.92rem;">Descubra Ações</div>
        <div style="color:#94A3B8; font-size:0.8rem;">Explore até 369 empresas com diagnóstico visual de saúde financeira sem termos difíceis.</div>
      </div>
    </div>
    <div style="background:rgba(17,24,39,0.6); border:1px solid rgba(255,255,255,0.06); border-radius:12px; padding:0.85rem 1rem; display:flex; align-items:center; gap:1rem;">
      <span style="font-size:1.3rem; background:rgba(52,211,153,0.15); padding:0.4rem 0.7rem; border-radius:8px; font-weight:800; color:#34D399;">2</span>
      <div>
        <div style="color:#F8FAFC; font-weight:700; font-size:0.92rem;">Minha Carteira</div>
        <div style="color:#94A3B8; font-size:0.8rem;">Monte sua carteira com 1 clique e acompanhe o progresso das suas Metas de Liberdade Financeira.</div>
      </div>
    </div>
    <div style="background:rgba(17,24,39,0.6); border:1px solid rgba(255,255,255,0.06); border-radius:12px; padding:0.85rem 1rem; display:flex; align-items:center; gap:1rem;">
      <span style="font-size:1.3rem; background:rgba(129,140,248,0.15); padding:0.4rem 0.7rem; border-radius:8px; font-weight:800; color:#818CF8;">3</span>
      <div>
        <div style="color:#F8FAFC; font-weight:700; font-size:0.92rem;">Teste no Passado & Radar de Notícias</div>
        <div style="color:#94A3B8; font-size:0.8rem;">Veja o ganho real acima da inflação (IPCA) e receba notícias dos seus ativos com análise de sentimento.</div>
      </div>
    </div>
  </div>
</div>
""",
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                """
<div style="padding:0.5rem 0; text-align:center;">
  <div style="font-size:2.5rem; margin-bottom:0.5rem;">🎉</div>
  <h3 style="color:#F8FAFC; margin-bottom:0.4rem;">Tudo pronto para decolar!</h3>
  <p style="color:#94A3B8; font-size:0.92rem; max-width:520px; margin:0 auto 1.5rem auto;">
    Você está pronto para explorar o mercado e simular sua carteira com segurança. Você pode reiniciar este tour a qualquer momento.
  </p>
</div>
""",
                unsafe_allow_html=True,
            )

    c1, c2, c3 = st.columns([1, 1, 1])
    with c1:
        if step > 0 and st.button("⬅ Voltar", width="stretch", key="ob_back"):
            st.session_state["onboarding_step"] = step - 1
            st.rerun()
    with c2:
        if step < len(steps) - 1:
            if st.button("Próximo ➔", type="primary", width="stretch", key="ob_next"):
                st.session_state["onboarding_step"] = step + 1
                st.rerun()
        else:
            if st.button(
                "🚀 Começar a Usar",
                type="primary",
                width="stretch",
                key="ob_done",
            ):
                mark_onboarding_done()
                st.session_state["onboarding_step"] = 0
                st.rerun()
    with c3:
        if st.button("Fechar tour", width="stretch", key="ob_skip"):
            mark_onboarding_done()
            st.rerun()

    return True


def render_onboarding_reset_button() -> None:
    """Botão para refazer o tour a qualquer momento."""
    if st.button("Iniciar tour novamente", key="ob_reset", icon=":material/school:"):
        st.session_state["tour_force_active"] = True
        st.session_state["onboarding_done"] = False
        st.session_state["onboarding_step"] = 0
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