"""Teste no passado — onboarding explicativo + simulação."""

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
from src.ui.data_source import provider_selectbox
from src.ui.friendly import friendly_dataframe
from src.ui.shell import page_setup

page_setup()
render_page_header("Teste no passado", "Simulação da tese Quality Dividend")

# ── Controles ──────────────────────────────────────────────
with st.sidebar:
    st.markdown("##### Configurar o teste")
    provider = provider_selectbox(key="bt_provider", show_help=True)
    start = st.date_input("Comecei a investir em…", value=date(2022, 1, 3), key="bt_start")
    end = st.date_input("Parei de acompanhar em…", value=date.today(), key="bt_end")
    initial_cash = st.number_input(
        "Capital fictício (R$)",
        min_value=100.0,
        value=100_000.0,
        step=1000.0,
        key="bt_cash",
    )
    top_n = st.slider("Quantas ações manter", 5, 25, 12, key="bt_top")
    rebalance = st.selectbox(
        "Com que frequência reajustar a carteira?",
        options=["M", "Q"],
        format_func=lambda x: "Todo mês" if x == "M" else "A cada 3 meses",
        key="bt_reb",
    )
    min_score = st.slider("Nota mínima das ações", 0, 100, 55, key="bt_score")
    universe_mode = st.selectbox(
        "Quantas empresas analisar?",
        options=["sample", "full"],
        format_func=lambda x: (
            "Amostra rápida (~40 empresas)"
            if x == "sample"
            else "Universo amplo (pode demorar)"
        ),
        key="bt_univ",
    )
    run = st.button("Rodar simulação", type="primary", width="stretch", key="bt_run")

# ── Rodar ──────────────────────────────────────────────────
if run:
    if start >= end:
        st.error("A data de início precisa ser anterior à data de fim.")
    else:
        universe = get_universe()
        if universe_mode == "sample":
            universe = universe[:40]
        if provider == "yfinance" and universe_mode == "full":
            st.warning(
                "Universo amplo + bolsa real pode levar vários minutos. "
                "Prefira amostra rápida na primeira vez."
            )
        cfg = BacktestConfig(
            start=start.isoformat(),
            end=end.isoformat(),
            initial_cash=float(initial_cash),
            top_n=int(top_n),
            rebalance=rebalance,  # type: ignore[arg-type]
            min_score=float(min_score),
            universe=universe,
        )
        with st.spinner("Viajando no tempo… montando a carteira dia a dia."):
            try:
                st.session_state["backtest_result"] = run_backtest(
                    get_provider(provider), cfg  # type: ignore[arg-type]
                )
                st.session_state["backtest_ran_once"] = True
            except Exception as e:
                st.error(f"Falha na simulação: {e}")
                st.stop()

result = st.session_state.get("backtest_result")

# ── Estado: ainda não rodou ────────────────────────────────
if not result:
    st.markdown(
        """
Esta página responde a uma pergunta simples:

> **“E se eu tivesse seguido as sugestões desta tese desde uma data no passado?”**

Você não arrisca dinheiro real. É um **laboratório** com capital fictício.
"""
    )

    c1, c2 = st.columns(2, gap="medium")
    with c1:
        with st.container(border=True):
            st.markdown("#### O que é **Modo treino**?")
            st.markdown(
                """
- Usa um **mercado simulado** (números realistas, mas inventados).
- É **rápido**, funciona offline e é ótimo para **aprender o fluxo**.
- Os resultados **não** representam a B3 de verdade.

**Use na primeira vez.** Depois, se quiser, mude para bolsa real.
"""
            )
    with c2:
        with st.container(border=True):
            st.markdown("#### O que é **Bolsa real**?")
            st.markdown(
                """
- Busca **preços e dividendos históricos** de ações brasileiras (Yahoo Finance, tickers `.SA`).
- Pode ser **lento** e, às vezes, incompleto (fonte gratuita).
- Ainda assim, o **score de qualidade** no MVP usa um “retrato” atual — não o balanço exato de cada mês do passado.

Útil para experimentar, **sem** ser um backtest de auditoria.
"""
            )

    with st.container(border=True):
        st.markdown("#### Como a simulação funciona (em passos)")
        st.markdown(
            """
1. Você escolhe **quando começou**, **quando parou** e com **quanto** de dinheiro fictício.
2. Em cada reajuste (mensal ou trimestral), o app escolhe as **melhores ações** segundo a tese Quality Dividend.
3. A carteira é **rebalanceada** (compra/vende para ficar perto dos pesos sugeridos).
4. **Dividendos** do período são creditados no caixa (quando a fonte de dados tiver esse histórico).
5. No fim você vê: patrimônio final, retorno, maior queda, dividendos e a carteira final.
"""
        )

    m1, m2, m3 = st.columns(3)
    with m1:
        with st.container(border=True):
            st.markdown("##### 1. Escolha a fonte")
            st.caption("Modo treino = seguro e rápido.")
    with m2:
        with st.container(border=True):
            st.markdown("##### 2. Ajuste datas e capital")
            st.caption("Barra lateral → início, fim, capital.")
    with m3:
        with st.container(border=True):
            st.markdown("##### 3. Clique em Rodar")
            st.caption("Depois explore os gráficos e tabelas.")

    with st.expander("O que cada configuração significa?", icon=":material/help:"):
        st.markdown(
            f"""
| Controle | Significado |
|----------|-------------|
| **Fonte de dados** | Treino (simulado) ou bolsa real (Yahoo) |
| **Datas** | Período da “viagem no tempo” |
| **Capital fictício** | Dinheiro de mentira no dia inicial (agora: **{format_brl(float(initial_cash))}**) |
| **Quantas ações manter** | Tamanho da carteira em cada reajuste (Top N) |
| **Frequência** | Mensal ou trimestral — com que frequência realinha a carteira |
| **Nota mínima** | Filtro de qualidade (0–100); mais alto = mais exigente |
| **Universo** | Amostra rápida (~40) ou lista ampla de tickers B3 |

**Sugestão de primeiro teste:** Modo treino · amostra rápida · 2022 → hoje · capital R$ 100.000.
"""
        )

    with st.expander("Limitações importantes (leia com calma)", icon=":material/warning:"):
        st.markdown(
            """
- **Não é recomendação de investimento** e não garante resultado futuro.
- Preços/dividendos históricos vêm da fonte escolhida; o **score fundamental** no MVP
  ainda **não** reconstrói o balanço de cada empresa mês a mês no passado.
- Não modela corretagem, imposto, slippage nem liquidez.
- Performance passada **não** garante performance futura.
"""
        )

    st.success(
        "Quando estiver pronto, use a **barra lateral** e clique em **Rodar simulação**.",
        icon=":material/play_arrow:",
    )
    st.stop()

# ── Resultados ─────────────────────────────────────────────
m = result.metrics
ret_cls = "up" if m["total_return"] >= 0 else "down"

with st.container(border=True):
    st.markdown("#### Resultado em linguagem simples")
    gain = float(m["final_equity"]) - float(m["initial_cash"])
    if gain >= 0:
        st.markdown(
            f"Começando com **{format_brl(m['initial_cash'])}** em **{m['start']}**, "
            f"você teria terminado em **{m['end']}** com **{format_brl(m['final_equity'])}** "
            f"(lucro de **{format_brl(gain)}**, ou **{format_pct(m['total_return'])}**)."
        )
    else:
        st.markdown(
            f"Começando com **{format_brl(m['initial_cash'])}** em **{m['start']}**, "
            f"você teria terminado em **{m['end']}** com **{format_brl(m['final_equity'])}** "
            f"(prejuízo de **{format_brl(abs(gain))}**, ou **{format_pct(m['total_return'])}**)."
        )
    st.caption(
        f"Reajustes: {m.get('n_rebalances', '—')} · ordens: {m.get('n_trades', '—')} · "
        f"fonte: {m.get('provider', '—')}"
    )

render_kpi_row(
    [
        ("Patrimônio final", format_brl(m["final_equity"]), None, None),
        ("Retorno total", format_pct(m["total_return"]), None, ret_cls),
        ("Crescimento médio ao ano", format_pct(m["cagr"]), None, None),
        ("Maior queda", format_pct(m["max_drawdown"]), None, "down"),
        ("Dividendos no período", format_brl(m["dividends_total"]), None, None),
    ]
)

# KPIs vs benchmarks
ibov_r = m.get("ibov_return")
cdi_r = m.get("cdi_return")
if ibov_r is not None or cdi_r is not None:
    xs_ibov = m.get("excess_vs_ibov")
    xs_cdi = m.get("excess_vs_cdi")
    render_kpi_row(
        [
            (
                "Ibovespa (mesmo período)",
                format_pct(ibov_r) if ibov_r is not None else "—",
                None,
                None,
            ),
            (
                "CDI (mesmo período)",
                format_pct(cdi_r) if cdi_r is not None else "—",
                None,
                None,
            ),
            (
                "Vs Ibovespa",
                format_pct(xs_ibov) if xs_ibov is not None else "—",
                "acima" if (xs_ibov or 0) >= 0 else "abaixo",
                "up" if (xs_ibov or 0) >= 0 else "down",
            ),
            (
                "Vs CDI",
                format_pct(xs_cdi) if xs_cdi is not None else "—",
                "acima" if (xs_cdi or 0) >= 0 else "abaixo",
                "up" if (xs_cdi or 0) >= 0 else "down",
            ),
        ]
    )
    bm_meta = m.get("benchmark_meta") or {}
    st.caption(
        f"Fontes dos benchmarks · Ibovespa: {bm_meta.get('ibov_source', '—')} · "
        f"CDI: {bm_meta.get('cdi_source', '—')}"
    )

# Curva com benchmarks
eq = result.equity_curve
bm = getattr(result, "benchmarks", None)
fig = go.Figure()
fig.add_trace(
    go.Scatter(
        x=eq["date"],
        y=eq["equity"],
        mode="lines",
        name="Sua carteira (tese)",
        line={"color": "#A78BFA", "width": 2.8, "shape": "spline"},
        hovertemplate="%{x|%d/%m/%Y}<br>Carteira R$ %{y:,.2f}<extra></extra>",
    )
)
if bm is not None and not getattr(bm, "empty", True):
    if "ibovespa" in bm.columns and bm["ibovespa"].notna().any():
        fig.add_trace(
            go.Scatter(
                x=bm["date"],
                y=bm["ibovespa"],
                mode="lines",
                name="Ibovespa",
                line={"color": "#38BDF8", "width": 2, "shape": "spline"},
                hovertemplate="%{x|%d/%m/%Y}<br>Ibov R$ %{y:,.2f}<extra></extra>",
            )
        )
    if "cdi" in bm.columns and bm["cdi"].notna().any():
        fig.add_trace(
            go.Scatter(
                x=bm["date"],
                y=bm["cdi"],
                mode="lines",
                name="CDI",
                line={"color": "#34D399", "width": 2, "dash": "dot", "shape": "spline"},
                hovertemplate="%{x|%d/%m/%Y}<br>CDI R$ %{y:,.2f}<extra></extra>",
            )
        )
fig.update_layout(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    height=400,
    margin={"l": 40, "r": 16, "t": 40, "b": 40},
    title={
        "text": "Patrimônio: tese × Ibovespa × CDI",
        "font": {"size": 14, "color": "#CBD5E1"},
    },
    font={"color": "#94A3B8", "family": "Inter, sans-serif"},
    xaxis={"gridcolor": "rgba(36,48,68,0.55)", "color": "#64748B"},
    yaxis={"gridcolor": "rgba(36,48,68,0.55)", "color": "#64748B"},
    legend={
        "orientation": "h",
        "yanchor": "bottom",
        "y": 1.02,
        "x": 0,
        "bgcolor": "rgba(0,0,0,0)",
    },
)
with st.container(border=True):
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
    st.caption(
        "Todos começam com o mesmo capital fictício no primeiro dia, "
        "para comparar a evolução no mesmo período."
    )

c1, c2 = st.columns(2, gap="medium")
with c1:
    with st.container(border=True):
        if result.final_holdings is not None and not result.final_holdings.empty:
            st.plotly_chart(
                holdings_donut(
                    result.final_holdings,
                    center_value=format_brl(m["final_equity"]),
                    title="Carteira no fim do teste",
                ),
                width="stretch",
                config={"displayModeBar": False},
            )
        else:
            st.caption("Sem posições no fim.")
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

with st.expander("Ordens e dividendos do período", icon=":material/receipt_long:"):
    t1, t2 = st.tabs(["Compras e vendas", "Dividendos"])
    with t1:
        if result.trades is not None and not getattr(result.trades, "empty", True):
            st.dataframe(
                friendly_dataframe(result.trades),
                width="stretch",
                hide_index=True,
            )
        else:
            st.caption("Nenhuma ordem registrada.")
    with t2:
        if result.dividends is not None and not getattr(result.dividends, "empty", True):
            st.dataframe(
                friendly_dataframe(result.dividends),
                width="stretch",
                hide_index=True,
            )
        else:
            st.caption("Nenhum dividendo no período (ou a fonte não trouxe proventos).")

with st.expander("Lembrar das limitações", icon=":material/info:"):
    st.caption(
        "Ferramenta de estudo. Score fundamental do MVP não é point-in-time completo. "
        "Não inclui custos nem impostos. Não é recomendação de investimento."
    )

if st.button("Limpar resultado e ver o guia de novo", key="bt_clear"):
    st.session_state.pop("backtest_result", None)
    st.rerun()
