"""Teste no passado — visual compacto."""

from __future__ import annotations

from datetime import date

import plotly.graph_objects as go
import streamlit as st

from src.backtest.engine import BacktestConfig, run_backtest
from src.data.providers import get_provider
from src.data.universe import get_universe
from src.services import format_brl, format_pct
from src.ui.charts import holdings_donut
from src.ui.components import render_kpi_row, render_page_header
from src.ui.friendly import friendly_dataframe
from src.ui.shell import page_setup

page_setup()
render_page_header("Teste no passado", "Simulação da tese")

with st.sidebar:
    provider = st.selectbox(
        "Dados",
        options=["demo", "yfinance"],
        format_func=lambda x: "Modo treino" if x == "demo" else "Bolsa real",
        key="bt_provider",
    )
    start = st.date_input("Início", value=date(2022, 1, 3), key="bt_start")
    end = st.date_input("Fim", value=date.today(), key="bt_end")
    initial_cash = st.number_input(
        "Capital", min_value=1000.0, value=100_000.0, step=1000.0, key="bt_cash"
    )
    top_n = st.slider("Top N", 5, 25, 12, key="bt_top")
    rebalance = st.selectbox(
        "Ajuste",
        options=["M", "Q"],
        format_func=lambda x: "Mensal" if x == "M" else "Trimestral",
        key="bt_reb",
    )
    min_score = st.slider("Nota mín.", 0, 100, 55, key="bt_score")
    universe_mode = st.selectbox(
        "Universo",
        options=["sample", "full"],
        format_func=lambda x: "Amostra rápida" if x == "sample" else "Amplo",
        key="bt_univ",
    )
    run = st.button("Rodar", type="primary", width="stretch", key="bt_run")

if run:
    universe = get_universe()
    if universe_mode == "sample":
        universe = universe[:40]
    cfg = BacktestConfig(
        start=start.isoformat(),
        end=end.isoformat(),
        initial_cash=float(initial_cash),
        top_n=int(top_n),
        rebalance=rebalance,  # type: ignore[arg-type]
        min_score=float(min_score),
        universe=universe,
    )
    with st.spinner("Simulando…"):
        try:
            st.session_state["backtest_result"] = run_backtest(
                get_provider(provider), cfg  # type: ignore[arg-type]
            )
        except Exception as e:
            st.error(str(e))
            st.stop()

result = st.session_state.get("backtest_result")
if not result:
    st.info("Configure na lateral e clique em **Rodar**.")
    st.stop()

m = result.metrics
ret_cls = "up" if m["total_return"] >= 0 else "down"
render_kpi_row(
    [
        ("Final", format_brl(m["final_equity"]), None, None),
        ("Retorno", format_pct(m["total_return"]), None, ret_cls),
        ("CAGR", format_pct(m["cagr"]), None, None),
        ("Maior queda", format_pct(m["max_drawdown"]), None, "down"),
        ("Dividendos", format_brl(m["dividends_total"]), None, None),
    ]
)

eq = result.equity_curve
fig = go.Figure()
fig.add_trace(
    go.Scatter(
        x=eq["date"],
        y=eq["equity"],
        mode="lines",
        line={"color": "#A78BFA", "width": 2.5, "shape": "spline"},
        fill="tozeroy",
        fillcolor="rgba(167,139,250,0.16)",
        hovertemplate="%{x|%d/%m/%Y}<br>R$ %{y:,.2f}<extra></extra>",
    )
)
fig.update_layout(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    height=360,
    margin={"l": 40, "r": 16, "t": 40, "b": 40},
    title={"text": "Patrimônio ao longo do tempo", "font": {"size": 14, "color": "#CBD5E1"}},
    font={"color": "#94A3B8", "family": "Inter, sans-serif"},
    xaxis={"gridcolor": "rgba(36,48,68,0.55)", "color": "#64748B"},
    yaxis={"gridcolor": "rgba(36,48,68,0.55)", "color": "#64748B"},
    showlegend=False,
)
with st.container(border=True):
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})

c1, c2 = st.columns(2, gap="medium")
with c1:
    with st.container(border=True):
        if result.final_holdings is not None and not result.final_holdings.empty:
            st.plotly_chart(
                holdings_donut(
                    result.final_holdings,
                    center_value=format_brl(m["final_equity"]),
                    title="Carteira final",
                ),
                width="stretch",
                config={"displayModeBar": False},
            )
        else:
            st.caption("Sem posições finais.")
with c2:
    with st.container(border=True):
        if result.final_holdings is not None and not result.final_holdings.empty:
            st.dataframe(
                friendly_dataframe(result.final_holdings),
                width="stretch",
                hide_index=True,
                height=320,
            )
        else:
            st.caption("—")

with st.expander("Trades e dividendos"):
    t1, t2 = st.tabs(["Trades", "Dividendos"])
    with t1:
        st.dataframe(
            friendly_dataframe(result.trades)
            if result.trades is not None
            else result.trades,
            width="stretch",
            hide_index=True,
        )
    with t2:
        st.dataframe(
            friendly_dataframe(result.dividends)
            if result.dividends is not None
            else result.dividends,
            width="stretch",
            hide_index=True,
        )
