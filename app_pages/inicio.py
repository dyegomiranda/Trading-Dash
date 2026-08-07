"""Início — overview geral do programa."""

from __future__ import annotations

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
from src.ui.charts import holdings_donut
from src.ui.components import render_kpi_row, render_page_header
from src.ui.friendly import friendly_dataframe
from src.ui.shell import page_setup
from src.ui.wallet import render_wallet_balance

page_setup()

render_page_header("Início", "Visão geral · tese Quality Dividend")

with st.sidebar:
    st.markdown("##### Dados")
    provider = st.selectbox(
        "Fonte",
        options=["demo", "yfinance"],
        format_func=lambda x: "Modo treino" if x == "demo" else "Bolsa real",
        key="home_provider",
    )
    if st.button("Atualizar overview", width="stretch", key="home_refresh"):
        st.cache_data.clear()
        st.rerun()


@st.cache_data(ttl=1800, show_spinner=False)
def _scored(provider: str):
    return load_scored_universe(provider_name=provider)  # type: ignore[arg-type]


with st.spinner("Carregando overview…"):
    result = _scored(provider)
    scored = result.scored
    filtered = result.filtered
    recs = recommend_weights(
        filtered if not filtered.empty else scored,
        top_n=10,
    )
    portfolio = load_portfolio("paper-main")
    prices = prices_dict_from_fundamentals(scored)
    summary = portfolio.summary(prices)
    holdings = portfolio.holdings_frame(prices)
    watch = recs["ticker"].head(8).tolist() if not recs.empty else []
    # Sempre busca notícias reais (Google News RSS); provider só muda os tickers/fonte extra
    news = fetch_headlines(watch, provider="yfinance", limit=10)

# KPIs rápidos
pnl = float(summary.get("pnl") or 0)
render_kpi_row(
    [
        ("Patrimônio (treino)", format_brl(summary["equity"]), format_pct(summary.get("pnl_pct") or 0), "up" if pnl >= 0 else "down"),
        ("Em carteira", str(summary.get("n_positions") or 0), None, None),
        ("Sugestões da tese", str(len(recs)), None, None),
        ("Universo analisado", str(len(scored)), None, None),
    ]
)

# Wallet + donut
left, right = st.columns([1.15, 1], gap="medium")
with left:
    render_wallet_balance(
        total=format_brl(summary["equity"]),
        delta=f"{format_brl(pnl)} ({format_pct(summary.get('pnl_pct') or 0)})",
        delta_positive=pnl >= 0,
        badge="Paper · overview",
        stats=[
            ("Caixa", format_brl(summary["cash"])),
            ("Investido", format_brl(summary["invested"])),
            ("Dividendos", format_brl(summary["dividends_received"])),
            ("Ativos", str(summary["n_positions"])),
        ],
    )
with right:
    with st.container(border=True):
        if holdings.empty:
            st.markdown("##### Carteira")
            st.caption("Vazia — monte em **Minha carteira → Operar**.")
        else:
            st.plotly_chart(
                holdings_donut(
                    holdings,
                    center_value=format_brl(summary["invested"]),
                    title="Sua carteira agora",
                ),
                width="stretch",
                config={"displayModeBar": False},
            )

# Radar + notícias
c1, c2 = st.columns([1.2, 1], gap="medium")
with c1:
    with st.container(border=True):
        st.markdown("##### Radar da tese")
        st.caption("Principais ações ranqueadas agora (Quality Dividend).")
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
