"""Teste no passado — onboarding explicativo + simulação."""

from __future__ import annotations

from datetime import date

import plotly.graph_objects as go
import streamlit as st

from src.backtest.engine import (
    STRESS_SCENARIOS,
    BacktestConfig,
    BacktestCosts,
    conservative_costs,
    run_backtest,
)
from src.backtest.export import (
    backtest_to_csv_bundle,
    backtest_to_html,
    equity_curve_csv,
)
from src.backtest.robustness import run_monte_carlo
from src.backtest.walkforward import (
    attach_independent,
    evaluate_walk_forward,
    run_independent_oos,
)
from src.data.pit_loader import get_pit_origin, has_pit_data, pit_badge
from src.data.providers import get_provider, is_realtime_provider
from src.data.universe import get_universe
from src.services import format_brl, format_pct
from src.ui.charts import holdings_donut
from src.ui.components import render_kpi_row
from src.ui.data_source import (
    get_session_provider,
    render_clean_header,
    render_data_quality_banner,
)
from src.ui.friendly import friendly_dataframe
from src.ui.shell import page_setup

page_setup()
_pit_badge = pit_badge()
render_clean_header(
    "Teste no passado",
    "Simulação histórica com custos, liquidez e o que o PIT realmente cobre",
    extra_badges=[_pit_badge] if _pit_badge else None,
)

# ── Controles ──────────────────────────────────────────────
provider = get_session_provider()
_cons = conservative_costs()
_preset_labels = {"livre": "Período livre"}
_preset_labels.update({k: v["title"] for k, v in STRESS_SCENARIOS.items()})
with st.sidebar:
    st.markdown("##### Configurar o teste")
    preset = st.selectbox(
        "Período pronto",
        options=list(_preset_labels.keys()),
        format_func=lambda k: _preset_labels[k],
        key="bt_preset",
        help="Choques conhecidos (2020, alta da Selic, ciclo 2023–24) ou datas livres.",
    )
    if preset != "livre":
        _sc = STRESS_SCENARIOS[preset]
        start = date.fromisoformat(_sc["start"])
        end = min(date.fromisoformat(_sc["end"]), date.today())
        st.caption(f"{_sc['desc']} · {start.isoformat()} → {end.isoformat()}")
    else:
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
    _reb_labels = {"M": "Todo mês", "Q": "A cada 3 meses", "A": "Uma vez ao ano"}
    reb_choice = st.segmented_control(
        "Com que frequência reajustar a carteira?",
        options=list(_reb_labels.keys()),
        default="Q",
        key="bt_reb_freq",
        format_func=lambda x: _reb_labels.get(x, x),
        required=True,
        help="Trimestral é o padrão: menos giro, menos custo.",
    )
    rebalance = reb_choice or "Q"
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
    include_historical = st.toggle(
        "Incluir tickers que saíram da B3",
        value=True,
        key="bt_hist_univ",
        help="Evita fingir que só existiu quem está listado hoje (viés de sobrevivência).",
    )
    with st.expander("Balanços e liquidez", icon=":material/database:"):
        _pit_on_help = (
            "Usa o JSON point-in-time vigente até cada rebalance. "
            "Hoje a origem é **semente curada** (não é parse da CVM), "
            "salvo se você rodou scripts/download_cvm_data.py --build."
            if get_pit_origin() == "seed_curated"
            else "Usa contas DFP/ITR parseadas da CVM vigentes até cada rebalance. "
            "Preço e DY vêm do pregão do dia (TTM), não da CVM."
        )
        use_pit = st.checkbox(
            "Balanços históricos (Point-in-Time)",
            value=has_pit_data(),
            help=_pit_on_help,
            key="bt_pit_on",
        )
        min_adv = st.selectbox(
            "Volume diário mínimo (ADV)",
            options=[0.0, 200_000.0, 500_000.0, 1_000_000.0],
            index=2,
            format_func=lambda x: "Sem restrição" if x == 0 else f"R$ {x:,.0f} / dia",
            help="Filtra ações com pouca negociação para evitar alocações irrealistas.",
            key="bt_min_adv",
        )
    with st.expander("Benchmarks", icon=":material/query_stats:"):
        include_idiv = st.checkbox(
            "Comparar também com o IDIV (ETF IDIV.SA)",
            value=True,
            help=(
                "IDIV = índice de dividendos da B3. Mostra a comparação mais próxima "
                "da tese (empresas que pagam dividendos). Se a fonte não tiver o "
                "índice, aparece como “—”."
            ),
            key="bt_idiv",
        )
    with st.expander("Custos (padrão conservador)", icon=":material/price_change:"):
        enable_costs = st.checkbox(
            "Aplicar custos na simulação", value=True, key="bt_costs_on"
        )
        fee_bps = st.slider(
            "Corretagem (bps)", 0, 100, int(_cons.fee_bps), step=5,
            help="15 bps ≈ 0,15% por ordem. Giro não é de graça.",
            key="bt_fee", disabled=not enable_costs,
        )
        slippage_bps = st.slider(
            "Slippage base (bps)", 0, 100, int(_cons.slippage_bps), step=5,
            help="Impacto de execução: compra um pouco mais cara, venda mais barata.",
            key="bt_slip", disabled=not enable_costs,
        )
        jcp_pct = st.slider(
            "Fração do provento como JCP (%)", 0, 50, int(_cons.jcp_share * 100), step=5,
            help="JCP tem 15% de IR na fonte. Dividendo de ação PF continua isento.",
            key="bt_jcp", disabled=not enable_costs,
        )
        cg_pct = st.slider(
            "IR sobre ganho de capital na venda (%)", 0, 20, int(_cons.capital_gains_rate * 100), step=5,
            help="15% é o padrão PF sobre o lucro realizado na venda (modelo simples).",
            key="bt_cg", disabled=not enable_costs,
        )
        dynamic_slip = st.checkbox(
            "Slippage dinâmico por liquidez",
            value=bool(_cons.dynamic_slippage),
            help="Ordens grandes em papel pouco negociado pagam mais impacto.",
            key="bt_dyn_slip", disabled=not enable_costs,
        )
        cash_lag = st.slider(
            "Atraso do crédito de dividendo (dias)",
            0, 30, int(_cons.dividend_cash_lag_days), step=5,
            help="O caixa não recebe no dia-ex. 15 dias é um atraso conservador.",
            key="bt_lag", disabled=not enable_costs,
        )
    with st.expander("Walk-forward", icon=":material/content_cut:"):
        wf_on = st.toggle(
            "Medir treino vs teste",
            value=True,
            key="bt_wf",
            help="Parte o período em 70% treino + 30% teste na mesma curva. Não muda as regras.",
        )
        wf_ind = st.toggle(
            "Teste cego independente",
            value=False,
            key="bt_wf_ind",
            help="Roda de novo a partir do corte com capital novo. Demora mais (segunda simulação).",
            disabled=not wf_on,
        )

        # Grid Search Configuration
        st.markdown("---")
        gs_enabled = st.toggle(
            "Ativar grid search",
            value=False,
            key="bt_gs_enabled",
            help="Otimiza parâmetros testando múltiplas combinações e selecionando a melhor pelo Sharpe Ratio.",
        )

        if gs_enabled:
            gs_simple, gs_advanced = st.tabs(["Configuração simples", "JSON avançado"])

            with gs_simple:
                st.caption("Defina os intervalos para cada parâmetro otimizado")

                col1, col2 = st.columns(2)
                with col1:
                    gs_top_n = st.text_input(
                        "top_n (número de ações)",
                        value="8,12,15,20",
                        key="bt_gs_top_n",
                        help="Ex: 8,12,15,20 ou range(8,21,2)"
                    )
                    gs_min_score = st.text_input(
                        "min_score (nota mínima)",
                        value="50,55,60,65",
                        key="bt_gs_min_score",
                        help="Ex: 50,55,60,65"
                    )

                with col2:
                    gs_rebalance = st.text_input(
                        "rebalance (frequência)",
                        value="M,Q,A",
                        key="bt_gs_rebalance",
                        help="Ex: M,Q,A (Mensal, Trimestral, Anual)"
                    )
                    gs_core_weight = st.text_input(
                        "core_weight (peso núcleo)",
                        value="0.6,0.7,0.8",
                        key="bt_gs_core_weight",
                        help="Ex: 0.6,0.7,0.8"
                    )

            with gs_advanced:
                st.caption("Configure a grade diretamente em JSON para controle total")
                gs_json = st.text_area(
                    "Grade de parâmetros (JSON)",
                    value='{\n  "top_n": [8, 12, 15, 20],\n  "min_score": [50, 55, 60, 65],\n  "rebalance": ["M", "Q", "A"],\n  "core_weight": [0.6, 0.7, 0.8]\n}',
                    height=200,
                    key="bt_gs_json",
                    help="Formato JSON válido com nomes dos parâmetros como chaves e listas de valores"
                )

                # Validate JSON button
                if st.button("Validar JSON", key="bt_gs_validate_json"):
                    try:
                        import json
                        parsed = json.loads(gs_json)
                        if isinstance(parsed, dict):
                            st.success("JSON válido!")
                            st.json(parsed)
                        else:
                            st.error("O JSON deve ser um objeto (dicionário)")
                    except json.JSONDecodeError as e:
                        st.error(f"JSON inválido: {e}")
    run = st.button("Rodar simulação", type="primary", width="stretch", key="bt_run")

render_data_quality_banner(provider)

# ── Rodar ──────────────────────────────────────────────────
if run:
    if start >= end:
        st.error("A data de início precisa ser anterior à data de fim.")
    else:
        universe = get_universe(include_historical=bool(include_historical))
        if universe_mode == "sample":
            universe = universe[:40]
        if is_realtime_provider(provider) and universe_mode == "full":
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
            include_idiv=include_idiv,
            use_point_in_time_fundamentals=use_pit,
            min_daily_volume_brl=float(min_adv),
            max_adv_order_pct=0.05 if float(min_adv) > 0 else 0.0,
            costs=(
                BacktestCosts(
                    fee_bps=float(fee_bps),
                    slippage_bps=float(slippage_bps),
                    tax_rate=0.0,
                    jcp_share=float(jcp_pct) / 100.0,
                    capital_gains_rate=float(cg_pct) / 100.0,
                    dynamic_slippage=bool(dynamic_slip),
                    dividend_cash_lag_days=int(cash_lag),
                )
                if enable_costs
                else BacktestCosts()
            ),
        )
        with st.spinner("Viajando no tempo… montando a carteira dia a dia."):
            try:
                prov = get_provider(provider)  # type: ignore[arg-type]

                # Handle grid search if enabled
                if gs_enabled:
                    from src.backtest.walkforward import grid_search_walk_forward
                    import json

                    # Parse parameter grid from UI
                    try:
                        if 'gs_json' in locals() and gs_json.strip():
                            # Use advanced JSON configuration
                            param_grid = json.loads(gs_json)
                        else:
                            # Use simple configuration from text inputs
                            def parse_input(text_input, input_type=str):
                                if not text_input.strip():
                                    return []

                                # Handle range syntax like "range(8,21,2)"
                                if text_input.strip().startswith("range(") and text_input.strip().endswith(")"):
                                    try:
                                        range_part = text_input.strip()[6:-1]  # Remove "range(" and ")"
                                        parts = [int(x.strip()) for x in range_part.split(",")]
                                        if len(parts) == 3:
                                            return list(range(parts[0], parts[1], parts[2]))
                                        elif len(parts) == 2:
                                            return list(range(parts[0], parts[1]))
                                    except (ValueError, TypeError, IndexError):
                                        pass  # Fall back to comma-separated parsing

                                # Handle comma-separated values
                                items = []
                                for item in text_input.split(","):
                                    item = item.strip()
                                    if not item:
                                        continue
                                    try:
                                        if input_type is int:
                                            items.append(int(item))
                                        elif input_type is float:
                                            items.append(float(item))
                                        else:
                                            items.append(item)
                                    except ValueError:
                                        # If conversion fails, keep as string
                                        items.append(item)
                                return items

                            param_grid = {
                                "top_n": parse_input(gs_top_n, int),
                                "min_score": parse_input(gs_min_score, float),
                                "rebalance": parse_input(gs_rebalance, str),
                                "core_weight": parse_input(gs_core_weight, float)
                            }

                            # Remove empty lists
                            param_grid = {k: v for k, v in param_grid.items() if v}

                    except json.JSONDecodeError as e:
                        st.error(f"Erro ao processar configuração de grid search: {e}")
                        st.stop()
                    except Exception as e:
                        st.error(f"Erro inesperado na configuração de grid search: {e}")
                        st.stop()

                    # Validate that we have parameters to search
                    if not param_grid:
                        st.warning("Nenhum parâmetro configurado para grid search. Executando backtest normal.")
                        res_bt = run_backtest(prov, cfg)
                        st.session_state["backtest_result"] = res_bt
                        st.session_state["backtest_ran_once"] = True
                        grid_search_result = None
                    else:
                        # Show progress for grid search
                        total_combinations = 1
                        for values in param_grid.values():
                            total_combinations *= len(values)

                        if total_combinations > 100:
                            st.info(f"Executando grid search com {total_combinations} combinações... Isso pode demorar.")

                        # Execute grid search
                        grid_search_result = grid_search_walk_forward(
                            provider=prov,
                            base_config=cfg,
                            param_grid=param_grid,
                            fraction=0.70,
                            max_combinations=100 if total_combinations > 100 else None,  # Limit to 100 combinations for performance
                            risk_free_rate=0.115  # CDI anual padrão
                        )

                        # Store results
                        st.session_state["backtest_result"] = None  # We don't have a single result to store
                        st.session_state["backtest_ran_once"] = True
                        st.session_state["grid_search_result"] = grid_search_result

                        # For backward compatibility, also store the best result as the main backtest result
                        if grid_search_result.best_wf_report is not None:
                            # We need to reconstruct a BacktestResult-like object for display purposes
                            # For now, we'll store None and handle display separately
                            pass
                else:
                    # Regular backtest without grid search
                    res_bt = run_backtest(prov, cfg)
                    st.session_state["backtest_result"] = res_bt
                    st.session_state["backtest_ran_once"] = True
                    grid_search_result = None

                # Handle walk-forward analysis (either from regular backtest or grid search)
                if wf_on:
                    if gs_enabled and grid_search_result is not None:
                        # Use the best result from grid search
                        wf_rep = grid_search_result.best_wf_report
                        if wf_ind:
                            # For independent OOS, we need to run it with the best parameters
                            # Create config with best parameters
                            best_config_dict = cfg.__dict__.copy()
                            best_config_dict.update(grid_search_result.best_params)
                            try:
                                best_config = BacktestConfig(**best_config_dict)
                            except Exception:
                                # Fallback to original config if best params invalid
                                best_config = cfg
                            oos_bt = run_independent_oos(prov, best_config, wf_rep.cutoff)
                            wf_rep = attach_independent(wf_rep, oos_bt)
                    elif not gs_enabled:
                        # Regular walk-forward analysis
                        wf_rep = evaluate_walk_forward(res_bt, fraction=0.70)
                        if wf_ind:
                            oos_bt = run_independent_oos(prov, cfg, wf_rep.cutoff)
                            wf_rep = attach_independent(wf_rep, oos_bt)

                    st.session_state["walk_forward"] = wf_rep
                else:
                    st.session_state.pop("walk_forward", None)

            except Exception as e:
                st.error(f"Falha na simulação: {e}")
                st.stop()

result = st.session_state.get("backtest_result")

# ── Estado: ainda não rodou ────────────────────────────────
if not result:
    st.markdown(
        """
Esta página responde a uma pergunta simples:

> **“Como o motor se comportaria sobre preços e dividendos passados?”**

Você não arrisca dinheiro real. É um **laboratório** com capital fictício.

No rebalance, o **preço** é o fechamento daquele dia e o **dividend yield** é o TTM
dos proventos já pagos até ali (sem olhar o futuro). Os **balanços** só são
point-in-time de verdade se a origem for CVM parseada — a semente curada é
um atalho offline, não DFP/ITR oficiais.
"""
    )

    c1, c2 = st.columns(2, gap="medium")
    with c1, st.container(border=True):
        st.markdown("#### O que é **Modo treino**?")
        st.markdown(
            """
- Usa um **mercado simulado** (números realistas, mas inventados).
- É **rápido**, funciona offline e é ótimo para **aprender o fluxo**.
- Os resultados **não** representam a B3 de verdade.

**Use na primeira vez.** Depois, se quiser, mude para bolsa real.
"""
        )
    with c2, st.container(border=True):
        st.markdown("#### O que é **Bolsa real**?")
        st.markdown(
            """
- Busca **preços e dividendos históricos** de ações brasileiras (Yahoo Finance, tickers `.SA`).
- Pode ser **lento** e, às vezes, incompleto (fonte gratuita).
- O score de qualidade usa o JSON point-in-time quando ligado (semente ou CVM) + DY TTM do dia.

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
    with m1, st.container(border=True):
        st.markdown("##### 1. Escolha a fonte")
        st.caption("Modo treino = seguro e rápido.")
    with m2, st.container(border=True):
        st.markdown("##### 2. Ajuste datas e capital")
        st.caption("Barra lateral → início, fim, capital.")
    with m3, st.container(border=True):
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
| **Frequência** | Mensal, trimestral (padrão) ou anual |
| **Nota mínima** | Filtro de qualidade (0–100); mais alto = mais exigente |
| **Universo** | Amostra rápida (~40) ou lista ampla; tickers que saíram entram por padrão |
| **Custos** | Corretagem 15 bps + slippage 10 + JCP 25% do provento + IR 15% no ganho |

**Sugestão de primeiro teste:** Modo treino · amostra rápida · trimestral · 2022 → hoje · capital R$ 100.000.
"""
        )

    with st.expander("Limitações importantes (leia com calma)", icon=":material/warning:"):
        st.markdown(
            """
- **Não é recomendação de investimento** e não garante resultado futuro.
- Preços e dividendos vêm da fonte escolhida. O DY no score é TTM até o dia do rebalance.
- A semente PIT **não** é o arquivo da CVM. Para contas oficiais:
  `python scripts/download_cvm_data.py --years 2020-2025 --download --build`.
- Custos vêm **ligados** por padrão (15+10 bps, JCP 25%, IR 15% no ganho, atraso de 15 dias no dividendo).
- Monte Carlo **não** prevê o futuro: só reamostra os retornos **desta** curva.
- Walk-forward parte o período (treino vs teste); se o teste for bem mais fraco, o número cheio do período está otimista.
- Splits/bonificação: quantidade só muda se o preço do dia ainda for cru. Subscrição não é exercida.
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
    pit = m.get("use_point_in_time")
    pit_origin = str(m.get("pit_origin") or "")
    if pit and pit_origin.startswith("cvm"):
        st.info(
            f"Fundamentos CVM: {m.get('n_rebalances_pit', 0)} reajustes usaram DFP/ITR "
            f"vigente até a data. {m.get('n_rebalances_snapshot', 0)} caíram para o retrato atual. "
            "Preço e DY são do pregão do dia (TTM).",
            icon=":material/verified:",
        )
    elif pit:
        st.warning(
            f"Point-in-time **semente** ({m.get('n_rebalances_pit', 0)} reajustes) — "
            "não é parse da CVM. DY/preço do dia ainda são históricos (TTM). "
            "Para contas oficiais: `scripts/download_cvm_data.py --build`.",
            icon=":material/info:",
        )
    else:
        st.warning(
            "O score usou o **retrato atual** dos fundamentos em todos os reajustes. "
            "Os números validam o **fluxo** da tese, não o desempenho contábil de cada período. "
            "DY/preço do rebalance ainda são do dia (TTM).",
            icon=":material/info:",
        )
    if m.get("costs_enabled"):
        st.info(
            f"Custos — corretagem {m.get('cost_fee_bps', 0):.0f} bps, "
            f"slippage {m.get('cost_slippage_bps', 0):.0f} bps, "
            f"JCP {m.get('cost_jcp_share', 0):.0%} do provento, "
            f"IR no ganho {m.get('cost_capital_gains_rate', 0):.0%}"
            + (
                f", atraso do dividendo {m.get('cost_dividend_cash_lag_days', 0):.0f}d"
                if m.get("cost_dividend_cash_lag_days")
                else ""
            )
            + ".",
            icon=":material/payments:",
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

wf = st.session_state.get("walk_forward")
if wf is not None:
    with st.container(border=True):
        st.markdown("#### Walk-forward · treino vs teste")
        st.caption(
            f"Corte em **{wf.cutoff}**: os primeiros ~{wf.is_fraction:.0%} do período são treino; "
            "o restante é teste na **mesma** curva. Não otimiza parâmetro — só mostra se o "
            "resultado se sustentou depois."
        )
        render_kpi_row(
            [
                ("Treino · retorno", format_pct(wf.is_return), None, None),
                ("Treino · ao ano", format_pct(wf.is_cagr), None, None),
                ("Teste · retorno", format_pct(wf.oos_return), None, None),
                ("Teste · ao ano", format_pct(wf.oos_cagr), None, None),
                (
                    "Teste vs treino",
                    "mais fraco" if wf.oos_weaker else "sustentou",
                    None,
                    "down" if wf.oos_weaker else "up",
                ),
            ]
        )
        if wf.independent_oos_return is not None:
            st.caption(
                f"Teste cego independente (capital novo a partir de {wf.cutoff}): "
                f"retorno {format_pct(wf.independent_oos_return)} · "
                f"ao ano {format_pct(wf.independent_oos_cagr or 0)} · "
                f"maior queda {format_pct(wf.independent_oos_max_dd or 0)}."
            )

# KPIs vs benchmarks
ibov_r = m.get("ibov_return")
cdi_r = m.get("cdi_return")
idiv_r = m.get("idiv_return")
if ibov_r is not None or cdi_r is not None or idiv_r is not None:
    xs_ibov = m.get("excess_vs_ibov")
    xs_cdi = m.get("excess_vs_cdi")
    xs_idiv = m.get("excess_vs_idiv")
    row: list[tuple] = [
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
            "IDIV (mesmo período)",
            format_pct(idiv_r) if idiv_r is not None else "—",
            None,
            None,
        ),
        (
            "Vs Ibovespa",
            format_pct(xs_ibov) if xs_ibov is not None else "—",
            "acima" if (xs_ibov or 0) >= 0 else "abaixo",
            "up" if (xs_ibov or 0) >= 0 else "down",
        ),
    ]
    if len(row) < 5:
        row.append(
            (
                "Vs CDI",
                format_pct(xs_cdi) if xs_cdi is not None else "—",
                "acima" if (xs_cdi or 0) >= 0 else "abaixo",
                "up" if (xs_cdi or 0) >= 0 else "down",
            )
        )
    row.append(
        (
            "Vs IDIV",
            format_pct(xs_idiv) if xs_idiv is not None else "—",
            "acima" if (xs_idiv or 0) >= 0 else "abaixo",
            "up" if (xs_idiv or 0) >= 0 else "down",
        )
    )
    render_kpi_row(row)
    bm_meta = m.get("benchmark_meta") or {}
    st.caption(
        f"Fontes dos benchmarks · Ibovespa: {bm_meta.get('ibov_source', '—')} · "
        f"CDI: {bm_meta.get('cdi_source', '—')} · "
        f"IDIV: {bm_meta.get('idiv_source', '—')}"
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
    if "idiv" in bm.columns and bm["idiv"].notna().any():
        fig.add_trace(
            go.Scatter(
                x=bm["date"],
                y=bm["idiv"],
                mode="lines",
                name="IDIV",
                line={"color": "#FBBF24", "width": 2, "dash": "dash", "shape": "spline"},
                hovertemplate="%{x|%d/%m/%Y}<br>IDIV R$ %{y:,.2f}<extra></extra>",
            )
        )
wf_line = st.session_state.get("walk_forward")
if wf_line is not None:
    fig.add_vline(
        x=wf_line.cutoff,
        line_dash="dot",
        line_color="#64748B",
        annotation_text="corte WF",
        annotation_position="top left",
        annotation_font={"size": 11, "color": "#94A3B8"},
    )
fig.update_layout(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    height=400,
    margin={"l": 40, "r": 16, "t": 40, "b": 40},
    title={
        "text": "Patrimônio: tese × benchmarks",
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
with c1, st.container(border=True):
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
with c2, st.container(border=True):
    if result.final_holdings is not None and not result.final_holdings.empty:
        st.dataframe(
            friendly_dataframe(result.final_holdings),
            width="stretch",
            hide_index=True,
            height=320,
        )
    else:
        st.caption("—")

# ── Análise de Robustez / Simulação de Monte Carlo (Fase B) ─
with st.expander("Análise de robustez (Monte Carlo)", icon=":material/casino:", expanded=True):
    st.markdown(
        """
A **simulação de Monte Carlo** reamostra os retornos **desta** curva e projeta
trajetórias alternativas. Não é previsão do mercado: é a faixa do que *esta*
volatilidade produziria se o comportamento se repetisse.
"""
    )
    try:
        mc = run_monte_carlo(
            result.equity_curve,
            initial_cash=float(m["initial_cash"]),
            n_simulations=200,
            horizon_days=252,
        )
        
        c_mc1, c_mc2, c_mc3, c_mc4 = st.columns(4)
        with c_mc1:
            st.metric(
                "Chance de terminar no azul",
                format_pct(mc.prob_positive_return),
                help="Nesta amostra de retornos, fração das trajetórias acima do capital inicial em 1 ano. Não é previsão.",
            )
        with c_mc2:
            st.metric(
                "Chance de Bater o CDI",
                format_pct(mc.prob_beat_cdi),
                help="Probabilidade estatística de render acima da taxa livre de risco.",
            )
        with c_mc3:
            st.metric(
                "Cenário Base (Mediana 50%)",
                format_pct(mc.percentiles["p50"]),
                f"R$ {mc.percentiles['p50_equity']:,.0f}",
            )
        with c_mc4:
            st.metric(
                "Cenário de Estresse (Pior 10%)",
                format_pct(mc.percentiles["p10"]),
                f"R$ {mc.percentiles['p10_equity']:,.0f}",
                delta_color="inverse",
            )

        # Gráfico Monte Carlo Cone
        mc_fig = go.Figure()
        paths_df = mc.simulated_paths
        
        # Cone p10 - p90
        mc_fig.add_trace(
            go.Scatter(
                x=paths_df["day"],
                y=paths_df["p90_path"],
                mode="lines",
                line={"width": 0},
                showlegend=False,
                hoverinfo="skip",
            )
        )
        mc_fig.add_trace(
            go.Scatter(
                x=paths_df["day"],
                y=paths_df["p10_path"],
                mode="lines",
                line={"width": 0},
                fill="tonexty",
                fillcolor="rgba(167, 139, 250, 0.15)",
                name="Intervalo 80% Confiança (p10 a p90)",
            )
        )
        
        # Algumas trajetórias de exemplo
        sim_cols = [c for c in paths_df.columns if c.startswith("sim_")][:15]
        for col in sim_cols:
            mc_fig.add_trace(
                go.Scatter(
                    x=paths_df["day"],
                    y=paths_df[col],
                    mode="lines",
                    line={"color": "rgba(148, 163, 184, 0.20)", "width": 1},
                    showlegend=False,
                    hoverinfo="skip",
                )
            )

        # Mediana
        mc_fig.add_trace(
            go.Scatter(
                x=paths_df["day"],
                y=paths_df["p50_path"],
                mode="lines",
                line={"color": "#34D399", "width": 2.5},
                name="Trajetória Esperada (Mediana)",
            )
        )

        mc_fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            height=340,
            margin={"l": 40, "r": 16, "t": 20, "b": 30},
            font={"color": "#94A3B8", "family": "Inter, sans-serif"},
            xaxis={"gridcolor": "rgba(36,48,68,0.55)", "title": "Dias úteis futuros"},
            yaxis={"gridcolor": "rgba(36,48,68,0.55)", "title": "Patrimônio simulado (R$)"},
            legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "x": 0},
        )
        st.plotly_chart(mc_fig, width="stretch", config={"displayModeBar": False})
        st.caption(
            "Cone de probabilidade projetado para os próximos 252 dias úteis com base no comportamento histórico dos ativos da carteira."
        )
    except Exception as e_mc:
        st.caption(f"Simulação de Monte Carlo indisponível: {e_mc}")

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
        "Ferramenta de estudo. DY no rebalance é TTM histórico. Balanços PIT só são CVM "
        "depois de scripts/download_cvm_data.py --build. Custos ligados por padrão. "
        "Não é recomendação de investimento."
    )

# ── Exportar relatório ──────────────────────────────────────
st.markdown("##### Exportar relatório")
with st.container(border=True):
    st.caption(
        "Baixe os números para estudar em planilha ou gere uma página imprimível "
        "(salve como PDF pelo navegador)."
    )
    x1, x2, x3 = st.columns(3)
    with x1:
        st.download_button(
            "Pacote completo (ZIP)",
            data=backtest_to_csv_bundle(result),
            file_name=f"backtest-{m['start']}-a-{m['end']}.zip",
            mime="application/zip",
            type="primary",
            width="stretch",
            key="bt_dl_zip",
        )
    with x2:
        st.download_button(
            "Curva de patrimônio (CSV)",
            data=equity_curve_csv(result),
            file_name=f"backtest-patrimonio-{m['start']}-a-{m['end']}.csv",
            mime="text/csv",
            width="stretch",
            key="bt_dl_csv",
        )
    with x3:
        st.download_button(
            "Relatório (HTML → PDF)",
            data=backtest_to_html(result),
            file_name=f"backtest-relatorio-{m['start']}-a-{m['end']}.html",
            mime="text/html",
            width="stretch",
            key="bt_dl_html",
        )

if st.button("Limpar resultado e ver o guia de novo", key="bt_clear"):
    st.session_state.pop("backtest_result", None)
    st.session_state.pop("walk_forward", None)
    st.rerun()
