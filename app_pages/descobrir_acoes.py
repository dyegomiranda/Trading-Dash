"""Descubra ações — ranking + histórico de preços."""

from __future__ import annotations

from datetime import datetime, timedelta

import streamlit as st

from src.config import get_settings
from src.data.providers import get_provider
from src.services import format_pct, load_scored_universe
from src.thesis.scoring import apply_filters, recommend_weights
from src.ui.charts import holdings_donut, price_history_chart, score_bars
from src.ui.components import render_kpi_row, render_page_header
from src.ui.data_source import provider_selectbox, render_data_quality_banner
from src.ui.friendly import friendly_dataframe
from src.ui.shell import page_setup

page_setup()
render_page_header("Descubra ações", "Notas da tese + histórico")

with st.sidebar:
    provider = provider_selectbox(key="disc_provider", label="Dados", show_help=True)
    min_score = st.slider("Nota mínima", 0, 100, 55, key="disc_min_score")
    top_n = st.slider("Top N", 5, 30, 15, key="disc_top_n")
    strict = st.toggle("Filtros rigorosos", value=False, key="disc_strict")
    hist_days = st.select_slider(
        "Histórico (dias)",
        options=[90, 180, 365, 730],
        value=365,
        key="disc_hist_days",
    )
    run = st.button("Atualizar", type="primary", width="stretch", key="disc_run")

render_data_quality_banner(provider)


@st.cache_data(ttl=3600, show_spinner=False)
def _cached_score(provider: str, min_score: float, strict: bool):
    return load_scored_universe(
        provider_name=provider,  # type: ignore[arg-type]
        min_score=min_score,
        strict_filters=strict,
    )


@st.cache_data(ttl=3600, show_spinner=False)
def _price_hist(provider: str, ticker: str, days: int):
    end = datetime.utcnow()
    start = end - timedelta(days=int(days) + 5)
    prov = get_provider(provider)  # type: ignore[arg-type]
    hist = prov.get_price_history([ticker], start=start, end=end)
    if hist is None or hist.empty:
        return hist
    return hist[hist["ticker"] == ticker].copy() if "ticker" in hist.columns else hist


if run or "ranking_loaded" not in st.session_state:
    with st.spinner("Calculando…"):
        scored = _cached_score(provider, float(min_score), strict)
        st.session_state["ranking_loaded"] = True
        st.session_state["scored_df"] = scored.scored
        st.session_state["provider"] = provider

scored_df = st.session_state.get("scored_df")
if scored_df is None:
    st.info("Clique em **Atualizar** na barra lateral.")
    st.stop()

if st.session_state.get("provider") != provider:
    with st.spinner("Recarregando…"):
        scored = _cached_score(provider, float(min_score), strict)
        scored_df = scored.scored
        st.session_state["scored_df"] = scored_df
        st.session_state["provider"] = provider

filtered, rejected = apply_filters(
    scored_df, min_score=float(min_score), strict=strict
)
settings = get_settings()
recs = recommend_weights(
    filtered if not filtered.empty else scored_df,
    top_n=top_n,
    core_weight=settings.core_weight,
    satellite_weight=settings.satellite_weight,
    max_position_pct=settings.max_position_pct,
)

render_kpi_row(
    [
        ("Analisadas", str(len(scored_df)), None, None),
        ("Aprovadas", str(len(filtered)), None, None),
        ("Sugestões", str(len(recs)), None, None),
        ("Modo", "Treino" if provider == "demo" else "Bolsa", None, None),
    ]
)

if recs.empty:
    st.warning("Nenhuma ação passou. Baixe a nota mínima.")
else:
    left, right = st.columns([1.15, 1], gap="medium")
    with left:
        with st.container(border=True):
            plot = recs.copy()
            plot["bucket"] = (
                plot["bucket"]
                .map({"core": "Base", "satellite": "Complemento"})
                .fillna(plot["bucket"])
            )
            st.plotly_chart(
                score_bars(plot, title="Top notas"),
                width="stretch",
                config={"displayModeBar": False},
            )
    with right:
        with st.container(border=True):
            if "target_weight" in recs.columns and recs["target_weight"].sum() > 0:
                pie_df = recs.copy()
                pie_df["market_value"] = pie_df["target_weight"]
                st.plotly_chart(
                    holdings_donut(
                        pie_df,
                        center_value=f"Top {len(recs)}",
                        title="Pesos sugeridos",
                    ),
                    width="stretch",
                    config={"displayModeBar": False},
                )

    st.markdown("##### Desempenho histórico")
    tickers = recs["ticker"].astype(str).tolist()
    pick = st.selectbox(
        "Escolha uma ação para ver o gráfico",
        options=tickers,
        key="disc_hist_ticker",
    )
    with st.spinner(f"Carregando histórico de {pick}…"):
        hist = _price_hist(provider, pick, int(hist_days))
    with st.container(border=True):
        st.plotly_chart(
            price_history_chart(
                hist if hist is not None else __import__("pandas").DataFrame(),
                ticker=pick,
                title=f"{pick} · últimos {hist_days} dias",
            ),
            width="stretch",
            config={"displayModeBar": False},
        )

    # mini grade com top 3 históricos
    top3 = tickers[:3]
    if len(top3) > 1:
        cols = st.columns(len(top3))
        for col, t in zip(cols, top3):
            with col:
                h = _price_hist(provider, t, int(hist_days))
                with st.container(border=True):
                    st.plotly_chart(
                        price_history_chart(h if h is not None else __import__("pandas").DataFrame(), ticker=t, title=t),
                        width="stretch",
                        config={"displayModeBar": False},
                    )

    view = recs.copy()
    for col in ("dividend_yield", "roe", "payout", "target_weight"):
        if col in view.columns:
            view[col] = view[col].map(
                lambda x: format_pct(x, 1) if x == x and x is not None else "—"
            )
    keep = [
        c
        for c in [
            "ticker",
            "name",
            "sector",
            "bucket",
            "score_total",
            "dividend_yield",
            "roe",
            "target_weight",
            "price",
        ]
        if c in view.columns
    ]
    st.dataframe(
        friendly_dataframe(view[keep]),
        width="stretch",
        hide_index=True,
        height=420,
    )

st.session_state["last_recs"] = recs
st.session_state["last_filtered"] = filtered
st.session_state["last_fundamentals"] = scored_df
