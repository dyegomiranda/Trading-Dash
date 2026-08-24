"""Assistente Visual de 1 Minuto (Quick Wizard) para Iniciantes.

Permite a qualquer pessoa montar uma carteira fictícia guiada em 3 passos visuais,
sem jargões ou termos contábeis complexos.
"""

from __future__ import annotations

import streamlit as st

from src.portfolio.income import DEFAULT_YIELD_HAIRCUT
from src.portfolio.paper import load_portfolio, save_portfolio
from src.services import format_brl, prices_dict_from_fundamentals
from src.thesis.scoring import recommend_weights


def render_quick_wizard(scored_universe_func, provider: str) -> None:
    """Renderiza o assistente visual passo a passo no Início."""
    with st.container(border=True):
        st.markdown(
            """
            ### 🚀 Assistente Rápido: Crie sua carteira em 1 minuto
            *Sem complicação: escolha quanto quer simular e o estilo que preferir.*
            """
        )

        c1, c2, c3 = st.columns([1.2, 1.4, 1.2], gap="medium")

        with c1:
            st.markdown("**1. Quanto quer simular?**")
            capital_choice = st.radio(
                "Capital inicial",
                options=[5_000.0, 10_000.0, 50_000.0, 100_000.0],
                index=1,
                format_func=lambda x: format_brl(x),
                horizontal=True,
                label_visibility="collapsed",
                key="wiz_capital",
            )

        with c2:
            st.markdown("**2. Qual o seu estilo de renda?**")
            style_choice = st.radio(
                "Estilo",
                options=["balanced", "dividends", "quality"],
                index=0,
                format_func=lambda x: {
                    "balanced": "⚖️ Equilibrada (Padrão)",
                    "dividends": "💰 Foco em Dividendos",
                    "quality": "💎 Máxima Segurança",
                }.get(x, x),
                horizontal=True,
                label_visibility="collapsed",
                key="wiz_style",
            )

        with c3:
            st.markdown("**3. Pronto para começar?**")
            create_clicked = st.button(
                "✨ Montar Carteira",
                type="primary",
                width="stretch",
                key="wiz_create_btn",
                help="Gera e salva sua carteira fictícia automaticamente com base nas melhores ações da B3.",
            )

        if create_clicked:
            with st.spinner("Analisando empresas e montando sua carteira ideal…"):
                try:
                    # Carregar dados do mercado
                    result = scored_universe_func(provider)
                    filtered = result.filtered
                    if filtered is None or getattr(filtered, "empty", True):
                        st.error(
                            "Nenhuma ação passou no filtro da tese agora. "
                            "Não montei a carteira com a lista sem filtro — "
                            "abra Descubra ações ou relaxe a nota mínima."
                        )
                        return

                    # Ajustar pesos de acordo com o estilo
                    core_w = 0.70
                    sat_w = 0.30
                    if style_choice == "quality":
                        core_w = 0.85
                        sat_w = 0.15
                    elif style_choice == "dividends":
                        core_w = 0.60
                        sat_w = 0.40

                    recs = recommend_weights(
                        filtered,
                        top_n=10,
                        core_weight=core_w,
                        satellite_weight=sat_w,
                    )
                    if recs is None or getattr(recs, "empty", True):
                        st.error("A tese não devolveu pesos. Tente de novo em alguns minutos.")
                        return

                    prices = prices_dict_from_fundamentals(result.scored)

                    active_name = st.session_state.get("pf_select") or "paper-main"
                    pf = load_portfolio(active_name)
                    pf.set_capital(float(capital_choice), reset_positions=True)

                    target_weights = dict(zip(recs["ticker"], recs["target_weight"]))
                    target_buckets = dict(zip(recs["ticker"], recs.get("bucket", "core")))

                    pf.rebalance_to_weights(
                        target_weights,
                        prices,
                        buckets=target_buckets,
                        note="wizard-automatico",
                    )
                    save_portfolio(pf)
                    dy_avg = (
                        float(recs["dividend_yield"].mean())
                        if "dividend_yield" in recs.columns
                        else 0.0
                    )
                    dy_avg = max(0.0, dy_avg * (1.0 - DEFAULT_YIELD_HAIRCUT))
                    monthly_div = (capital_choice * dy_avg) / 12.0

                    st.success(
                        f"🎉 **Carteira montada com sucesso!** "
                        f"Alocamos **{format_brl(capital_choice)}** em **{len(recs)} empresas sólidas**. "
                        f"Renda estimada: **~{format_brl(monthly_div)}/mês** em dividendos.",
                        icon="✅",
                    )
                    st.session_state["pf_flash"] = "Carteira criada com sucesso!"
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao montar carteira: {e}")
