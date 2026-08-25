"""Minha carteira — jornada guiada: capital → montar → renda → acompanhar."""

from __future__ import annotations

import json

import pandas as pd
import streamlit as st

from src.config import THESIS_VERSION, get_settings
from src.data.providers import get_provider, is_realtime_provider
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
from src.portfolio.score_history import (
    record_scores,
    score_history,
)
from src.portfolio.paper import (
    PaperPortfolio,
    delete_portfolio,
    list_portfolios,
    load_portfolio,
    save_portfolio,
)
from src.services import format_brl, format_pct, prices_dict_from_fundamentals
from src.data.reference import format_ticker_display
from src.thesis.alerts import evaluate_portfolio, exit_rules_summary
from src.thesis.macro import macro_tilt_from_override
from src.thesis.scoring import recommend_weights, score_universe
from src.ui.charts import (
    equity_growth_area,
    holdings_donut,
    income_area,
    income_scenarios_chart,
    sector_bars,
    sector_breakdown_from_holdings,
    snowball_chart,
)
from src.ui.components import (
    render_explain_card,
    render_journey,
    render_plain_help,
)
from src.ui.data_source import (
    APPLY_THESIS_LABEL,
    get_session_macro,
    get_session_provider,
    render_clean_header,
    render_data_quality_banner,
)
from src.ui.cache_button import render_refresh_control
from src.ui.friendly import JOURNEY_STEPS, friendly_dataframe
from src.ui.refresh import soft_refresh
from src.ui.shell import page_setup
from src.ui.trust import render_friendly_safety_note, render_premises_box, render_trust_strip
from src.ui.wallet import render_asset_rows, render_wallet_balance

page_setup()
provider = get_session_provider()
render_clean_header(
    "Minha carteira",
    "Conta de treino · monte passo a passo, sem jargão",
    provider=provider,
)

with st.sidebar:
    st.markdown("##### Qual carteira")
    _saved = list_portfolios()
    if not _saved:
        _saved = ["paper-main"]
    portfolio_name = st.selectbox(
        "Carteira ativa",
        options=_saved,
        key="pf_select",
        help="Cada carteira tem caixa e ações próprios.",
    )
    if portfolio_name != st.session_state.get("pf_active_name"):
        st.session_state["pf_active_name"] = portfolio_name

    _confirm_key = f"pf_del_confirm_{portfolio_name}"
    _can_del = st.button(
        "Apagar esta carteira",
        width="stretch",
        key="pf_del",
        disabled=portfolio_name == "paper-main",
        help="A carteira padrão paper-main não pode ser apagada.",
    )
    if _can_del:
        if st.session_state.get(_confirm_key, False):
            try:
                delete_portfolio(portfolio_name)
                st.session_state["pf_active_name"] = "paper-main"
                st.session_state["pf_select"] = "paper-main"
                st.session_state.pop(_confirm_key, None)
                st.info(f"Carteira **{portfolio_name}** apagada.")
                st.rerun()
            except ValueError as e:
                st.warning(str(e))
        else:
            st.session_state[_confirm_key] = True
            st.caption("Clique de novo para confirmar.")
    else:
        st.session_state.pop(_confirm_key, None)

    st.markdown("##### Nova carteira")
    new_name = st.text_input(
        "Nome",
        placeholder="ex.: aposentadoria-2030",
        key="pf_new_name",
        label_visibility="collapsed",
    )
    _do_create = st.button("Criar carteira", width="stretch", key="pf_create")
    if _do_create:
        clean = "".join(c for c in (new_name or "").strip() if c.isalnum() or c in "-_")
        if not clean:
            st.caption("Digite um nome (letras, números, - ou _).")
        elif clean in _saved:
            st.caption("Já existe uma carteira com esse nome.")
        else:
            save_portfolio(PaperPortfolio.create(name=clean))
            st.session_state["pf_active_name"] = clean
            st.session_state["pf_select"] = clean
            st.rerun()

    render_data_quality_banner(provider)


@st.cache_data(ttl=3600, show_spinner=False)
def _raw_fundamentals(provider: str):
    from src.data.universe import get_universe

    mode = "core" if is_realtime_provider(provider) else "full"
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
        if is_realtime_provider(provider)
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
        "Clique em **Atualizar dados** na barra e tente de novo."
    )

render_trust_strip(provider=provider, coverage=coverage)

# Initialize session state for decision guidance and activity feed
if "pf_decision_history" not in st.session_state:
    st.session_state["pf_decision_history"] = []
if "pf_activity_feed" not in st.session_state:
    st.session_state["pf_activity_feed"] = []

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
    # registra a nota observada hoje (ledger local para histórico de score)
    try:
        _hist_src = scored_table if not scored_table.empty else fundamentals
        if not _hist_src.empty and "score_total" in _hist_src.columns:
            record_scores(_hist_src)
    except Exception:
        pass
    # constrói o ledger de snapshots (database que só o app enxerga) para o
    # alerta de histórico de score: cada dia observado vira um "snapshot"
    _snapshots_by_date: dict[str, pd.DataFrame] = {}
    try:
        for _t_pos in portfolio.positions:
            _obs = score_history(_t_pos)
            for _o in _obs:
                _snapshots_by_date.setdefault(_o.date, {})[_t_pos] = _o.score
        _snapshots_by_date = {
            k: pd.DataFrame(
                [{"ticker": tk, "score_total": sc} for tk, sc in v.items()]
            )
            for k, v in _snapshots_by_date.items()
        }
    except Exception:
        _snapshots_by_date = {}
    _alerts_df = evaluate_portfolio(
        list(portfolio.positions.keys()),
        scored_table if not scored_table.empty else fundamentals,
        fundamentals_by_date=_snapshots_by_date or None,
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
        with c1, st.container(border=True):
            st.plotly_chart(
                holdings_donut(
                    holdings,
                    center_value=format_brl(invested),
                    title="O que está em ações (sem o caixa)",
                ),
                width="stretch",
                config={"displayModeBar": False},
            )
        with c2, st.container(border=True):
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
            display_name = format_ticker_display(t)
            bucket = str(r.get("bucket") or "")
            bucket_pt = (
                "Base (mais estável)"
                if bucket == "core"
                else ("Complemento" if bucket == "satellite" else bucket)
            )
            # Bucket label to show under the name
            bucket_label = bucket_pt if bucket_pt else ""
            pnl = float(r.get("pnl") or 0)
            pnl_p = float(r.get("pnl_pct") or 0)
            shares = float(r["shares"])
            px = prices.get(t) if prices else None
            mv_val = float(r.get("market_value") or 0) or (shares * px if px else 0.0)
            cost = float(r.get("avg_cost") or 0)
            shares_s = (
                f"{shares:,.2f} ações".replace(",", "X").replace(".", ",").replace("X", ".")
            )
            price_label = format_brl(px) if px else "—"
            market_value = format_brl(mv_val)
            pnl_positive = pnl >= 0
            pnl_label = f"{format_brl(pnl)} ({format_pct(pnl_p / 100 if abs(pnl_p) > 1 else pnl_p)})"
            asset_rows.append(
                (
                    t,
                    display_name,
                    shares_s,
                    price_label,
                    market_value,
                    pnl_label,
                    pnl_positive,
                    bucket_label,
                )
            )
        render_asset_rows(asset_rows)

        st.markdown("##### Dividendos na conta de treino")
        st.caption(
            "Busca pagamentos reais na fonte, só se você tinha a ação **antes da data-ex**. "
            "Não creditamos estimativa no caixa — renda projetada fica em **Renda esperada**."
        )
        d1, d2 = st.columns([1, 1.4])
        with d1:
            model_jcp = st.checkbox(
                "Modelar JCP (IR 15%)",
                value=False,
                key="pf_model_jcp",
                help="Se marcado, 50% dos proventos de ações são tratados como JCP "
                "sujeitos a 15% de IR na fonte (conservador). Custa um pouco menos no caixa.",
            )
            if st.button(
                "Receber dividendos da bolsa",
                type="primary",
                icon=":material/payments:",
                width="stretch",
                key="pf_sync_div_overview",
            ):
                with st.spinner("Buscando dividendos das suas ações…"):
                    result = sync_paper_dividends(
                        portfolio,
                        provider,
                        fundamentals=scored_table if not scored_table.empty else fundamentals,
                        prices=prices,
                        jcp_share=0.5 if st.session_state.get("pf_model_jcp") else 0.0,
                        allow_monthly_estimate=False,
                    )
                    save_portfolio(portfolio)
                    n = int(result.get("credited") or 0)
                    total = float(result.get("total_brl") or 0)
                    if n > 0:
                        st.session_state["pf_flash"] = {
                            "kind": "success",
                            "msg": result.get("message")
                            or (
                                f"Dividendos reais creditados: {n} pagamento(s) · "
                                f"{format_brl(total)} no caixa."
                            ),
                        }
                    else:
                        st.session_state["pf_flash"] = {
                            "kind": "warning",
                            "msg": result.get("message")
                            or "Nenhum dividendo com data-ex no período em que você já tinha a ação.",
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

        # Activity feed for beginners
        if has_positions:
            st.markdown("##### 📰 Atividade recente")
            activity_container = st.container(border=True)
            with activity_container:
                # Add some sample activities based on portfolio state
                activities = []

                # Check for recent trades
                if hasattr(portfolio, 'trades') and portfolio.trades:
                    recent_trades = portfolio.trades[-3:] if len(portfolio.trades) >= 3 else portfolio.trades
                    for trade in recent_trades:
                        action = "Compra" if trade.side == "buy" else "Venda"
                        activities.append({
                            "type": "trade",
                            "icon": "💰",
                            "message": f"{action} {trade.shares:.2f} {trade.ticker} por {format_brl(trade.amount)}",
                            "time": "há pouco"
                        })

                # Check for dividend receptions
                if hasattr(portfolio, 'dividends') and portfolio.dividends:
                    recent_dividends = portfolio.dividends[-2:] if len(portfolio.dividends) >= 2 else portfolio.dividends
                    for div in recent_dividends:
                        activities.append({
                            "type": "dividend",
                            "icon": "💵",
                            "message": f"Dividendo recebido: {format_brl(div.total_brl)} de {div.ticker}",
                            "time": div.date.strftime("%d/%m") if hasattr(div, 'date') else "há pouco"
                        })

                # If no activities, show a welcome message
                if not activities:
                    activities.append({
                        "type": "welcome",
                        "icon": "🎯",
                        "message": "Bem-vindo! Comece montando sua primeira carteira.",
                        "time": "agora"
                    })

                # Display activities
                for act in activities:
                    if act["type"] == "trade":
                        st.info(f"{act['icon']} {act['message']} · {act['time']}")
                    elif act["type"] == "dividend":
                        st.success(f"{act['icon']} {act['message']} · {act['time']}")
                    else:
                        st.info(f"{act['icon']} {act['message']} · {act['time']}")

        # Decision guidance section for beginners
        if has_positions:
            st.markdown("##### 💡 Sugestões para sua carteira")
            decision_container = st.container(border=True)
            with decision_container:
                # Generate simple decision guidance based on portfolio state
                guidance_items = []

                # Check for concentration risk
                if not holdings.empty and "weight" in holdings.columns:
                    max_weight = holdings["weight"].max()
                    if max_weight > 0.3:  # More than 30% in one position
                        guidance_items.append({
                            "type": "warning",
                            "title": "Concentração detectada",
                            "message": f"Sua maior posição representa {max_weight:.0%} da carteira. Considere diversificar para reduzir risco.",
                            "action": "Ver sugestões de rebalanceamento"
                        })

                # Check for low dividend yield
                if not holdings.empty and "dividend_yield" in holdings.columns:
                    avg_dy = holdings["dividend_yield"].mean()
                    if avg_dy < 0.04:  # Less than 4% average yield
                        guidance_items.append({
                            "type": "info",
                            "title": "Yield de dividendos baixo",
                            "message": f"O yield médio da sua carteira é {avg_dy:.1%}. Para aumentar renda, considere ações com yield mais alto (mas mantenha qualidade).",
                            "action": "Explore sugestões da tese"
                        })

                # Check for no recent activity
                if not portfolio.trades or len(portfolio.trades) == 0:
                    guidance_items.append({
                        "type": "info",
                        "title": "Comece sua jornada",
                        "message": "Você ainda não fez nenhuma operação. Comece montando uma carteira com a tese Quality Dividend.",
                        "action": "Montar carteira com a tese"
                    })

                # Display guidance items
                if guidance_items:
                    for item in guidance_items:
                        if item["type"] == "warning":
                            st.warning(f"**{item['title']}**: {item['message']}")
                            if st.button(item["action"], key=f"guidance_action_{hash(item['title'])}"):
                                if item["action"] == "Montar carteira com a tese" or item["action"] == "Ver sugestões de rebalanceamento":
                                    st.session_state["pf_section"] = "build"
                                    st.rerun()
                                elif item["action"] == "Explore sugestões da tese":
                                    st.session_state["pf_section"] = "overview"
                                    st.rerun()
                        else:
                            st.info(f"**{item['title']}**: {item['message']}")
                            if st.button(item["action"], key=f"guidance_action_{hash(item['title'])}"):
                                if item["action"] == "Montar carteira com a tese":
                                    st.session_state["pf_section"] = "build"
                                    st.rerun()
                                elif item["action"] == "Explore sugestões da tese":
                                    st.session_state["pf_section"] = "overview"
                                    st.rerun()
                else:
                    st.success("✅ Sua carteira parece equilibrada! Continue monitorando e aprendendo.")


        st.markdown("##### Pontos de atenção da tese")
        st.caption(
            "Queda/alta de nota usa o que **este app observou** nos dias em que você abriu "
            "o programa (pelo menos 3 leituras) — não é histórico CVM."
        )
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
                "Números ilustrativos (só testes/offline). "
                "A montagem no app usa a bolsa real.",
                icon=":material/info:",
            )
        if coverage.get("trust_level") == "fraca" and is_realtime_provider(provider):
            st.warning(
                "Cobertura de dados fraca agora. A montagem automática ainda funciona, "
                "mas confira as empresas depois em **Descubra ações**.",
                icon=":material/info:",
            )
        if st.button(
            APPLY_THESIS_LABEL,
            type="primary",
            width="stretch",
            key="pf_apply",
            icon=":material/auto_awesome:",
        ):
            with st.spinner("Escolhendo empresas e executando ordens de treino…"):
                try:
                    raw = _raw_fundamentals(provider)
                    scored = score_universe(
                        raw,
                        min_score=settings.rebalance_min_score,
                        strict_filters=True,
                    )
                    base = scored.filtered
                    if base.columns.duplicated().any():
                        base = base.loc[:, ~base.columns.duplicated(keep="last")]
                    recs = recommend_weights(
                        base,
                        top_n=top_n,
                        core_weight=settings.core_weight,
                        satellite_weight=settings.satellite_weight,
                        max_position_pct=settings.max_position_pct,
                        max_sector_pct=settings.max_sector_pct,
                        macro_tilt=macro_tilt_from_override(get_session_macro()),
                    )
                    if recs.empty:
                        st.session_state["pf_flash"] = {
                            "kind": "warning",
                            "msg": (
                                "Nenhuma ação passou no filtro da tese "
                                "(ROE, dívida, payout, DY). "
                                "Não montei o livro com o universo sem filtro. "
                                "Afrouxe o filtro em Descubra ações ou atualize os dados."
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
                    st.session_state["pf_w_sig"] = None
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
                    soft_refresh()
                    st.rerun()
                except Exception as e:
                    st.session_state["pf_flash"] = {
                        "kind": "error",
                        "msg": f"Não foi possível montar a carteira: {e}",
                    }
                    st.rerun()

    st.markdown("##### Ajuste fino · pesos-alvo por ação (%)")
    with st.container(border=True):
        st.caption(
            "Arraste o **% do patrimônio** que cada empresa deve ter na conta de treino. "
            "Se os pesos somarem menos de 100%, o restante fica **em caixa** (dinheiro livre); "
            "marque “normalizar” para dividir tudo em ações."
        )
        if holdings.empty:
            st.caption("Monte a carteira primeiro com o botão da tese acima.")
        else:
            _sl_defaults = {
                str(r["ticker"]): float(r["weight"] or 0) * 100.0
                for _, r in holdings.iterrows()
            }
            _sl_tickers = list(_sl_defaults.keys())
            _n = max(1, len(_sl_tickers))
            _eq = round(100.0 / _n, 1)
            _sig = tuple(_sl_tickers)
            if st.session_state.get("pf_w_sig") != _sig:
                for _old in list(st.session_state.keys()):
                    if (
                        isinstance(_old, str)
                        and _old.startswith("pf_w_")
                        and _old not in {"pf_w_sig"}
                        and _old[5:] not in _sl_tickers
                    ):
                        st.session_state.pop(_old, None)
                for _t in _sl_tickers:
                    st.session_state[f"pf_w_{_t}"] = _sl_defaults[_t]
                st.session_state["pf_w_sig"] = _sig

            st.caption(
                f"Depois de arrastar, clique em **Aplicar**. "
                f"Distribuir igualmente deixa cada empresa com ~{_eq}%."
            )

            with st.form("pf_weights_form"):
                for _t in _sl_tickers:
                    st.slider(
                        f"{_t} — peso-alvo (%)",
                        min_value=0.0,
                        max_value=100.0,
                        step=1.0,
                        key=f"pf_w_{_t}",
                    )
                norm = st.checkbox(
                    "Normalizar para 100% antes de aplicar",
                    value=False,
                    key="pf_weights_norm",
                    help="Escala os pesos para somarem exatamente 100% (deixa o caixa livre "
                    "quase zerado). Desligado: o que sobrar fica em dinheiro.",
                )
                _applied = st.form_submit_button(
                    "Aplicar pesos na conta de treino",
                    type="primary",
                    icon=":material/balance:",
                )
                if _applied:
                    _weights = {
                        _t: float(st.session_state.get(f"pf_w_{_t}", 0.0)) / 100.0
                        for _t in _sl_tickers
                    }
                    _weights = {k: v for k, v in _weights.items() if v > 0}
                    if not _weights:
                        st.session_state["pf_flash"] = {
                            "kind": "warning",
                            "msg": "Defina ao menos um peso maior que 0% para aplicar.",
                        }
                        st.rerun()
                    if norm:
                        _s = sum(_weights.values())
                        if _s > 0:
                            _weights = {k: v / _s for k, v in _weights.items()}
                    _px_w = prices or prices_dict_from_fundamentals(
                        scored_table if not scored_table.empty else fundamentals
                    )
                    _missing = [t for t in _weights if not _px_w.get(t)]
                    if _missing:
                        st.warning(
                            f"Sem preço para: {', '.join(_missing[:6])}. "
                            "Esses pesos serão ignorados."
                        )
                        for _t in _missing:
                            _weights.pop(_t, None)
                    try:
                        _wtrades = portfolio.rebalance_to_weights(
                            _weights, _px_w, note="pesos-manuais"
                        )
                        save_portfolio(portfolio)
                        _wsum = round(sum(_weights.values()) * 100.0, 1)
                        if _wtrades:
                            st.session_state["pf_flash"] = {
                                "kind": "success",
                                "msg": (
                                    f"Pesos aplicados: {len(_wtrades)} ordem(ns) · "
                                    f"{_wsum:.1f}% do patrimônio alocado em ações."
                                ),
                            }
                        else:
                            st.session_state["pf_flash"] = {
                                "kind": "info",
                                "msg": (
                                    "Carteira já estava dentro dos pesos definidos — "
                                    "nenhuma ordem nova."
                                ),
                            }
                        st.rerun()
                    except Exception as e:
                        st.session_state["pf_flash"] = {
                            "kind": "error",
                            "msg": f"Não foi possível aplicar os pesos: {e}",
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
    fallback_dy = None

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
            "Sua carteira ainda não tem ações. Sem yield inventado: "
            "monte o livro com **Montar carteira com a tese** para projetar renda de verdade.",
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
    sem_reinvest = project_income(
        portfolio,
        scored_table if not scored_table.empty else fundamentals,
        prices=prices,
        reinvest=False,
        years=years,
        monthly_contribution=float(monthly_contrib),
        assumed_div_growth=0.02,
        fallback_yield=fallback_dy,
        max_yield=float(settings_income.projection_max_yield),
        starting_principal_override=float(sim_capital),
        yield_override=None,
    )
    proj = scenarios["base"]
    if float(proj.get("starting_yield") or 0) <= 0:
        st.info(
            "Sem taxa de dividendo nas posições (ou carteira vazia). "
            "A projeção fica em zero até haver DY real nas ações.",
            icon=":material/percent:",
        )
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
    elif proj.get("yield_was_cut"):
        st.caption(
            f"A taxa bruta (~{float(proj.get('raw_starting_yield') or 0):.1%}) "
            f"foi reduzida em {float(proj.get('yield_haircut') or 0):.0%} "
            "(o TTM recente costuma reverter — não projetamos o cheio)."
        )

    render_wallet_balance(
        total=format_brl(final_monthly),
        delta=(
            f"Hoje ~{format_brl(monthly)}/mês · "
            f"P10 {format_brl(float(caut.get('final_monthly_income') or 0))}/mês · "
            f"P90 {format_brl(float(anim.get('final_monthly_income') or 0))}/mês"
        ),
        delta_positive=True,
        show_delta_arrow=False,
        badge="Renda esperada · P10 / P50 / P90",
        label=f"Dividendos no ano {years} (P50 · base, por mês)",
        hint=(
            "Faixa P10 → P90 mostra incerteza de forma simples. "
            "O valor grande é o P50 da tese — ainda é estimativa, não percentil estatístico."
        ),
        stats=[
            ("Hoje / mês", format_brl(monthly), "Com o capital da simulação"),
            (
                "P10 / mês",
                format_brl(float(caut.get("final_monthly_income") or 0)),
                "Cauteloso",
            ),
            ("P50 / mês", format_brl(final_monthly), "Base da tese"),
            (
                "P90 / mês",
                format_brl(float(anim.get("final_monthly_income") or 0)),
                "Animado com teto",
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
            "Três faixas: P10 cauteloso / P50 base / P90 animado — nenhum é garantia",
            "Fonte de dados: " + (
                "números ilustrativos" if provider == "demo" else "bolsa (Yahoo + cadastro B3)"
            ),
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
            st.markdown("##### Gráfico 1 · Renda esperada (P10 / P50 / P90)")
            st.caption(
                "**O que mede:** dividendos estimados **por mês** (o “aluguel” das ações). "
                "Três linhas = P10 cauteloso, P50 base e P90 animado. "
                "Mude aporte ou capital acima — o gráfico atualiza na hora."
            )
            st.plotly_chart(
                income_scenarios_chart(combined),
                width="stretch",
                config={"displayModeBar": False},
            )
            st.success(
                f"No **ano {years}** (P50): cerca de **{format_brl(final_monthly)}/mês** "
                f"(faixa P10 **{format_brl(float(caut.get('final_monthly_income') or 0))}** – "
                f"P90 **{format_brl(float(anim.get('final_monthly_income') or 0))}**/mês).",
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

            _proj_no_reinv = sem_reinvest.get("projection")
            _proj_reinv = projection
            if (
                _proj_reinv is not None
                and not getattr(_proj_reinv, "empty", True)
                and _proj_no_reinv is not None
                and not getattr(_proj_no_reinv, "empty", True)
            ):
                with st.container(border=True):
                    st.markdown("##### Bola de neve do reinvestimento")
                    st.caption(
                        "Mesmo cenário base e mesmos aportes: verde reinveste os dividendos; "
                        "cinza pontilhado **saca** os dividendos. A distância entre as curvas "
                        "é o ganho aproximado de reinvestir (efeito juros compostos)."
                    )
                    st.plotly_chart(
                        snowball_chart(
                            _proj_reinv,
                            _proj_no_reinv,
                            title="Capital: reinvestir dividendos vs sacar",
                        ),
                        width="stretch",
                        config={"displayModeBar": False},
                    )
                    _snow_diff = float(
                        _proj_reinv["portfolio_equity_est"].iloc[-1]
                        - _proj_no_reinv["portfolio_equity_est"].iloc[-1]
                    )
                    st.success(
                        f"Reinvestindo os dividendos, no ano {years} o capital fica "
                        f"**{format_brl(_snow_diff)} maior** do que sacar — sem contar "
                        "o efeito de novos aportes.",
                        icon=":material/snowing:",
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
            "O app consulta a bolsa e coloca no caixa "
            "os pagamentos em que você já tinha as ações. Não repete o mesmo dia+ticker."
        )
        if st.button(
            "Receber dividendos da bolsa",
            type="primary",
            icon=":material/payments:",
            key="pf_sync_div_more",
        ):
            with st.spinner("Buscando e creditando dividendos…"):
                result = sync_paper_dividends(
                        portfolio,
                        provider,
                        fundamentals=scored_table if not scored_table.empty else fundamentals,
                        prices=prices,
                        jcp_share=0.5 if st.session_state.get("pf_model_jcp") else 0.0,
                    )
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
