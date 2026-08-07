"""Minha carteira — dashboard + operar com capital e alocações manuais."""

from __future__ import annotations

import json

import pandas as pd
import streamlit as st

from src.config import get_settings
from src.data.providers import get_provider
from src.data.universe import normalize_ticker
from src.portfolio.income import project_income
from src.portfolio.paper import PaperPortfolio, load_portfolio, save_portfolio
from src.services import format_brl, format_pct, prices_dict_from_fundamentals
from src.thesis.scoring import recommend_weights, score_universe
from src.ui.charts import (
    holdings_donut,
    income_area,
    sector_bars,
    sector_breakdown_from_holdings,
)
from src.ui.components import render_page_header
from src.ui.friendly import friendly_dataframe
from src.ui.shell import page_setup
from src.ui.wallet import render_asset_rows, render_wallet_balance

page_setup()
render_page_header("Minha carteira", "Conta de treino")

with st.sidebar:
    st.markdown("##### Conta")
    portfolio_name = st.text_input("Carteira", value="paper-main", key="pf_name")
    provider = st.selectbox(
        "Dados",
        options=["demo", "yfinance"],
        format_func=lambda x: "Modo treino" if x == "demo" else "Bolsa real",
        key="pf_provider",
    )
    if st.button("Atualizar", icon=":material/refresh:", width="stretch", key="pf_refresh"):
        st.cache_data.clear()
        st.rerun()


@st.cache_data(ttl=3600, show_spinner=False)
def _raw_fundamentals(provider: str):
    return get_provider(provider).get_fundamentals()  # type: ignore[arg-type]


@st.cache_data(ttl=3600, show_spinner=False)
def _scored_table(provider: str):
    raw = _raw_fundamentals(provider)
    return score_universe(raw).scored


portfolio = load_portfolio(portfolio_name)
fundamentals = _raw_fundamentals(provider)
scored_table = _scored_table(provider)
prices = prices_dict_from_fundamentals(
    scored_table if not scored_table.empty else fundamentals
)
summary = portfolio.summary(prices)
holdings = portfolio.holdings_frame(prices)

# Feedback persistente da última aplicação de sugestões
if st.session_state.get("pf_flash"):
    flash = st.session_state.pop("pf_flash")
    kind = flash.get("kind", "success")
    msg = flash.get("msg", "")
    if kind == "success":
        st.success(msg, icon=":material/check_circle:")
        if flash.get("details"):
            with st.expander("Ver o que mudou", expanded=True):
                st.dataframe(pd.DataFrame(flash["details"]), width="stretch", hide_index=True)
    elif kind == "warning":
        st.warning(msg)
    else:
        st.error(msg)

pnl_abs = float(summary.get("pnl") or 0)
pnl_pct = float(summary.get("pnl_pct") or 0)
render_wallet_balance(
    total=format_brl(summary["equity"]),
    delta=f"{format_brl(pnl_abs)}  ({format_pct(pnl_pct)})",
    delta_positive=pnl_abs >= 0,
    badge="Paper · BRL",
    stats=[
        ("Caixa", format_brl(summary["cash"])),
        ("Investido", format_brl(summary["invested"])),
        ("Dividendos", format_brl(summary["dividends_received"])),
        ("Ativos", str(summary["n_positions"])),
    ],
)

tab_dash, tab_trade, tab_income, tab_more = st.tabs(
    ["Dashboard", "Operar", "Renda", "Mais"]
)

with tab_dash:
    if holdings.empty:
        st.info(
            "Carteira vazia. Vá em **Operar** para definir o capital e aplicar a tese "
            "ou alocar manualmente.",
            icon=":material/info:",
        )
    else:
        invested = float(summary.get("invested") or holdings["market_value"].sum())
        sectors = sector_breakdown_from_holdings(
            holdings, scored_table if not scored_table.empty else fundamentals
        )

        c1, c2 = st.columns(2, gap="medium")
        with c1:
            with st.container(border=True):
                st.plotly_chart(
                    holdings_donut(
                        holdings,
                        center_value=format_brl(invested),
                        title="Patrimônio investido",
                    ),
                    width="stretch",
                    config={"displayModeBar": False},
                )
        with c2:
            with st.container(border=True):
                if sectors.empty:
                    st.caption("Sem dados de setor.")
                else:
                    st.plotly_chart(
                        sector_bars(sectors, title="Divisão por setor"),
                        width="stretch",
                        config={"displayModeBar": False},
                    )

        if not sectors.empty:
            c3, c4 = st.columns(2, gap="medium")
            with c3:
                with st.container(border=True):
                    st.plotly_chart(
                        holdings_donut(
                            sectors.rename(
                                columns={"sector": "ticker", "value": "market_value"}
                            ),
                            center_value=f"{len(sectors)} setores",
                            title="Setores (rosca)",
                        ),
                        width="stretch",
                        config={"displayModeBar": False},
                    )
            with c4:
                with st.container(border=True):
                    top = holdings.nlargest(min(8, len(holdings)), "market_value").copy()
                    top["pct"] = top["market_value"] / top["market_value"].sum()
                    st.plotly_chart(
                        sector_bars(
                            top.rename(
                                columns={"ticker": "sector", "market_value": "value"}
                            )[["sector", "value", "pct"]],
                            title="Maiores posições",
                        ),
                        width="stretch",
                        config={"displayModeBar": False},
                    )

        st.markdown("##### Ativos")
        name_map = {}
        name_src = scored_table if not scored_table.empty else fundamentals
        if not name_src.empty:
            for _, r in name_src.iterrows():
                name_map[str(r["ticker"])] = str(r.get("name") or r["ticker"])
        asset_rows = []
        for _, r in holdings.iterrows():
            t = str(r["ticker"])
            name = name_map.get(t, t)
            bucket = str(r.get("bucket") or "")
            bucket_pt = (
                "Base"
                if bucket == "core"
                else ("Complemento" if bucket == "satellite" else bucket)
            )
            pnl = float(r.get("pnl") or 0)
            pnl_p = float(r.get("pnl_pct") or 0)
            shares = float(r["shares"])
            shares_s = f"{shares:,.2f} un".replace(",", "X").replace(".", ",").replace("X", ".")
            asset_rows.append(
                (
                    t,
                    f"{name} · {bucket_pt}" if bucket_pt else name,
                    shares_s,
                    format_brl(float(r["price"])),
                    format_brl(float(r["market_value"])),
                    f"{format_brl(pnl)} ({format_pct(pnl_p)})",
                    pnl >= 0,
                )
            )
        render_asset_rows(asset_rows)

with tab_trade:
    st.markdown("##### 1. Capital de treino")
    with st.container(border=True):
        cc1, cc2, cc3 = st.columns([1.2, 1, 1])
        with cc1:
            new_capital = st.number_input(
                "Patrimônio total (R$)",
                min_value=1000.0,
                value=float(summary.get("equity") or portfolio.initial_cash or 100_000.0),
                step=1000.0,
                key="pf_capital_input",
            )
        with cc2:
            reset_pos = st.checkbox(
                "Zerar posições ao aplicar",
                value=False,
                help="Se marcado, vende tudo (simulado) e deixa 100% em caixa com o novo capital.",
            )
        with cc3:
            st.write("")
            st.write("")
            if st.button("Salvar capital", type="primary", width="stretch", key="pf_save_cap"):
                try:
                    portfolio.set_capital(
                        float(new_capital), prices=prices, reset_positions=reset_pos
                    )
                    save_portfolio(portfolio)
                    st.session_state["pf_flash"] = {
                        "kind": "success",
                        "msg": f"Capital atualizado para {format_brl(new_capital)}.",
                    }
                    st.rerun()
                except Exception as e:
                    st.error(str(e))

    st.markdown("##### 2. Aplicar sugestões da tese")
    with st.container(border=True):
        top_n = st.slider("Nº de empresas na carteira", 5, 20, 12, key="pf_top_n")
        st.caption(
            "Usa a tese Quality Dividend, escolhe as melhores ações e rebalanceia "
            "seu patrimônio de treino automaticamente."
        )
        if st.button(
            "Aplicar sugestões da tese",
            type="primary",
            width="stretch",
            key="pf_apply",
            icon=":material/auto_awesome:",
        ):
            with st.spinner("Calculando ranking e executando ordens…"):
                try:
                    settings = get_settings()
                    raw = _raw_fundamentals(provider)
                    scored = score_universe(raw, min_score=settings.rebalance_min_score)
                    base = (
                        scored.filtered
                        if not scored.filtered.empty
                        else scored.scored
                    )
                    if base.columns.duplicated().any():
                        base = base.loc[:, ~base.columns.duplicated(keep="last")]
                    recs = recommend_weights(
                        base,
                        top_n=top_n,
                        core_weight=settings.core_weight,
                        satellite_weight=settings.satellite_weight,
                        max_position_pct=settings.max_position_pct,
                    )
                    if recs.empty:
                        st.session_state["pf_flash"] = {
                            "kind": "warning",
                            "msg": "Nenhuma ação passou nos filtros da tese. "
                            "Reduza a nota mínima em Descubra ações ou use modo treino.",
                        }
                        st.rerun()

                    tickers = recs["ticker"].astype(str).tolist()
                    weights = dict(
                        zip(tickers, recs["target_weight"].astype(float).tolist())
                    )
                    buckets = dict(zip(tickers, recs["bucket"].astype(str).tolist()))
                    px = prices_dict_from_fundamentals(scored.scored) or prices
                    missing_px = [t for t in tickers if not px.get(t)]
                    if missing_px:
                        st.warning(
                            f"Sem preço para: {', '.join(missing_px[:8])}. "
                            "Essas serão ignoradas."
                        )
                        for t in missing_px:
                            weights.pop(t, None)

                    before_eq = portfolio.total_value(px)
                    trades = portfolio.rebalance_to_weights(
                        weights, px, buckets=buckets, note="sugestoes"
                    )
                    save_portfolio(portfolio)
                    after = portfolio.summary(px)
                    details = [
                        {
                            "lado": t.side,
                            "ticker": t.ticker,
                            "qtd": round(t.shares, 4),
                            "preço": round(t.price, 2),
                            "valor": round(t.amount, 2),
                        }
                        for t in trades
                    ]
                    if trades:
                        st.session_state["pf_flash"] = {
                            "kind": "success",
                            "msg": (
                                f"Tese aplicada: {len(trades)} ordens · "
                                f"{len(portfolio.positions)} ativos · "
                                f"patrimônio {format_brl(after['equity'])} "
                                f"(antes {format_brl(before_eq)})."
                            ),
                            "details": details,
                        }
                    else:
                        st.session_state["pf_flash"] = {
                            "kind": "warning",
                            "msg": (
                                "Nenhuma ordem necessária — a carteira já está alinhada "
                                "às sugestões (ou faltou preço/caixa). "
                                f"Patrimônio: {format_brl(after['equity'])} · "
                                f"posições: {len(portfolio.positions)}."
                            ),
                            "details": details,
                        }
                    st.cache_data.clear()
                    st.rerun()
                except Exception as e:
                    st.session_state["pf_flash"] = {
                        "kind": "error",
                        "msg": f"Não foi possível aplicar as sugestões: {e}",
                    }
                    st.rerun()

    st.markdown("##### 3. Alocação manual por ação")
    with st.container(border=True):
        st.caption("Compre ou venda uma ação específica com o dinheiro de treino.")
        tickers_opts = []
        if not scored_table.empty and "ticker" in scored_table.columns:
            tickers_opts = sorted(scored_table["ticker"].astype(str).unique().tolist())
        with st.form("alocacao_manual"):
            m1, m2, m3, m4 = st.columns(4)
            with m1:
                if tickers_opts:
                    ticker_m = st.selectbox("Código", options=tickers_opts, index=0)
                else:
                    ticker_m = st.text_input("Código", value="ITUB4")
                ticker_m = normalize_ticker(ticker_m)
            with m2:
                mode = st.selectbox(
                    "Modo",
                    ["valor", "qtd", "vender"],
                    format_func=lambda x: {
                        "valor": "Comprar por R$",
                        "qtd": "Comprar por qtd",
                        "vender": "Vender qtd",
                    }[x],
                )
            with m3:
                amount = st.number_input(
                    "Valor (R$) ou quantidade",
                    min_value=0.0,
                    value=1000.0,
                    step=100.0,
                )
            with m4:
                default_px = float(prices.get(ticker_m, 0) or 0)
                price_m = st.number_input(
                    "Preço (R$)",
                    min_value=0.0,
                    value=default_px,
                    step=0.01,
                    format="%.2f",
                )
            submitted = st.form_submit_button("Executar alocação", type="primary")
            if submitted:
                try:
                    if mode == "valor":
                        portfolio.buy_value(ticker_m, amount, price_m, note="manual-valor")
                    elif mode == "qtd":
                        portfolio.buy(ticker_m, amount, price_m, note="manual-qtd")
                    else:
                        portfolio.sell(ticker_m, amount, price_m, note="manual-venda")
                    save_portfolio(portfolio)
                    st.session_state["pf_flash"] = {
                        "kind": "success",
                        "msg": f"Alocação em {ticker_m} registrada.",
                    }
                    st.rerun()
                except Exception as e:
                    st.error(str(e))

with tab_income:
    c1, c2, c3 = st.columns(3)
    reinvest = c1.toggle("Reinvestir dividendos", value=True, key="pf_reinvest")
    years = c2.slider("Anos", 1, 30, 10, key="pf_years")
    growth = c3.slider("Cresc. div. a.a.", 0.0, 0.12, 0.04, 0.01, key="pf_growth")

    proj = project_income(
        portfolio,
        scored_table if not scored_table.empty else fundamentals,
        prices=prices,
        reinvest=reinvest,
        years=years,
        assumed_div_growth=growth,
    )
    annual = float(proj.get("annual_income_now") or 0.0)
    monthly = float(proj.get("monthly_income_now") or annual / 12.0)
    yoe = float(proj.get("yield_on_equity") or 0.0)

    render_wallet_balance(
        total=format_brl(monthly),
        delta=f"{format_brl(annual)} / ano · {format_pct(yoe)} yield",
        delta_positive=True,
        badge="Renda estimada",
        stats=[
            ("Mensal", format_brl(monthly)),
            ("Anual", format_brl(annual)),
            ("Yield", format_pct(yoe)),
            ("Horizonte", f"{years}a"),
        ],
    )

    projection = proj.get("projection")
    if projection is not None and not getattr(projection, "empty", True):
        with st.container(border=True):
            st.plotly_chart(
                income_area(projection),
                width="stretch",
                config={"displayModeBar": False},
            )

    by_ticker = proj.get("by_ticker")
    if by_ticker is not None and not getattr(by_ticker, "empty", True):
        bt = by_ticker.copy()
        if bt.columns.duplicated().any():
            bt = bt.loc[:, ~bt.columns.duplicated(keep="last")]
        if "annual_income" in bt.columns and len(bt):
            with st.container(border=True):
                st.plotly_chart(
                    holdings_donut(
                        bt,
                        value_col="annual_income",
                        label_col="ticker",
                        center_value=format_brl(annual),
                        title="Renda por ativo",
                    ),
                    width="stretch",
                    config={"displayModeBar": False},
                )

with tab_more:
    with st.expander("Tabela completa", icon=":material/table:"):
        if holdings.empty:
            st.caption("Sem posições.")
        else:
            view = holdings.copy()
            for c in ("weight", "pnl_pct"):
                if c in view.columns:
                    view[c] = view[c].map(format_pct)
            for c in ("avg_price", "price", "market_value", "cost", "pnl"):
                if c in view.columns:
                    view[c] = view[c].map(format_brl)
            st.dataframe(friendly_dataframe(view), width="stretch", hide_index=True)

    with st.expander("Histórico de ordens", icon=":material/history:"):
        if portfolio.trades:
            st.dataframe(
                friendly_dataframe(pd.DataFrame([t.__dict__ for t in portfolio.trades])),
                width="stretch",
                hide_index=True,
            )
        else:
            st.caption("Sem trades.")

    with st.expander("Reset / backup", icon=":material/settings:"):
        new_cash = st.number_input(
            "Capital inicial (reset total)",
            min_value=1000.0,
            value=100_000.0,
            step=1000.0,
            key="pf_reset_cash",
        )
        if st.button("Zerar carteira completamente", type="secondary"):
            portfolio = PaperPortfolio.create(name=portfolio_name, cash=new_cash)
            save_portfolio(portfolio)
            st.session_state["pf_flash"] = {
                "kind": "success",
                "msg": "Carteira zerada.",
            }
            st.rerun()
        st.download_button(
            "Exportar JSON",
            data=json.dumps(portfolio.to_dict(), indent=2, ensure_ascii=False),
            file_name=f"{portfolio_name}.json",
            mime="application/json",
        )

    st.caption("Estudo e treino · não é recomendação de investimento.")
