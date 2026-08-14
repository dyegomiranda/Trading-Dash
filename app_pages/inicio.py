"""Início — overview geral do programa."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from src.data.news import fetch_headlines
from src.portfolio.paper import load_portfolio
from src.services import (
    format_brl,
    format_pct,
    load_scored_universe,
    prices_dict_from_fundamentals,
)
from src.thesis.scoring import recommend_weights
from src.ai.coach import narrative_thesis, summarize_headlines
from src.ui.charts import holdings_donut
from src.ui.components import render_journey, render_kpi_row, render_page_header, render_plain_help
from src.ui.data_source import provider_selectbox, render_data_quality_banner
from src.ui.friendly import JOURNEY_STEPS, friendly_dataframe
from src.ui.onboarding import render_onboarding_if_needed, render_onboarding_reset_button
from src.ui.shell import page_setup
from src.ui.wallet import render_wallet_balance

page_setup()

render_page_header("Início", "Comece aqui · caminho guiado para montar uma carteira de treino")

with st.sidebar:
    st.markdown("##### Dados")
    provider = provider_selectbox(key="home_provider", label="Fonte", show_help=True)
    if st.button("Atualizar overview", width="stretch", key="home_refresh"):
        st.cache_data.clear()
        st.rerun()
    render_onboarding_reset_button()

# Tour na primeira visita
if render_onboarding_if_needed():
    st.stop()

render_data_quality_banner(provider)


@st.cache_data(ttl=1800, show_spinner=False)
def _scored(provider: str):
    # yfinance: scan core (~40) — full universe trava a UI
    return load_scored_universe(
        provider_name=provider,  # type: ignore[arg-type]
        universe_mode="auto",
    )


# Carteira paper é local e instantânea — mostra mesmo se Yahoo demorar
portfolio = load_portfolio("paper-main")
scored = pd.DataFrame()
filtered = scored
recs = scored
prices: dict = {}
news = pd.DataFrame()

try:
    with st.spinner(
        "Carregando overview… (Bolsa real: até ~15–30s na 1ª vez; depois cache)"
        if provider == "yfinance"
        else "Carregando overview…"
    ):
        result = _scored(provider)
        scored = result.scored
        filtered = result.filtered
        recs = recommend_weights(
            filtered if not filtered.empty else scored,
            top_n=10,
        )
        prices = prices_dict_from_fundamentals(scored)
except Exception as e:
    st.error(f"Falha ao carregar mercado: {e}")
    scored = pd.DataFrame()
    recs = scored

summary = portfolio.summary(prices)
holdings = portfolio.holdings_frame(prices)
watch = (
    recs["ticker"].head(6).tolist()
    if not recs.empty and "ticker" in recs.columns
    else ["ITUB4", "PETR4", "VALE3"]
)
try:
    news = fetch_headlines(watch, provider="yfinance", limit=6, timeout_sec=6.0)
except Exception:
    news = pd.DataFrame()

# Jornada + KPIs
has_pos = not holdings.empty
render_journey(
    JOURNEY_STEPS,
    current=2 if has_pos else (0 if float(summary.get("equity") or 0) < 100 else 1),
    completed_through=2 if has_pos else (0 if float(summary.get("equity") or 0) >= 100 else -1),
)
render_plain_help(
    "Seu caminho em 4 passos",
    """
1. **Descubra ações** — veja notas e o gráfico de preço em vários períodos  
2. **Minha carteira → Montar carteira** — defina o capital e clique em *Montar com a tese*  
3. **Renda esperada** — entenda quanto poderia render em dividendos (estimativa)  
4. **Teste no passado** (opcional) — veja como a ideia se comportaria historicamente  

Tudo aqui é **conta de treino** (dinheiro de mentira), para aprender com segurança.
""",
)

# Coach da tese (IA se XAI_API_KEY; senão texto local)
try:
    tops = (
        recs["ticker"].astype(str).head(5).tolist()
        if not recs.empty and "ticker" in recs.columns
        else []
    )
    avg_sc = (
        float(recs["score_total"].mean())
        if not recs.empty and "score_total" in recs.columns
        else None
    )
    narr = narrative_thesis(
        n_suggestions=int(len(recs)),
        avg_score=avg_sc,
        top_tickers=tops,
        provider=provider,
    )
    with st.container(border=True):
        st.markdown("##### Coach da tese")
        st.markdown(narr["text"])
        st.caption(
            "Texto com IA (SpaceXAI/xAI)"
            if narr.get("source") == "ia"
            else "Texto local · defina a variável de ambiente XAI_API_KEY para ativar a IA"
        )
except Exception:
    pass

pnl = float(summary.get("pnl") or 0)
render_kpi_row(
    [
        ("Dinheiro na conta de treino", format_brl(summary["equity"]), format_pct(summary.get("pnl_pct") or 0), "up" if pnl >= 0 else "down"),
        ("Empresas na carteira", str(summary.get("n_positions") or 0), None, None),
        ("Sugestões da tese agora", str(len(recs)), None, None),
        ("Empresas analisadas", str(len(scored)), None, None),
    ]
)

left, right = st.columns([1.15, 1], gap="medium")
with left:
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
with right:
    with st.container(border=True):
        if holdings.empty:
            st.markdown("##### Sua carteira")
            st.caption("Ainda vazia. Abra **Minha carteira → Montar carteira** e monte com a tese.")
        else:
            st.plotly_chart(
                holdings_donut(
                    holdings,
                    center_value=format_brl(summary["invested"]),
                    title="Só o que está em ações (sem o caixa)",
                ),
                width="stretch",
                config={"displayModeBar": False},
            )

# Radar + notícias
c1, c2 = st.columns([1.2, 1], gap="medium")
with c1:
    with st.container(border=True):
        st.markdown("##### Radar da tese (top da lista)")
        st.caption(
            "Empresas com melhor nota para a ideia de renda com qualidade. "
            "Nomes em português na tabela."
        )
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

with c2:
    with st.container(border=True):
        st.markdown("##### Headlines reais")
        st.caption("Matérias via Google News / Yahoo — clique para abrir a fonte.")
        if news is None or news.empty:
            st.warning(
                "Não foi possível carregar notícias agora (rede/API). "
                "Tente atualizar o overview."
            )
        else:
            for _, row in news.iterrows():
                tag = str(row.get("tag") or "mercado")
                ticker = str(row.get("ticker") or "")
                title = str(row.get("title") or "")
                src = str(row.get("source") or "")
                when = str(row.get("published") or "")
                url = row.get("url")
                head = f"**{ticker}** · {tag}" if ticker else tag
                if url:
                    st.markdown(f"{head}  \n[{title}]({url})  \n*{src} · {when}*")
                else:
                    st.markdown(f"{head}  \n{title}  \n*{src} · {when}*")
                st.markdown("")

st.caption(
    "Overview em tempo de sessão · notícias de fontes públicas · "
    "não é recomendação de investimento."
)
