"""Descubra ações — ranking guiado + histórico de preços com vários períodos."""

from __future__ import annotations

from datetime import datetime, timedelta

import streamlit as st

from src.config import THESIS_VERSION, get_settings
from src.data.providers import get_provider
from src.data.quality import coverage_summary, enrich_fundamentals_quality
from src.services import format_pct, load_scored_universe
from src.thesis.scoring import apply_filters, recommend_weights
from src.ui.charts import holdings_donut, price_history_chart, score_bars
from src.ui.components import render_kpi_row, render_page_header, render_plain_help
from src.ui.data_source import provider_selectbox, render_data_quality_banner
from src.ui.friendly import PRICE_PERIODS, friendly_dataframe, render_glossary_expander
from src.ui.shell import page_setup
from src.ui.trust import render_friendly_safety_note, render_trust_strip

page_setup()
render_page_header(
    "Descubra ações",
    "Notas da tese em português claro + histórico do preço",
)

with st.sidebar:
    st.markdown("##### Filtros")
    provider = provider_selectbox(key="disc_provider", label="Fonte de dados", show_help=True)
    min_score = st.slider(
        "Nota mínima do app",
        0,
        100,
        55,
        key="disc_min_score",
        help="Só entram empresas com nota igual ou acima deste valor (0–100).",
    )
    top_n = st.slider(
        "Quantas sugestões mostrar",
        5,
        30,
        15,
        key="disc_top_n",
    )
    strict = st.toggle(
        "Filtros mais rigorosos",
        value=False,
        key="disc_strict",
        help="Exige mais qualidade e sustentabilidade dos dividendos.",
    )
    period_labels = [p[0] for p in PRICE_PERIODS]
    period_choice = st.selectbox(
        "Período do gráfico de preço",
        options=period_labels,
        index=3,  # 1 ano
        key="disc_hist_period",
        help="Do curto prazo (1 mês) até o máximo que a fonte tiver de histórico.",
    )
    hist_days = dict(PRICE_PERIODS).get(period_choice)
    run = st.button("Atualizar lista", type="primary", width="stretch", key="disc_run")
    render_glossary_expander()

render_data_quality_banner(provider)

render_plain_help(
    "Como usar esta página (3 minutos)",
    f"""
1. Olhe as **notas** (0–100): quanto maior, melhor encaixe na tese de renda com qualidade (v{THESIS_VERSION})
2. Veja o **gráfico de preço** em vários períodos (1 mês → máximo disponível)
3. Quando achar razoável, vá em **Minha carteira** e clique em *Montar carteira com a tese*

**Dica:** “Quanto paga de dividendo” alto demais pode ser armadilha — a nota do app tenta equilibrar isso  
e marca a **qualidade dos dados** de cada empresa.
""",
)


@st.cache_data(ttl=3600, show_spinner=False)
def _cached_score(provider: str, min_score: float, strict: bool):
    return load_scored_universe(
        provider_name=provider,  # type: ignore[arg-type]
        min_score=min_score,
        strict_filters=strict,
        universe_mode="auto",
    )


@st.cache_data(ttl=3600, show_spinner=False)
def _price_hist(provider: str, ticker: str, days: int | None):
    end = datetime.utcnow()
    if days is None:
        # ~20 anos ou o que a fonte tiver
        start = end - timedelta(days=365 * 20)
    else:
        start = end - timedelta(days=int(days) + 5)
    prov = get_provider(provider)  # type: ignore[arg-type]
    hist = prov.get_price_history([ticker], start=start, end=end)
    if hist is None or hist.empty:
        return hist
    return hist[hist["ticker"] == ticker].copy() if "ticker" in hist.columns else hist


need_load = (
    run
    or "ranking_loaded" not in st.session_state
    or st.session_state.get("provider") != provider
)
if need_load:
    try:
        with st.spinner(
            "Calculando ranking… (Bolsa real: até ~30s na 1ª carga; depois usa cache)"
            if provider == "yfinance"
            else "Calculando ranking de treino…"
        ):
            scored = _cached_score(provider, float(min_score), strict)
            st.session_state["ranking_loaded"] = True
            scored_df = scored.scored
            if scored_df is not None and not scored_df.empty:
                scored_df = enrich_fundamentals_quality(scored_df)
            st.session_state["scored_df"] = scored_df
            st.session_state["provider"] = provider
    except Exception as e:
        st.error(f"Não deu para carregar os dados: {e}")
        st.info("Tente **Modo treino** na barra lateral para carregar na hora.")
        st.stop()

scored_df = st.session_state.get("scored_df")
if scored_df is None or getattr(scored_df, "empty", True):
    st.warning("Sem dados de mercado. Clique em **Atualizar lista** ou use Modo treino.")
    st.stop()

if "quality_level" not in scored_df.columns:
    scored_df = enrich_fundamentals_quality(scored_df)

cov = coverage_summary(scored_df)
render_trust_strip(provider=provider, coverage=cov)

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
    max_sector_pct=settings.max_sector_pct,
)

render_kpi_row(
    [
        ("Empresas analisadas", str(len(scored_df)), None, None),
        ("Passaram na nota mínima", str(len(filtered)), None, None),
        ("Sugestões na lista", str(len(recs)), None, None),
        (
            "Cobertura de dados",
            cov.get("trust_label", "—")[:22],
            None,
            None,
        ),
    ]
)

if recs.empty:
    st.warning("Nenhuma ação passou. Baixe a **nota mínima** na barra lateral.")
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
                score_bars(plot, title="Maiores notas da lista"),
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
                        title="Fatias sugeridas na carteira",
                    ),
                    width="stretch",
                    config={"displayModeBar": False},
                )
            st.caption(
                "A rosca mostra **quanto %** cada ação teria numa carteira modelo da tese — "
                "não é o preço da ação."
            )

    st.markdown("##### Histórico do preço")
    st.caption(
        f"Período selecionado: **{period_choice}**. "
        "Mude na barra lateral (1 mês até o máximo disponível)."
    )
    tickers = recs["ticker"].astype(str).tolist()
    pick = st.selectbox(
        "Escolha uma ação para o gráfico principal",
        options=tickers,
        key="disc_hist_ticker",
    )
    # Atalhos de período na própria página (além da sidebar)
    period_labels_ui = period_labels
    period_quick = st.segmented_control(
        "Atalho de período",
        options=period_labels_ui,
        default=period_choice,
        key="disc_period_seg",
        label_visibility="collapsed",
    )
    active_period = period_quick or period_choice
    active_days = dict(PRICE_PERIODS).get(active_period)

    try:
        with st.spinner(f"Carregando histórico de {pick} ({active_period})…"):
            hist = _price_hist(provider, pick, active_days)
    except Exception as e:
        st.warning(f"Não foi possível carregar o histórico: {e}")
        hist = None

    with st.container(border=True):
        st.plotly_chart(
            price_history_chart(
                hist if hist is not None else __import__("pandas").DataFrame(),
                ticker=pick,
                title=f"{pick} · {active_period}",
            ),
            width="stretch",
            config={"displayModeBar": False},
        )
        if hist is not None and not getattr(hist, "empty", True) and "close" in hist.columns:
            first = float(hist.sort_values("date").iloc[0]["close"])
            last = float(hist.sort_values("date").iloc[-1]["close"])
            if first > 0:
                chg = (last / first) - 1.0
                st.caption(
                    f"No período: de {first:.2f} para {last:.2f} "
                    f"({chg:+.1%} no total do gráfico — passado ≠ futuro)."
                )

    top3 = tickers[:3]
    if len(top3) > 1:
        st.markdown("##### Comparativo rápido (top 3 da lista)")
        cols = st.columns(len(top3))
        for col, t in zip(cols, top3):
            with col:
                try:
                    h = _price_hist(provider, t, active_days)
                except Exception:
                    h = None
                with st.container(border=True):
                    st.plotly_chart(
                        price_history_chart(
                            h if h is not None else __import__("pandas").DataFrame(),
                            ticker=t,
                            title=t,
                        ),
                        width="stretch",
                        config={"displayModeBar": False},
                    )

    st.markdown("##### Tabela das sugestões")
    st.caption(
        "Nomes em português. Passe o mouse nos cabeçalhos quando o navegador permitir; "
        "o dicionário está na barra lateral."
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
            "quality_label",
            "data_completeness_pct",
            "dividend_yield",
            "roe",
            "target_weight",
            "price",
        ]
        if c in view.columns
    ]
    st.dataframe(
        friendly_dataframe(
            view[keep],
            extra_map={
                "quality_label": "Qualidade dos dados",
                "data_completeness_pct": "Completude dos dados (%)",
            },
        ),
        width="stretch",
        hide_index=True,
        height=420,
    )

    st.info(
        "Próximo passo: abra **Minha carteira** → **Montar carteira** → "
        "**Montar carteira com a tese** (montagem automática com diversificação).",
        icon=":material/arrow_forward:",
    )
    render_friendly_safety_note()

st.session_state["last_recs"] = recs
st.session_state["last_filtered"] = filtered
st.session_state["last_fundamentals"] = scored_df
