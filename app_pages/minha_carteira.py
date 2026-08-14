"""Minha carteira — jornada guiada: capital → montar → renda → acompanhar."""

from __future__ import annotations

import json

import pandas as pd
import streamlit as st

from src.config import THESIS_VERSION, get_settings
from src.data.providers import get_provider
from src.data.quality import coverage_summary, enrich_fundamentals_quality
from src.data.universe import normalize_ticker
from src.portfolio.dividends_live import dividends_frame, sync_paper_dividends
from src.portfolio.export import (
    holdings_export_df,
    portfolio_to_csv_bundle,
    single_csv_bytes,
    trades_export_df,
)
from src.portfolio.income import (
    project_income,
    project_income_scenarios,
    suggest_monthly_contribution,
)
from src.portfolio.paper import PaperPortfolio, load_portfolio, save_portfolio
from src.services import format_brl, format_pct, prices_dict_from_fundamentals
from src.thesis.alerts import evaluate_portfolio, exit_rules_summary
from src.thesis.scoring import recommend_weights, score_universe
from src.ui.charts import (
    equity_growth_area,
    holdings_donut,
    income_area,
    income_scenarios_chart,
    sector_bars,
    sector_breakdown_from_holdings,
)
from src.ui.components import (
    render_explain_card,
    render_journey,
    render_page_header,
    render_plain_help,
)
from src.ui.data_source import provider_selectbox, render_data_quality_banner
from src.ui.friendly import JOURNEY_STEPS, friendly_dataframe, render_glossary_expander
from src.ui.shell import page_setup
from src.ui.trust import render_friendly_safety_note, render_premises_box, render_trust_strip
from src.ui.wallet import render_asset_rows, render_wallet_balance

page_setup()
render_page_header(
    "Minha carteira",
    "Conta de treino · monte passo a passo, sem jargão",
)

with st.sidebar:
    st.markdown("##### Conta de treino")
    portfolio_name = st.text_input("Nome da carteira", value="paper-main", key="pf_name")
    provider = provider_selectbox(key="pf_provider", label="Fonte de dados", show_help=True)
    if st.button("Atualizar dados", icon=":material/refresh:", width="stretch", key="pf_refresh"):
        st.cache_data.clear()
        st.rerun()
    render_glossary_expander()

render_data_quality_banner(provider)


@st.cache_data(ttl=3600, show_spinner=False)
def _raw_fundamentals(provider: str):
    from src.data.universe import get_universe

    mode = "core" if provider == "yfinance" else "full"
    return get_provider(provider).get_fundamentals(get_universe(mode=mode))  # type: ignore[arg-type]


@st.cache_data(ttl=3600, show_spinner=False)
def _scored_table(provider: str):
    raw = _raw_fundamentals(provider)
    return score_universe(raw).scored


portfolio = load_portfolio(portfolio_name)
fundamentals = pd.DataFrame()
scored_table = fundamentals
prices: dict = {}
coverage: dict = {}
try:
    with st.spinner(
        "Carregando cotações… (1ª vez na Bolsa real: ~15–30s; depois cache)"
        if provider == "yfinance"
        else "Carregando dados de treino…"
    ):
        fundamentals = _raw_fundamentals(provider)
        scored_table = _scored_table(provider)
        if not scored_table.empty:
            scored_table = enrich_fundamentals_quality(scored_table)
        prices = prices_dict_from_fundamentals(
            scored_table if not scored_table.empty else fundamentals
        )
        coverage = coverage_summary(
            scored_table if not scored_table.empty else fundamentals
        )
except Exception as e:
    st.error(f"Não deu para carregar o mercado: {e}")
    st.info(
        "Sua carteira de treino ainda aparece abaixo. "
        "Para dados na hora, escolha **Modo treino** na barra lateral."
    )

render_trust_strip(provider=provider, coverage=coverage)

summary = portfolio.summary(prices)
holdings = portfolio.holdings_frame(prices)
has_positions = not holdings.empty
has_capital = float(summary.get("equity") or 0) >= 100
viewed_income = bool(st.session_state.get("pf_viewed_income"))

# 0 capital · 1 escolher · 2 montar · 3 renda
if not has_capital:
    journey_current, journey_done = 0, -1
elif not has_positions:
    journey_current, journey_done = 2, 0
elif not viewed_income:
    journey_current, journey_done = 3, 2
else:
    journey_current, journey_done = 3, 3

render_journey(JOURNEY_STEPS, current=journey_current, completed_through=journey_done)

# Feedback da última ação
if st.session_state.get("pf_flash"):
    flash = st.session_state.pop("pf_flash")
    kind = flash.get("kind", "success")
    msg = flash.get("msg", "")
    if kind == "success":
        st.success(msg, icon=":material/check_circle:")
        if flash.get("details"):
            with st.expander("Ver o que mudou nas ordens", expanded=False):
                st.dataframe(pd.DataFrame(flash["details"]), width="stretch", hide_index=True)
    elif kind == "warning":
        st.warning(msg)
    else:
        st.error(msg)

pnl_abs = float(summary.get("pnl") or 0)
pnl_pct = float(summary.get("pnl_pct") or 0)
invested = float(summary.get("invested") or 0)
cash = float(summary.get("cash") or 0)

render_wallet_balance(
    total=format_brl(summary["equity"]),
    delta=f"Lucro/prejuízo simulado: {format_brl(pnl_abs)} ({format_pct(pnl_pct)})",
    delta_positive=pnl_abs >= 0,
    badge="Conta de treino · BRL",
    label="Dinheiro total na conta de treino",
    hint=(
        "Isso é caixa livre + valor das ações (preço de hoje). "
        "Não é a renda de dividendos — essa fica na aba “Renda esperada”."
    ),
    stats=[
        (
            "Livre no caixa",
            format_brl(cash),
            "Disponível para comprar ações",
        ),
        (
            "Aplicado em ações",
            format_brl(invested),
            "Valor de mercado das posições",
        ),
        (
            "Dividendos (simulado)",
            format_brl(summary["dividends_received"]),
            "Já “recebidos” nesta conta de treino",
        ),
        (
            "Empresas na carteira",
            str(summary["n_positions"]),
            "Quantas empresas você tem agora",
        ),
    ],
)

# Alertas resumidos no topo
_alerts_df = pd.DataFrame()
if portfolio.positions:
    _alerts_df = evaluate_portfolio(
        list(portfolio.positions.keys()),
        scored_table if not scored_table.empty else fundamentals,
    )
    _crit = (
        _alerts_df[_alerts_df["severidade"] == "critical"]
        if not _alerts_df.empty
        else pd.DataFrame()
    )
    _warn = (
        _alerts_df[_alerts_df["severidade"] == "warning"]
        if not _alerts_df.empty
        else pd.DataFrame()
    )
    if not _crit.empty:
        st.error(
            f"{len(_crit)} ponto(s) de atenção forte — veja a aba Visão geral.",
            icon=":material/error:",
        )
    elif not _warn.empty:
        st.warning(
            f"{len(_warn)} ponto(s) de atenção — veja a aba Visão geral.",
            icon=":material/warning:",
        )

# Abas persistentes: st.tabs volta sempre para a 1ª no rerun (ex.: ao digitar renda).
# segmented_control + session_state mantém o usuário na seção em que estava.
_SECTION_LABELS = {
    "overview": "Visão geral",
    "build": "Montar carteira",
    "income": "Renda esperada",
    "more": "Detalhes",
}
if "pf_section" not in st.session_state:
    st.session_state["pf_section"] = "overview"

section = st.segmented_control(
    "Seção da carteira",
    options=list(_SECTION_LABELS.keys()),
    format_func=lambda k: _SECTION_LABELS[k],
    key="pf_section",
    help="Ao editar valores, você permanece nesta seção (não volta sozinho para Visão geral).",
)
if section is None:
    section = st.session_state.get("pf_section") or "overview"

# ─── Visão geral ────────────────────────────────────────────────────────────
if section == "overview":
    if not has_positions:
        render_plain_help(
            "Sua carteira ainda está vazia — vamos montar juntos",
            """
1. Abra a aba **Montar carteira**
2. Confirme o **capital de treino** (dinheiro de mentira)
3. Clique em **Montar carteira com a tese** (o app escolhe e “compra” por você)
4. Depois vá em **Renda esperada** para ver quanto poderia render em dividendos

Quer escolher na mão? Use **Descubra ações** e volte aqui em alocação manual.
""",
        )
        if st.button(
            "Ir para Montar carteira",
            type="primary",
            icon=":material/arrow_forward:",
            key="pf_go_build",
        ):
            st.session_state["pf_section"] = "build"
            st.rerun()
    else:
        st.markdown("##### Como seu dinheiro está dividido")
        st.caption(
            "O gráfico da esquerda mostra só o que está **aplicado em ações** "
            "(não inclui o caixa livre). Por isso o total pode ser menor que o banner de cima."
        )
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
                        title="O que está em ações (sem o caixa)",
                    ),
                    width="stretch",
                    config={"displayModeBar": False},
                )
        with c2:
            with st.container(border=True):
                if sectors.empty:
                    st.caption("Sem dados de setor para montar o gráfico.")
                else:
                    st.plotly_chart(
                        sector_bars(sectors, title="Divisão por setor da economia"),
                        width="stretch",
                        config={"displayModeBar": False},
                    )

        st.markdown("##### Suas empresas")
        st.caption(
            "Valor atual = preço de hoje × quantidade. "
            "Lucro/prejuízo compara com o preço médio que você “pagou” no treino."
        )
        name_map: dict[str, str] = {}
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
                "Base (mais estável)"
                if bucket == "core"
                else ("Complemento" if bucket == "satellite" else bucket)
            )
            pnl = float(r.get("pnl") or 0)
            pnl_p = float(r.get("pnl_pct") or 0)
            shares = float(r["shares"])
            shares_s = (
                f"{shares:,.2f} ações".replace(",", "X").replace(".", ",").replace("X", ".")
            )
            asset_rows.append(
                (
                    t,
                    f"{name} · {bucket_pt}" if bucket_pt else name,
                    shares_s,
                    f"Preço hoje {format_brl(float(r['price']))}",
                    format_brl(float(r["market_value"])),
                    f"{format_brl(pnl)} ({format_pct(pnl_p)})",
                    pnl >= 0,
                )
            )
        render_asset_rows(asset_rows)

        st.markdown("##### Dividendos na conta de treino")
        st.caption(
            "Busca pagamentos reais na fonte. Se a compra for recente e ainda não houve data-ex, "
            "credita uma **estimativa do mês** (baseada no % de dividendo) para você ver a renda "
            "na conta de treino — isso aparece como “Carteira (estimado)”."
        )
        d1, d2 = st.columns([1, 1.4])
        with d1:
            if st.button(
                "Receber dividendos da bolsa",
                type="primary",
                icon=":material/payments:",
                width="stretch",
                key="pf_sync_div_overview",
            ):
                with st.spinner("Buscando dividendos das suas ações…"):
                    result = sync_paper_dividends(portfolio, provider, fundamentals=scored_table if not scored_table.empty else fundamentals, prices=prices)
                    save_portfolio(portfolio)
                    n = int(result.get("credited") or 0)
                    total = float(result.get("total_brl") or 0)
                    if n > 0:
                        st.session_state["pf_flash"] = {
                            "kind": "success",
                            "msg": (
                                f"Dividendos creditados: {n} pagamento(s) · "
                                f"{format_brl(total)} no caixa."
                            ),
                        }
                    else:
                        st.session_state["pf_flash"] = {
                            "kind": "warning",
                            "msg": result.get("message")
                            or "Nenhum dividendo novo para creditar no período.",
                        }
                    st.rerun()
        with d2:
            div_total = float(summary.get("dividends_received") or 0)
            st.metric("Já creditado em caixa", format_brl(div_total))
            st.caption(
                f"{len(portfolio.dividends)} registro(s) · "
                "detalhes e exportação em **Detalhes**."
            )
        div_df = dividends_frame(portfolio)
        if not div_df.empty:
            show_div = div_df.head(8).copy()
            if "valor_por_acao" in show_div.columns:
                show_div["valor_por_acao"] = show_div["valor_por_acao"].map(
                    lambda x: format_brl(x) if x == x else "—"
                )
            if "total_recebido" in show_div.columns:
                show_div["total_recebido"] = show_div["total_recebido"].map(format_brl)
            st.dataframe(
                friendly_dataframe(
                    show_div,
                    extra_map={
                        "data": "Data",
                        "ticker": "Código",
                        "qtd_acoes": "Qtd. de ações",
                        "valor_por_acao": "R$ por ação",
                        "total_recebido": "Total recebido",
                        "obs": "Obs.",
                    },
                ),
                width="stretch",
                hide_index=True,
            )


        st.markdown("##### Pontos de atenção da tese")
        if _alerts_df.empty:
            st.caption("Ainda não há alertas calculados para estas posições.")
        else:
            show_alerts = _alerts_df[_alerts_df["severidade"] != "info"]
            if show_alerts.empty:
                st.success(
                    "Nenhum alerta grave nos ativos atuais — continue acompanhando.",
                    icon=":material/check_circle:",
                )
            else:
                st.dataframe(
                    friendly_dataframe(show_alerts),
                    width="stretch",
                    hide_index=True,
                )
            with st.expander("Ver todos os avisos (incluindo ok)", icon=":material/list:"):
                st.dataframe(friendly_dataframe(_alerts_df), width="stretch", hide_index=True)
            with st.expander("Como o app pensa em “sair” de um papel", icon=":material/rule:"):
                st.markdown(exit_rules_summary())
                st.caption(
                    "O app **não vende sozinho**. Você decide na aba Montar carteira."
                )

# ─── Montar carteira ────────────────────────────────────────────────────────
if section == "build":
    render_plain_help(
        "Como montar uma carteira saudável neste app",
        """
**Ideia da tese:** várias empresas de qualidade que pagam dividendos de forma sustentável —
não colocar tudo em uma só ação nem caçar o maior dividendo a qualquer preço.

**Caminho recomendado para iniciantes**
1. Ajuste o capital de treino
2. Deixe o app **montar com a tese** (base + complemento)
3. Veja a **renda esperada** e os **riscos**
4. Só depois mexa manualmente, se quiser
""",
    )

    st.markdown("##### Passo 1 · Capital de treino")
    with st.container(border=True):
        st.caption(
            "É dinheiro **de mentira** para praticar. Não está ligado à sua corretora."
        )
        cc1, cc2, cc3 = st.columns([1.2, 1, 1])
        with cc1:
            _eq = float(summary.get("equity") or portfolio.initial_cash or 100_000.0)
            _eq = round(_eq + 1e-9, 2)
            _min_cap = 100.0
            _default_cap = max(_min_cap, _eq)
            if "pf_capital_input" in st.session_state:
                try:
                    prev = float(st.session_state["pf_capital_input"])
                    if prev < _min_cap or prev != prev:
                        st.session_state["pf_capital_input"] = _default_cap
                except (TypeError, ValueError):
                    st.session_state["pf_capital_input"] = _default_cap
            new_capital = st.number_input(
                "Quanto você quer ter na conta de treino (R$)",
                min_value=_min_cap,
                value=_default_cap,
                step=1000.0,
                key="pf_capital_input",
                help="Soma de caixa + ações. Ao salvar, o app ajusta a conta de treino.",
            )
        with cc2:
            reset_pos = st.checkbox(
                "Começar do zero (zerar ações)",
                value=False,
                help="Se marcado, vende tudo (simulado) e deixa 100% em caixa com o novo valor.",
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
                        "msg": f"Capital de treino atualizado para {format_brl(new_capital)}.",
                    }
                    st.rerun()
                except Exception as e:
                    st.error(str(e))

    st.markdown("##### Passo 2 · Montar com a tese (recomendado)")
    with st.container(border=True):
        settings = get_settings()
        top_n = st.slider(
            "Quantas empresas na carteira?",
            5,
            20,
            12,
            key="pf_top_n",
            help="Carteiras com 8–15 nomes costumam ser um bom começo para diversificar.",
        )
        st.markdown(
            f"""
- Cerca de **{settings.core_weight:.0%}** em empresas mais estáveis (**base**)
- Cerca de **{settings.satellite_weight:.0%}** em um **complemento** um pouco mais flexível
- Limite por ação ~**{settings.max_position_pct:.0%}** · por setor ~**{settings.max_sector_pct:.0%}**
- Tese **v{THESIS_VERSION}** — favorece qualidade e dividendos sustentáveis (penaliza “dividendo alto demais”)
"""
        )
        if provider == "demo":
            st.warning(
                "Você está no **modo treino**. A carteira montada usa números ilustrativos. "
                "Para sugestões com cara de mercado, mude para **Bolsa real**.",
                icon=":material/school:",
            )
        if coverage.get("trust_level") == "fraca" and provider == "yfinance":
            st.warning(
                "Cobertura de dados fraca agora. A montagem automática ainda funciona, "
                "mas confira as empresas depois em **Descubra ações**.",
                icon=":material/info:",
            )
        if st.button(
            "Montar carteira com a tese",
            type="primary",
            width="stretch",
            key="pf_apply",
            icon=":material/auto_awesome:",
        ):
            with st.spinner("Escolhendo empresas e executando ordens de treino…"):
                try:
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
                        max_sector_pct=settings.max_sector_pct,
                    )
                    if recs.empty:
                        st.session_state["pf_flash"] = {
                            "kind": "warning",
                            "msg": (
                                "Nenhuma ação passou nos filtros. "
                                "Tente Modo treino ou baixe a nota em Descubra ações."
                            ),
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
                            "Essas serão ignoradas neste momento."
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
                                f"Carteira montada: {len(trades)} ordens · "
                                f"{len(portfolio.positions)} empresas · "
                                f"total {format_brl(after['equity'])}. "
                                "Agora abra a aba Renda esperada."
                            ),
                            "details": details,
                        }
                    else:
                        st.session_state["pf_flash"] = {
                            "kind": "warning",
                            "msg": (
                                "Nenhuma ordem nova — a carteira já estava alinhada "
                                f"ou faltou preço/caixa. Total: {format_brl(after['equity'])}."
                            ),
                            "details": details,
                        }
                    st.cache_data.clear()
                    st.rerun()
                except Exception as e:
                    st.session_state["pf_flash"] = {
                        "kind": "error",
                        "msg": f"Não foi possível montar a carteira: {e}",
                    }
                    st.rerun()

    st.markdown("##### Passo 3 · Compra ou venda manual (opcional)")
    with st.container(border=True):
        st.caption(
            "Use quando quiser ajustar uma empresa específica. "
            "Para o primeiro uso, o botão da tese acima costuma bastar."
        )
        tickers_opts = []
        if not scored_table.empty and "ticker" in scored_table.columns:
            tickers_opts = sorted(scored_table["ticker"].astype(str).unique().tolist())
        with st.form("alocacao_manual"):
            m1, m2, m3, m4 = st.columns(4)
            with m1:
                if tickers_opts:
                    ticker_m = st.selectbox("Código da ação", options=tickers_opts, index=0)
                else:
                    ticker_m = st.text_input("Código da ação", value="ITUB4")
                ticker_m = normalize_ticker(ticker_m)
            with m2:
                mode = st.selectbox(
                    "O que fazer",
                    ["valor", "qtd", "vender"],
                    format_func=lambda x: {
                        "valor": "Comprar gastando R$",
                        "qtd": "Comprar N ações",
                        "vender": "Vender N ações",
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
                    "Preço usado na simulação (R$)",
                    min_value=0.0,
                    value=default_px,
                    step=0.01,
                    format="%.2f",
                )
            submitted = st.form_submit_button("Executar na conta de treino", type="primary")
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
                        "msg": f"Operação em {ticker_m} registrada na conta de treino.",
                    }
                    st.rerun()
                except Exception as e:
                    st.error(str(e))

# ─── Renda esperada ─────────────────────────────────────────────────────────
if section == "income":
    st.session_state["pf_viewed_income"] = True
    settings_income = get_settings()
    fallback_dy = (settings_income.preferred_dy_min + settings_income.preferred_dy_max) / 2.0

    render_plain_help(
        "O que esta simulação faz (e o que não faz)",
        """
Usa o **dinheiro que já está na conta de treino** (caixa + ações) e soma os **aportes mensais**
que você definir abaixo.

- A **renda do seu trabalho** serve só para *sugerir* quanto aportar — **não** é somada à carteira
- **Dividendos** = “aluguel” estimado das ações (não é o seu salário)
- Preço das ações fica de lado; a taxa de dividendo tem **teto** (não sobe para sempre)
- **Não é previsão** — é um cenário de estudo
""",
    )

    if not has_positions:
        st.warning(
            "Sua carteira ainda não tem ações. O cenário usa a taxa de dividendo típica da tese "
            f"(~{fallback_dy:.0%}) e o capital/caixa atual. "
            "Vá em **Montar carteira** para usar os % reais das suas empresas.",
            icon=":material/info:",
        )

    st.markdown("##### 1 · Sua renda de trabalho e quanto aportar por mês")
    with st.container(border=True):
        st.caption(
            "A renda líquida só ajuda a **sugerir** o aporte (5% / 10% / 15%). "
            "O que entra na simulação da carteira é **somente o valor do aporte**."
        )
        if "pf_user_income" not in st.session_state:
            st.session_state["pf_user_income"] = 8_000.0

        ic1, ic2 = st.columns([1, 1.2])
        with ic1:
            user_income = st.number_input(
                "Sua renda líquida mensal aproximada (R$)",
                min_value=0.0,
                step=500.0,
                key="pf_user_income",
                help="Valor que entra na sua conta por mês, depois dos descontos. Só para sugerir aportes.",
            )
        suggestions = suggest_monthly_contribution(float(user_income))
        with ic2:
            st.markdown("**Sugestões de aporte mensal** (com base na sua renda)")
            s1, s2, s3 = st.columns(3)
            if s1.button(
                f"Leve · {format_brl(suggestions['leve'])}",
                width="stretch",
                key="pf_sug_leve",
                help="Cerca de 5% da renda — ritmo suave.",
            ):
                st.session_state["pf_monthly_contrib"] = float(suggestions["leve"])
                st.rerun()
            if s2.button(
                f"Recomendado · {format_brl(suggestions['recomendado'])}",
                type="primary",
                width="stretch",
                key="pf_sug_rec",
                help="Cerca de 10% da renda — meta clássica de investimento.",
            ):
                st.session_state["pf_monthly_contrib"] = float(suggestions["recomendado"])
                st.rerun()
            if s3.button(
                f"Forte · {format_brl(suggestions['forte'])}",
                width="stretch",
                key="pf_sug_forte",
                help="Cerca de 15% da renda — só se couber no orçamento.",
            ):
                st.session_state["pf_monthly_contrib"] = float(suggestions["forte"])
                st.rerun()
            st.caption(suggestions["blurb"])

        if "pf_monthly_contrib" not in st.session_state:
            st.session_state["pf_monthly_contrib"] = float(
                suggestions["recomendado"] if user_income > 0 else 500.0
            )
        # Mantém o slider dentro do max se a renda mudar
        slider_max = max(
            5_000.0,
            float(user_income) * 0.4 if user_income else 0.0,
            float(st.session_state["pf_monthly_contrib"]) * 1.5,
            1_000.0,
        )
        if float(st.session_state["pf_monthly_contrib"]) > slider_max:
            st.session_state["pf_monthly_contrib"] = float(slider_max)

        monthly_contrib = st.slider(
            "Quanto você pretende aportar por mês na carteira? (R$)",
            min_value=0.0,
            max_value=float(slider_max),
            step=50.0,
            key="pf_monthly_contrib",
            help="Todo mês o modelo assume que este valor entra na carteira da tese.",
        )
        if user_income and user_income > 0:
            pct_of_income = monthly_contrib / user_income
            st.caption(
                f"Seu aporte de **{format_brl(monthly_contrib)}/mês** representa "
                f"**{pct_of_income:.0%}** da renda informada "
                f"(**{format_brl(monthly_contrib * 12)}** por ano em aportes novos)."
            )
        else:
            st.caption(
                f"Aportes de **{format_brl(monthly_contrib)}/mês** "
                f"(**{format_brl(monthly_contrib * 12)}**/ano). "
                "Preencha a renda acima para ver o % do orçamento."
            )

    st.markdown("##### 2 · Capital e horizonte da simulação")
    portfolio_eq = float(summary.get("equity") or portfolio.cash or 10_000.0)
    if "pf_sim_capital" not in st.session_state:
        st.session_state["pf_sim_capital"] = float(portfolio_eq)
    sc1, sc2, sc3 = st.columns(3)
    with sc1:
        sim_capital = st.number_input(
            "Capital inicial desta simulação (R$)",
            min_value=100.0,
            step=500.0,
            key="pf_sim_capital",
            help=(
                "Pode ser diferente da conta de treino. "
                "Ex.: simule R$ 3 mil mesmo se a conta paper tiver outro valor."
            ),
        )
    with sc2:
        reinvest = st.toggle(
            "Reinvestir os dividendos",
            value=True,
            key="pf_reinvest",
            help="Se ligado, a renda de dividendos compra mais ações no modelo (bola de neve).",
        )
    with sc3:
        years = st.slider(
            "Olhar quantos anos à frente?",
            1,
            30,
            10,
            key="pf_years",
            help="Horizonte do gráfico de renda esperada.",
        )
    if abs(float(sim_capital) - portfolio_eq) > 1:
        st.caption(
            f"Conta de treino hoje: **{format_brl(portfolio_eq)}**. "
            f"Simulação usando **{format_brl(sim_capital)}** (você escolheu outro capital)."
        )
    else:
        st.caption(f"Usando o capital da conta de treino: **{format_brl(sim_capital)}**.")

    scenarios = project_income_scenarios(
        portfolio,
        scored_table if not scored_table.empty else fundamentals,
        prices=prices,
        years=years,
        monthly_contribution=float(monthly_contrib),
        reinvest=reinvest,
        starting_principal=float(sim_capital),
        fallback_yield=fallback_dy,
        max_yield=float(settings_income.projection_max_yield),
    )
    proj = scenarios["base"]
    annual = float(proj.get("annual_income_now") or 0.0)
    monthly = float(proj.get("monthly_income_now") or annual / 12.0)
    start_yield = float(proj.get("starting_yield") or 0.0)
    start_principal = float(proj.get("starting_principal") or sim_capital)
    final_monthly = float(proj.get("final_monthly_income") or 0.0)
    final_annual = float(proj.get("final_annual_income") or 0.0)
    boost = float(proj.get("income_boost_from_contrib") or 0.0)
    total_aportes = float(proj.get("total_contributed_end") or 0.0)
    final_eq = float(proj.get("final_equity_est") or sim_capital)
    final_yld = float(proj.get("final_yield") or start_yield)
    implied = float(proj.get("implied_yield_end") or 0.0)
    caut = scenarios["cauteloso"]
    anim = scenarios["animado"]

    st.info(
        f"**Renda esperada (cenário base):** capital **{format_brl(start_principal)}** · "
        f"taxa ~**{start_yield:.1%}** (teto {settings_income.projection_max_yield:.0%}) · "
        f"aportes **{format_brl(monthly_contrib)}/mês** · "
        f"{'com' if reinvest else 'sem'} reinvestir · **{years}** anos. "
        f"Sua renda de trabalho ({format_brl(user_income)}/mês) **não** entra na carteira.",
        icon=":material/calculate:",
    )
    if proj.get("yield_was_capped"):
        st.warning(
            f"A taxa bruta (~{float(proj.get('raw_starting_yield') or 0):.1%}) "
            f"foi limitada a {settings_income.projection_max_yield:.0%} para evitar cenários irreais.",
            icon=":material/speed:",
        )

    render_wallet_balance(
        total=format_brl(final_monthly),
        delta=(
            f"Hoje ~{format_brl(monthly)}/mês · "
            f"cauteloso {format_brl(float(caut.get('final_monthly_income') or 0))}/mês · "
            f"animado {format_brl(float(anim.get('final_monthly_income') or 0))}/mês"
        ),
        delta_positive=True,
        show_delta_arrow=False,
        badge="Renda esperada · 3 cenários",
        label=f"Dividendos no ano {years} (cenário base, por mês)",
        hint=(
            "Faixa cauteloso → animado mostra incerteza de forma simples. "
            "O valor grande é o cenário base da tese — ainda é estimativa."
        ),
        stats=[
            ("Hoje / mês", format_brl(monthly), "Com o capital da simulação"),
            (
                "Cauteloso / mês",
                format_brl(float(caut.get("final_monthly_income") or 0)),
                "Mais conservador",
            ),
            ("Base / mês", format_brl(final_monthly), "Mais usado no guia"),
            (
                "Animado / mês",
                format_brl(float(anim.get("final_monthly_income") or 0)),
                "Otimista com teto",
            ),
        ],
    )

    with st.container(border=True):
        st.markdown("##### Conta rápida (cenário base)")
        st.markdown(
            f"""
1. Capital inicial da simulação: **{format_brl(start_principal)}**  
2. Aportes em {years} anos: **{format_brl(total_aportes)}**  
3. Capital no fim (base): **{format_brl(final_eq)}**  
4. Dividendos no fim ≈ capital × taxa →  
   **{format_brl(final_eq)} × {final_yld:.1%} ≈ {format_brl(final_annual)}/ano**  
   (**{format_brl(final_monthly)}/mês**) · taxa implícita **{implied:.1%}**
"""
        )

    render_premises_box(
        [
            f"Tese Quality Dividend v{THESIS_VERSION}",
            f"Capital inicial simulado: {format_brl(start_principal)}",
            f"Aporte mensal: {format_brl(monthly_contrib)}",
            f"Reinvestir dividendos: {'sim' if reinvest else 'não'}",
            f"Taxa inicial de dividendo (base): ~{start_yield:.1%} (teto {settings_income.projection_max_yield:.0%})",
            "Preço das ações fica de lado (foco em renda, não em valorização)",
            "Três cenários: cauteloso / base / animado — nenhum é garantia",
            "Fonte de dados: " + ("modo treino" if provider == "demo" else "bolsa (Yahoo + cadastro B3)"),
        ],
        title="Premissas da renda esperada",
    )

    e1, e2, e3 = st.columns(3)
    with e1:
        render_explain_card(
            "Por que aportar todo mês ajuda",
            format_brl(boost / 12.0) + "/mês a mais",
            "No cenário base, diferença aproximada vs. não aportar mais no último ano. Mais capital → mais base para dividendos.",
        )
    with e2:
        render_explain_card(
            "Como a tese busca segurança",
            "Base + qualidade",
            "Prioriza empresas estáveis e dividendos sustentáveis; penaliza yield alto com sinais fracos. Diversifica por ação e setor.",
        )
    with e3:
        render_explain_card(
            "O que ainda é risco",
            "Bolsa oscila",
            "Empresas podem cortar dividendos; preços caem; aportes dependem da sua vida. Use a faixa dos 3 cenários, não um número só.",
        )

    combined = scenarios.get("combined")
    projection = proj.get("projection")
    if combined is not None and not getattr(combined, "empty", True):
        with st.container(border=True):
            st.markdown("##### Gráfico 1 · Renda esperada em 3 cenários")
            st.caption(
                "**O que mede:** dividendos estimados **por mês** (o “aluguel” das ações). "
                "Três linhas = cauteloso, base e animado. "
                "Mude aporte ou capital acima — o gráfico atualiza na hora."
            )
            st.plotly_chart(
                income_scenarios_chart(combined),
                width="stretch",
                config={"displayModeBar": False},
            )
            st.success(
                f"No **ano {years}** (base): cerca de **{format_brl(final_monthly)}/mês** "
                f"(faixa **{format_brl(float(caut.get('final_monthly_income') or 0))}** – "
                f"**{format_brl(float(anim.get('final_monthly_income') or 0))}**/mês).",
                icon=":material/payments:",
            )

        if projection is not None and not getattr(projection, "empty", True):
            with st.container(border=True):
                st.markdown("##### Gráfico 2 · Capital acumulado (cenário base)")
                st.caption(
                    "**O que mede:** o **tamanho da carteira** (dinheiro investido), não a renda mensal. "
                    "Barras = com seus aportes. Linha amarela = sem aportar mais. "
                    "É o “bolo” que gera os dividendos do gráfico 1."
                )
                st.plotly_chart(
                    equity_growth_area(
                        projection,
                        title="Capital acumulado na carteira (R$ investidos)",
                    ),
                    width="stretch",
                    config={"displayModeBar": False},
                )
                st.caption(
                    "Leitura: capital no fim × taxa de dividendo ≈ renda anual do cenário base."
                )

            with st.container(border=True):
                st.markdown("##### Comparativo: com aportes vs só o capital inicial")
                st.caption(
                    "Mesmo cenário base: linha roxa com aportes mensais · pontilhada sem aportar mais."
                )
                st.plotly_chart(
                    income_area(
                        projection,
                        title="Impacto dos aportes na renda mensal (cenário base)",
                        show_no_contrib=True,
                        monthly=True,
                    ),
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
                st.markdown("##### De onde viria a renda **hoje** (sem aportes futuros)")
                st.caption("Fatia estimada de dividendos por empresa com a carteira atual.")
                st.plotly_chart(
                    holdings_donut(
                        bt,
                        value_col="annual_income",
                        label_col="ticker",
                        center_value=format_brl(annual),
                        title="Renda estimada por empresa (hoje)",
                    ),
                    width="stretch",
                    config={"displayModeBar": False},
                )
                show_bt = bt.copy()
                for col in ("dividend_yield",):
                    if col in show_bt.columns:
                        show_bt[col] = show_bt[col].map(
                            lambda x: format_pct(x, 1) if x == x and x is not None else "—"
                        )
                for col in ("annual_income", "monthly_income", "market_value", "price"):
                    if col in show_bt.columns:
                        show_bt[col] = show_bt[col].map(format_brl)
                keep = [
                    c
                    for c in [
                        "ticker",
                        "shares",
                        "market_value",
                        "dividend_yield",
                        "annual_income",
                        "monthly_income",
                    ]
                    if c in show_bt.columns
                ]
                st.dataframe(
                    friendly_dataframe(show_bt[keep]),
                    width="stretch",
                    hide_index=True,
                )


# ─── Detalhes ───────────────────────────────────────────────────────────────
if section == "more":
    st.markdown("##### Exportar carteira")
    with st.container(border=True):
        st.caption(
            "Baixe planilhas para estudar fora do app (Excel/Google Sheets). "
            "É a conta de **treino**, não extrato de corretora."
        )
        zip_bytes = portfolio_to_csv_bundle(portfolio, prices)
        e1, e2, e3, e4 = st.columns(4)
        with e1:
            st.download_button(
                "Pacote completo (ZIP)",
                data=zip_bytes,
                file_name=f"{portfolio_name}-export.zip",
                mime="application/zip",
                type="primary",
                width="stretch",
                key="pf_dl_zip",
            )
        with e2:
            st.download_button(
                "Posições (CSV)",
                data=single_csv_bytes(holdings_export_df(portfolio, prices)),
                file_name=f"{portfolio_name}-posicoes.csv",
                mime="text/csv",
                width="stretch",
                key="pf_dl_hold",
            )
        with e3:
            st.download_button(
                "Ordens (CSV)",
                data=single_csv_bytes(trades_export_df(portfolio)),
                file_name=f"{portfolio_name}-ordens.csv",
                mime="text/csv",
                width="stretch",
                key="pf_dl_trades",
            )
        with e4:
            st.download_button(
                "Dividendos (CSV)",
                data=single_csv_bytes(dividends_frame(portfolio)),
                file_name=f"{portfolio_name}-dividendos.csv",
                mime="text/csv",
                width="stretch",
                key="pf_dl_divs",
            )
        st.download_button(
            "Backup técnico (JSON)",
            data=json.dumps(portfolio.to_dict(), indent=2, ensure_ascii=False),
            file_name=f"{portfolio_name}.json",
            mime="application/json",
            key="pf_dl_json",
        )

    st.markdown("##### Dividendos creditados")
    with st.container(border=True):
        st.caption(
            "O app consulta a fonte de dados (Bolsa real ou modo treino) e coloca no caixa "
            "os pagamentos em que você já tinha as ações. Não repete o mesmo dia+ticker."
        )
        if st.button(
            "Receber dividendos da bolsa",
            type="primary",
            icon=":material/payments:",
            key="pf_sync_div_more",
        ):
            with st.spinner("Buscando e creditando dividendos…"):
                result = sync_paper_dividends(portfolio, provider, fundamentals=scored_table if not scored_table.empty else fundamentals, prices=prices)
                save_portfolio(portfolio)
                n = int(result.get("credited") or 0)
                total = float(result.get("total_brl") or 0)
                msg = (
                    f"{n} pagamento(s) · {format_brl(total)} creditados."
                    if n
                    else (result.get("message") or "Nada novo para creditar.")
                )
                st.session_state["pf_flash"] = {
                    "kind": "success" if n else "warning",
                    "msg": msg,
                }
                if result.get("errors"):
                    st.session_state["pf_flash"]["msg"] += (
                        " Avisos: " + "; ".join(result["errors"][:3])
                    )
                st.rerun()
        div_df = dividends_frame(portfolio)
        if div_df.empty:
            st.caption(
                "Ainda sem dividendos creditados. Monte a carteira e clique em "
                "**Receber dividendos da bolsa**."
            )
        else:
            show_div = div_df.copy()
            for c in ("valor_por_acao", "total_recebido"):
                if c in show_div.columns:
                    show_div[c] = show_div[c].map(
                        lambda x: format_brl(x) if x == x and x is not None else "—"
                    )
            st.dataframe(
                friendly_dataframe(
                    show_div,
                    extra_map={
                        "data": "Data",
                        "ticker": "Código",
                        "qtd_acoes": "Qtd. de ações",
                        "valor_por_acao": "R$ por ação",
                        "total_recebido": "Total recebido",
                        "obs": "Obs.",
                    },
                ),
                width="stretch",
                hide_index=True,
                height=320,
            )
            st.metric(
                "Total de dividendos na conta de treino",
                format_brl(float(summary.get("dividends_received") or 0)),
            )

    with st.expander("Regras de atenção da tese", icon=":material/rule:", expanded=False):
        st.markdown(exit_rules_summary())
        st.caption("Regras **não** executam vendas automáticas.")

    with st.expander("Tabela completa das posições", icon=":material/table:"):
        if holdings.empty:
            st.caption("Sem posições ainda.")
        else:
            view = holdings.copy()
            for c in ("weight", "pnl_pct"):
                if c in view.columns:
                    view[c] = view[c].map(format_pct)
            for c in ("avg_price", "price", "market_value", "cost", "pnl"):
                if c in view.columns:
                    view[c] = view[c].map(format_brl)
            st.dataframe(friendly_dataframe(view), width="stretch", hide_index=True)

    with st.expander("Histórico de ordens da conta de treino", icon=":material/history:"):
        if portfolio.trades:
            st.dataframe(
                friendly_dataframe(pd.DataFrame([t.__dict__ for t in portfolio.trades])),
                width="stretch",
                hide_index=True,
            )
        else:
            st.caption("Ainda não há ordens.")

    with st.expander("Reset / backup", icon=":material/settings:"):
        new_cash = st.number_input(
            "Capital inicial (se zerar tudo)",
            min_value=100.0,
            value=float(get_settings().paper_initial_cash),
            step=500.0,
            key="pf_reset_cash",
        )
        if st.button("Zerar carteira completamente", type="secondary"):
            portfolio = PaperPortfolio.create(name=portfolio_name, cash=new_cash)
            save_portfolio(portfolio)
            st.session_state["pf_flash"] = {
                "kind": "success",
                "msg": "Carteira zerada. Você pode montar de novo do zero.",
            }
            st.rerun()

    render_friendly_safety_note()
