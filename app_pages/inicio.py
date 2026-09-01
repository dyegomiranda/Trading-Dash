"""Início — overview geral do programa."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from src.data.news import fetch_headlines
from src.portfolio.paper import load_portfolio, list_portfolios
from src.services import (
    format_brl,
    format_pct,
    load_scored_universe,
    prices_dict_from_fundamentals,
)
from src.thesis.macro import macro_tilt_from_override
from src.ui.data_source import (
    APPLY_THESIS_LABEL,
    get_session_macro,
    get_session_provider,
    render_clean_header,
    render_data_quality_banner,
)
from src.thesis.scoring import recommend_weights
from src.ui.charts import holdings_donut
from src.ui.components import (
    pillar_means,
    render_core_sectors_card,
    render_kpi_row,
    render_news_feed_cards,
    render_thesis_pillars,
)
from src.ui.friendly import friendly_dataframe
from src.ui.onboarding import render_onboarding_if_needed
from src.ui.shell import page_setup
from src.ui.wallet import render_wallet_balance
from src.ui.wizard import render_quick_wizard

import importlib
import src.ui.wallet
import src.ui.theme

importlib.reload(src.ui.wallet)
importlib.reload(src.ui.theme)

page_setup()

provider = get_session_provider()
_home_title = "Início"
_home_sub = "Painel principal · visão geral da carteira de treino e do mercado"

render_clean_header(_home_title, _home_sub, provider=provider)
render_data_quality_banner(provider)

# Card de Status Atual da Economia
try:
    from src.thesis.macro import fetch_macro_state, classify_regime
    _macro_state = fetch_macro_state()
    _regime = classify_regime(_macro_state.get("real_rate"), _macro_state.get("ipca_12m"))

    _selic = float(_macro_state.get("selic_aa") or 0.0)
    _raw_ipca = float(_macro_state.get("ipca_12m") or 0.0)
    _ipca_pct = _raw_ipca if _raw_ipca > 1.0 else _raw_ipca * 100.0
    _real_rate = float(_macro_state.get("real_rate") or (_selic - _ipca_pct))

    _regime_info = {
        "restrictive": {
            "title": "Regime Restritivo (Juros Altos)",
            "icon": "🔴",
            "color": "#F87171",
            "tooltip": "Juros reais elevados para controlar a inflação. Crédito mais caro e maior pressão sobre empresas alavancadas.",
            "recommendation": "Priorizar empresas perenes, com baixo endividamento (Dívida/EBITDA < 2.0x), margens elevadas e fortes geradoras de caixa (ex: Energia Elétrica, Saneamento, Seguradoras e Bancos).",
        },
        "cautious": {
            "title": "Regime Cauteloso (Neutro / Transição)",
            "icon": "🟡",
            "color": "#FACC15",
            "tooltip": "Taxas de juros em patamar intermediário ou em ciclo de transição. Cenário de equilíbrio entre crescimento e proteção.",
            "recommendation": "Manter equilíbrio entre ações 'Core' (dividendos consistentes e defensivas) e boas oportunidades 'Complemento' com valuations atraentes.",
        },
        "expansionary": {
            "title": "Regime Expansionista (Juros Baixos)",
            "icon": "🟢",
            "color": "#4ADE80",
            "tooltip": "Juros baixos estimulam consumo, crédito e investimentos produtivos. Cenário favorável para expansão dos lucros corporativos.",
            "recommendation": "Aproveitar momento para alocar em empresas de crescimento com boa governança, consumo/varejo resiliente e empresas com alto potencial de valorização e reinvestimento.",
        },
    }

    _info = _regime_info.get(_regime, _regime_info["cautious"])

    st.markdown(
        f"""
<div style="
    display: flex;
    flex-direction: column;
    padding: 0.9rem 1.2rem;
    background: linear-gradient(135deg, rgba(30, 41, 59, 0.7), rgba(15, 23, 42, 0.9));
    border: 1px solid rgba(148, 163, 184, 0.15);
    border-radius: 14px;
    margin-bottom: 1.1rem;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
    gap: 0.75rem;
">
  <div style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 0.75rem;">
    <div style="display: flex; align-items: center; gap: 0.85rem;">
      <span style="font-size: 1.6rem; line-height: 1;">{_info['icon']}</span>
      <div>
        <div style="font-size: 0.72rem; color: #94A3B8; text-transform: uppercase; letter-spacing: 0.05em; font-weight: 600;">Status Atual da Economia</div>
        <div style="display: flex; align-items: center; gap: 0.5rem; margin-top: 0.15rem;">
          <span style="color: {_info['color']}; font-weight: 700; font-size: 1.05rem;">{_info['title']}</span>
          <span title="{_info['tooltip']}" style="cursor: help; background: rgba(148,163,184,0.15); color: #94A3B8; border-radius: 50%; width: 18px; height: 18px; display: inline-flex; align-items: center; justify-content: center; font-size: 0.7rem; font-weight: bold;">ⓘ</span>
        </div>
      </div>
    </div>
    <div style="display: flex; gap: 1.25rem; align-items: center; flex-wrap: wrap;">
      <div style="text-align: right;">
        <div style="font-size: 0.68rem; color: #94A3B8;">Taxa Selic Meta</div>
        <div style="font-size: 0.95rem; font-weight: 600; color: #F8FAFC;">{_selic:.2f}% a.a.</div>
      </div>
      <div style="width: 1px; height: 24px; background: rgba(148,163,184,0.15);"></div>
      <div style="text-align: right;">
        <div style="font-size: 0.68rem; color: #94A3B8;">IPCA 12m</div>
        <div style="font-size: 0.95rem; font-weight: 600; color: #F8FAFC;">{_ipca_pct:.2f}%</div>
      </div>
      <div style="width: 1px; height: 24px; background: rgba(148,163,184,0.15);"></div>
      <div style="text-align: right;">
        <div style="font-size: 0.68rem; color: #94A3B8;">Taxa Real Líquida</div>
        <div style="font-size: 0.95rem; font-weight: 600; color: {_info['color']};">+{_real_rate:.2f}%</div>
      </div>
    </div>
  </div>
  <div style="font-size: 0.82rem; color: #CBD5E1; background: rgba(15, 23, 42, 0.6); border: 1px solid rgba(148, 163, 184, 0.1); border-radius: 8px; padding: 0.5rem 0.8rem; line-height: 1.45;">
    <strong>💡 Recomendação da tese:</strong> {_info['recommendation']}
  </div>
</div>
""",
        unsafe_allow_html=True,
    )
except Exception:
    pass

if render_onboarding_if_needed():
    st.stop()

with st.sidebar:
    st.markdown("##### Qual carteira")
    _saved = list_portfolios()
    if not _saved:
        _saved = ["paper-main"]
    current_active = (
        st.session_state.get("pf_active_name")
        or st.session_state.get("pf_select")
        or _saved[0]
    )
    if current_active not in _saved:
        current_active = _saved[0]
    active_idx = _saved.index(current_active)

    selected_portfolio = st.selectbox(
        "Carteira ativa",
        options=_saved,
        index=active_idx,
        key="home_pf_select_box",
        help="Cada carteira tem caixa e ações próprios.",
    )
    if selected_portfolio != current_active:
        st.session_state["pf_active_name"] = selected_portfolio
        st.session_state["pf_select"] = selected_portfolio
        st.rerun()

    st.markdown("---")
    if st.button("Iniciar tour novamente", key="home_tour_restart", width="stretch", icon=":material/school:"):
        st.session_state["tour_force_active"] = True
        st.session_state["onboarding_done"] = False
        st.session_state["onboarding_step"] = 0
        if "learning_milestones" in st.session_state:
            del st.session_state["learning_milestones"]
        st.rerun()


@st.cache_data(ttl=1800, show_spinner=False)
def _scored(provider: str):
    return load_scored_universe(
        provider_name=provider,  # type: ignore[arg-type]
        universe_mode="auto",
    )


@st.cache_data(ttl=900, show_spinner=False)
def _cached_home_news(tickers_tuple: tuple[str, ...], provider_name: str) -> pd.DataFrame:
    try:
        return fetch_headlines(
            list(tickers_tuple),
            provider=provider_name,
            limit=8,
            timeout_sec=12.0,
            holdings_only=False,
        )
    except Exception:
        return pd.DataFrame()


# Carteira ativa (sincronizada com Minha carteira)
_active = (
    st.session_state.get("pf_active_name")
    or st.session_state.get("pf_select")
    or "paper-main"
)
if _active not in list_portfolios() and _active != "paper-main":
    _active = "paper-main"
portfolio = load_portfolio(_active)
if not hasattr(portfolio, "meta") or portfolio.meta is None:
    portfolio.meta = {}

scored = pd.DataFrame()
filtered = scored
recs = scored
prices: dict = {}
news = pd.DataFrame()

try:
    with st.spinner("Carregando mercado…"):
        result = _scored(provider)
        scored = result.scored
        filtered = result.filtered
        recs = recommend_weights(
            filtered,
            top_n=10,
            macro_tilt=macro_tilt_from_override(get_session_macro()),
        )
        prices = prices_dict_from_fundamentals(scored)

        # Garante cotações reais para todas as posições da carteira atual (mesmo em universo amplo de 369 ações)
        if portfolio.positions:
            missing_pos = [t for t in portfolio.positions.keys() if t not in prices]
            if missing_pos:
                from src.data.providers import get_provider
                prov = get_provider(provider)
                extra_fund = prov.get_fundamentals(missing_pos)
                if extra_fund is not None and not extra_fund.empty:
                    prices.update(prices_dict_from_fundamentals(extra_fund))

        watch_boot = (
            list(portfolio.positions.keys())[:6]
            if portfolio.positions
            else (
                recs["ticker"].head(6).tolist()
                if not recs.empty and "ticker" in recs.columns
                else ["ITUB4", "PETR4", "VALE3"]
            )
        )
        news = _cached_home_news(tuple(watch_boot), provider)
except Exception as e:
    st.error(f"Falha ao carregar mercado: {e}")
    scored = pd.DataFrame()
    recs = scored

# Quick Wizard: montador visual de carteira em 1 minuto para iniciantes
if not portfolio.positions:
    render_quick_wizard(_scored, provider)

summary = portfolio.summary(prices)
holdings = portfolio.holdings_frame(prices)

build_meta = portfolio.meta.get("build_settings", {}) if hasattr(portfolio, "meta") and portfolio.meta else {}
n_analyzed = build_meta.get("total_analyzed", len(scored))
n_suggestions = build_meta.get("total_approved", len(recs))

pnl = float(summary.get("pnl") or 0)
render_kpi_row(
    [
        (
            "Dinheiro na conta de treino",
            format_brl(summary["equity"]),
            format_pct(summary.get("pnl_pct") or 0),
            "up" if pnl >= 0 else "down",
        ),
        (
            "Empresas na carteira",
            str(summary.get("n_positions") or 0),
            None,
            None,
        ),
        (
            "Sugestões da tese agora",
            str(n_suggestions),
            None,
            None,
        ),
        (
            "Empresas analisadas",
            str(n_analyzed),
            None,
            None,
        ),
    ]
)

col_left, col_right = st.columns([1.2, 1], gap="medium")
with col_left:
    render_wallet_balance(
        total=format_brl(summary["equity"]),
        delta=f"Lucro/prejuízo simulado: {format_brl(pnl)} ({format_pct(summary.get('pnl_pct') or 0)})",
        delta_positive=pnl >= 0,
        badge="Conta de treino",
        label="Dinheiro total na conta de treino",
        hint="Caixa livre + valor das ações. A renda de dividendos fica em Minha carteira → Renda esperada.",
        stats=[
            ("Livre no caixa", format_brl(summary["cash"]), "Para comprar ações"),
            ("Aplicado em ações", format_brl(summary["invested"]), "Pelo preço de hoje"),
            ("Dividendos (simulado)", format_brl(summary["dividends_received"]), "Já “recebidos” no treino"),
            ("Empresas", str(summary["n_positions"]), "Quantas você tem"),
        ],
    )
    with st.container(border=True):
        st.markdown("##### Sugestões da tese agora")
        st.caption(
            "Empresas com melhor encaixe em renda com qualidade. "
            "A nota junta lucro, dividendo sustentável, dívida e preço."
        )
        if not recs.empty:
            q, d, h, v = pillar_means(recs)
            render_thesis_pillars(q, d, h, v, heading="Média das 4 notas desta lista")
        render_core_sectors_card()
        if recs.empty:
            st.warning("Sem sugestões com os filtros atuais.")
        else:
            view = recs.copy()
            keep = [
                c
                for c in [
                    "ticker",
                    "name",
                    "sector",
                    "score_total",
                    "dividend_yield",
                    "roe",
                    "price",
                    "bucket",
                ]
                if c in view.columns
            ]
            show = view[keep].head(10).copy()
            if "dividend_yield" in show.columns:
                show["dividend_yield"] = show["dividend_yield"].map(
                    lambda x: format_pct(x) if x == x and x is not None else "—"
                )
            if "roe" in show.columns:
                show["roe"] = show["roe"].map(
                    lambda x: format_pct(x) if x == x and x is not None else "—"
                )
            st.dataframe(
                friendly_dataframe(show),
                width="stretch",
                hide_index=True,
                height=360,
            )

with col_right:
    with st.container(border=True):
        if holdings.empty:
            st.markdown("##### 💼 Carteira de Ações")
            st.caption("Sua carteira de treino ainda está 100% em caixa.")
            st.markdown(
                """
<div style="padding: 0.6rem 0; text-align: center;">
  <div style="font-size: 1.8rem; margin-bottom: 0.3rem;">🎯</div>
  <div style="font-size: 0.88rem; font-weight: 600; color: #F8FAFC;">Pronto para montar sua carteira?</div>
  <div style="font-size: 0.78rem; color: #94A3B8; margin-top: 0.2rem; margin-bottom: 0.6rem;">
    Aplique a tese com 1 clique para alocar o capital nas melhores ações da B3.
  </div>
</div>
""",
                unsafe_allow_html=True,
            )
            st.page_link(
                "app_pages/minha_carteira.py",
                label=APPLY_THESIS_LABEL,
                icon=":material/auto_awesome:",
                width="stretch",
            )
        else:
            st.plotly_chart(
                holdings_donut(
                    holdings,
                    center_value=format_brl(summary["invested"]),
                    title="Só o que está em ações (sem o caixa)",
                    height=280,
                ),
                width="stretch",
                config={"displayModeBar": False},
            )

    with st.container(border=True):
        st.markdown("##### Radar de Notícias")
        st.caption(
            "Mercado brasileiro (B3) e, quando o título cita, as ações da sua conta de treino."
        )
        if news is None or news.empty:
            st.caption("Nenhuma notícia recente disponível no momento.")
        else:
            render_news_feed_cards(news)

st.caption(
    "Overview em tempo de sessão · notícias de fontes públicas · "
    "não é recomendação de investimento."
)
