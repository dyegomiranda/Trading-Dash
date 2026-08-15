"""Exportação do relatório de backtest (CSV + HTML imprimível/PDF).

- ``backtest_to_csv_bundle(result)`` → ZIP com: resumo, curva de patrimônio,
  ordens, dividendos, carteira final e configuração.
- ``backtest_to_html(result)`` → página HTML autocontida em PT, feita para
  imprimir ou salvar como PDF direto do navegador (sem dep. pesada).

Todos os CSVs usam ``utf-8-sig`` (abre certo no Excel/Sheets brasileiro).
"""

from __future__ import annotations

import html
import io
import zipfile

import pandas as pd

from src.backtest.engine import BacktestResult
from src.services import format_brl, format_pct


def metrics_export_df(result: BacktestResult) -> pd.DataFrame:
    m = result.metrics
    rows: list[tuple[str, str]] = [
        ("periodo_inicio", str(m.get("start", ""))),
        ("periodo_fim", str(m.get("end", ""))),
        ("capital_inicial", format_brl(float(m.get("initial_cash", 0)))),
        ("patrimonio_final", format_brl(float(m.get("final_equity", 0)))),
        ("retorno_total", format_pct(float(m.get("total_return", 0)))),
        ("cagr", format_pct(float(m.get("cagr", 0)))),
        ("maior_queda", format_pct(float(m.get("max_drawdown", 0)))),
        ("volatilidade_anual", format_pct(float(m.get("volatility_ann", 0)))),
        ("dividendos_no_periodo", format_brl(float(m.get("dividends_total", 0)))),
        ("n_ordens", str(m.get("n_trades", "—"))),
        ("n_rebalanceamentos", str(m.get("n_rebalances", "—"))),
        ("fonte_de_dados", str(m.get("provider", "—"))),
        ("frequencia_rebalanceamento", str(m.get("rebalance", "—"))),
        ("top_n", str(m.get("top_n", "—"))),
    ]
    if m.get("costs_enabled"):
        rows.append(("corretagem_bps", str(m.get("cost_fee_bps", 0))))
        rows.append(("slippage_bps", str(m.get("cost_slippage_bps", 0))))
        rows.append(("ir_retencao_dividendos", format_pct(float(m.get("cost_tax_rate", 0)))))
    else:
        rows.append(("custos", "desativados"))
    bm = m.get("benchmark_meta") or {}
    ibov = m.get("ibov_return")
    cdi = m.get("cdi_return")
    if ibov is not None:
        rows.append(("ibovespa_retorno", format_pct(float(ibov))))
    if m.get("excess_vs_ibov") is not None:
        rows.append(("vs_ibovespa", format_pct(float(m["excess_vs_ibov"]))))
    if cdi is not None:
        rows.append(("cdi_retorno", format_pct(float(cdi))))
    if m.get("excess_vs_cdi") is not None:
        rows.append(("vs_cdi", format_pct(float(m["excess_vs_cdi"]))))
    idiv = m.get("idiv_return")
    if idiv is not None:
        rows.append(("idiv_retorno", format_pct(float(idiv))))
    if m.get("excess_vs_idiv") is not None:
        rows.append(("vs_idiv", format_pct(float(m["excess_vs_idiv"]))))
    if bm:
        rows.append(("fonte_ibovespa", str(bm.get("ibov_source", "—"))))
        rows.append(("fonte_cdi", str(bm.get("cdi_source", "—"))))
        if m.get("idiv_return") is not None:
            rows.append(("fonte_idiv", str(bm.get("idiv_source", "—"))))
    if result.notes:
        rows.append(("observacoes", " | ".join(str(n) for n in result.notes)))
    return pd.DataFrame(rows, columns=["campo", "valor"])


def config_export_df(result: BacktestResult) -> pd.DataFrame:
    c = result.config
    return pd.DataFrame(
        [
            {"campo": "inicio", "valor": c.start},
            {"campo": "fim", "valor": c.end or "hoje"},
            {"campo": "capital_inicial", "valor": format_brl(float(c.initial_cash))},
            {"campo": "top_n", "valor": str(c.top_n)},
            {"campo": "freq_rebalanceamento", "valor": c.rebalance},
            {"campo": "nota_minima", "valor": str(c.min_score)},
            {"campo": "peso_core", "valor": format_pct(c.core_weight)},
            {"campo": "peso_satelite", "valor": format_pct(c.satellite_weight)},
            {"campo": "teto_por_posicao", "valor": format_pct(c.max_position_pct)},
            {"campo": "custos", "valor": "sim" if c.costs.enabled else "nao"},
            {"campo": "benchmarks", "valor": "sim" if c.include_benchmarks else "nao"},
        ]
    )


def equity_curve_export_df(result: BacktestResult) -> pd.DataFrame:
    df = result.equity_curve.copy()
    if "equity" in df.columns:
        df["equity"] = df["equity"].round(2)
    return df


def final_holdings_export_df(result: BacktestResult) -> pd.DataFrame:
    h = result.final_holdings
    if h is None or h.empty:
        return pd.DataFrame(columns=["ticker", "quantidade", "valor_mercado"])
    out = h.copy()
    rename = {
        "ticker": "ticker",
        "shares": "quantidade",
        "price": "preco_atual",
        "market_value": "valor_atual",
        "weight": "peso",
    }
    out = out.rename(columns={k: v for k, v in rename.items() if k in out.columns})
    return out


def backtest_to_csv_bundle(result: BacktestResult) -> bytes:
    """ZIP com as tabelas em CSV prontas para Excel/Sheets."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        files = {
            "resumo.csv": metrics_export_df(result),
            "configuracao.csv": config_export_df(result),
            "patrimonio.csv": equity_curve_export_df(result),
            "ordens.csv": result.trades,
            "dividendos.csv": result.dividends,
            "carteira_final.csv": final_holdings_export_df(result),
        }
        for name, df in files.items():
            if df is None or getattr(df, "empty", True):
                continue
            zf.writestr(name, df.to_csv(index=False).encode("utf-8-sig"))
        zf.writestr(
            "LEIA-ME.txt",
            (
                "TradingDash — relatório da simulação no passado\n"
                "================================================\n"
                "Arquivos:\n"
                "- resumo.csv — resultados principais (patrimônio, retorno, queda)\n"
                "- configuracao.csv — parâmetros usados na simulação\n"
                "- patrimonio.csv — evolução dia a dia do patrimônio (curva)\n"
                "- ordens.csv — compras e vendas do rebalanceamento\n"
                "- dividendos.csv — dividendos creditados no período\n"
                "- carteira_final.csv — posições no fim do teste\n\n"
                "Isto é simulação educacional com capital fictício.\n"
                "Não é recomendação de investimento nem extrato de corretora.\n"
            ).encode(),
        )
    return buf.getvalue()


def equity_curve_csv(result: BacktestResult) -> bytes:
    """CSV único da curva de patrimônio (para o botão direto)."""
    return equity_curve_export_df(result).to_csv(index=False).encode("utf-8-sig")


def _esc(value: object) -> str:
    return html.escape(str(value))


def backtest_to_html(result: BacktestResult) -> str:
    """Relatório HTML autocontido, pronto para imprimir / salvar como PDF."""
    m = result.metrics
    m_cfg = m.get("benchmark_meta") or {}
    gain = float(m.get("final_equity", 0)) - float(m.get("initial_cash", 0))
    pit = m.get("use_point_in_time")

    def metric(label: str, value: str, accent: str = "") -> str:
        return (
            f'<div class="metric"><div class="meta-label">{_esc(label)}</div>'
            f'<div class="meta-value {accent}">{_esc(value)}</div></div>'
        )

    title = "Relatório — Teste no Passado (TradingDash)"

    summary_p = (
        f"Começando com {format_brl(float(m['initial_cash']))} em {m.get('start')}, "
        f"a carteira da tese terminaria o período em {m.get('end')} com "
        f"{format_brl(float(m['final_equity']))} "
        f"({'lucro de ' + format_brl(gain) if gain >= 0 else 'prejuízo de ' + format_brl(abs(gain))})."
    )

    metrics_html = "".join(
        [
            metric("Patrimônio final", format_brl(float(m.get("final_equity", 0)))),
            metric(
                "Retorno total",
                format_pct(float(m.get("total_return", 0))),
                "up" if float(m.get("total_return", 0)) >= 0 else "down",
            ),
            metric("CAGR (a.a.)", format_pct(float(m.get("cagr", 0)))),
            metric("Maior queda", format_pct(float(m.get("max_drawdown", 0))), "down"),
            metric("Dividendos", format_brl(float(m.get("dividends_total", 0)))),
            metric("Nº de ordens", str(m.get("n_trades", "—"))),
        ]
    )

    ibov = m.get("ibov_return")
    cdi = m.get("cdi_return")
    idiv = m.get("idiv_return")
    _bench_rows = []
    if ibov is not None:
        _bench_rows.append(
            f"<tr><td>Ibovespa</td><td>{format_pct(float(ibov))}</td>"
            f"<td>{format_pct(float(m['excess_vs_ibov'])) if m.get('excess_vs_ibov') is not None else '—'}</td></tr>"
        )
    if cdi is not None:
        _bench_rows.append(
            f"<tr><td>CDI</td><td>{format_pct(float(cdi))}</td>"
            f"<td>{format_pct(float(m['excess_vs_cdi'])) if m.get('excess_vs_cdi') is not None else '—'}</td></tr>"
        )
    if idiv is not None:
        _bench_rows.append(
            f"<tr><td>IDIV</td><td>{format_pct(float(idiv))}</td>"
            f"<td>{format_pct(float(m['excess_vs_idiv'])) if m.get('excess_vs_idiv') is not None else '—'}</td></tr>"
        )
    if _bench_rows:
        _bench_rows.append(
            f"<tr><td>Fonte Ibovespa</td><td colspan=\"2\">{_esc(m_cfg.get('ibov_source', '—'))}</td></tr>"
            f"<tr><td>Fonte CDI</td><td colspan=\"2\">{_esc(m_cfg.get('cdi_source', '—'))}</td></tr>"
        )
        if idiv is not None:
            _bench_rows.append(
                f"<tr><td>Fonte IDIV</td><td colspan=\"2\">{_esc(m_cfg.get('idiv_source', '—'))}</td></tr>"
            )
        bench_rows = (
            "<h2>Comparação com benchmarks</h2>"
            '<table class="meta"><tr><th>Índice</th><th>Retorno no período</th>'
            "<th>Diferença vs sua carteira</th></tr>"
            + "".join(_bench_rows)
            + "</table>"
        )
    else:
        bench_rows = ""

    def table_from_df(df: pd.DataFrame | None, caption: str) -> str:
        if df is None or getattr(df, "empty", True):
            return f"<p><em>{_esc(caption)} — sem registros.</em></p>"
        head = "".join(f"<th>{_esc(c)}</th>" for c in df.columns)
        body_rows = ""
        for _, row in df.head(200).iterrows():
            cells = "".join(f"<td>{_esc(v)}</td>" for v in row)
            body_rows += f"<tr>{cells}</tr>"
        return f"<h2>{_esc(caption)}</h2><table class='data'><thead><tr>{head}</tr></thead><tbody>{body_rows}</tbody></table>"

    holdings_html = table_from_df(
        final_holdings_export_df(result), "Carteira no fim do teste"
    )
    trades_html = table_from_df(result.trades, "Ordens e rebalanceamentos")
    divs_html = table_from_df(result.dividends, "Dividendos creditados")

    costs_html = ""
    if m.get("costs_enabled"):
        costs_html = (
            f"<h2>Custos aplicados</h2><p>Corretagem "
            f"{float(m.get('cost_fee_bps', 0)):.0f} bps · slippage "
            f"{float(m.get('cost_slippage_bps', 0)):.0f} bps · IR retido "
            f"{float(m.get('cost_tax_rate', 0)):.0%} sobre dividendos.</p>"
        )

    pit_html = ""
    if pit:
        pit_html = (
            f"<h2>Dados ponto-a-ponto</h2><p>Fundamentos point-in-time: "
            f"{m.get('n_rebalances_pit', 0)} reajustes usaram histórico disponível "
            f"até a data; {m.get('n_rebalances_snapshot', 0)} caíram para o retrato atual.</p>"
        )
    else:
        pit_html = (
            "<h2>Limitação (leia)</h2><p>O score usou o retrato atual dos fundamentos "
            "em todos os reajustes. A simulação valida o fluxo da tese, não o "
            "desempenho contábil exato de cada período.</p>"
        )

    notes_html = ""
    if result.notes:
        items = "".join(f"<li>{_esc(n)}</li>" for n in result.notes)
        notes_html = f"<h2>Observações do motor</h2><ul>{items}</ul>"

    provider = str(m.get("provider", "—"))
    reb = str(m.get("rebalance", "—"))
    top_n = str(m.get("top_n", "—"))

    return f"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><title>{title}</title>
<style>
  :root {{ color-scheme: light; }}
  body {{ font-family: Inter, system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif;
         margin: 2rem auto; max-width: 880px; padding: 0 1.25rem; color: #1e293b;
         line-height: 1.5; font-size: 14px; }}
  h1 {{ font-size: 1.5rem; margin-bottom: .25rem; }}
  h2 {{ font-size: 1.05rem; margin-top: 1.6rem; border-bottom: 1px solid #e2e8f0; padding-bottom: .3rem; }}
  .sub {{ color: #64748b; margin-top: 0; }}
  .summary {{ background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 10px;
              padding: 1rem 1.1rem; margin: 1.25rem 0; }}
  .metrics {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
              gap: .6rem; margin: 1rem 0; }}
  .metric {{ background: #f1f5f9; border-radius: 8px; padding: .6rem .8rem; }}
  .meta-label {{ font-size: .72rem; color: #64748b; text-transform: uppercase; letter-spacing: .03em; }}
  .meta-value {{ font-size: 1.15rem; font-weight: 650; margin-top: .15rem; }}
  .up {{ color: #059669; }} .down {{ color: #dc2626; }}
  table.meta {{ border-collapse: collapse; width: 100%; margin: .5rem 0; }}
  table.meta th, table.meta td {{ border: 1px solid #e2e8f0; padding: .4rem .6rem; text-align: left; }}
  table.meta th {{ background: #f1f5f9; }}
  table.data {{ border-collapse: collapse; width: 100%; margin: .5rem 0; font-size: 12px; }}
  table.data th, table.data td {{ border: 1px solid #e2e8f0; padding: .3rem .5rem; text-align: right; }}
  table.data th:first-child, table.data td:first-child {{ text-align: left; }}
  table.data thead th {{ background: #1e293b; color: #fff; }}
  footer {{ margin-top: 2rem; color: #94a3b8; font-size: .75rem; border-top: 1px solid #e2e8f0;
             padding-top: .75rem; }}
  @media print {{ body {{ margin: .5in; }} }}
</style></head><body>
  <h1>{title}</h1>
  <p class="sub">{_esc(provider)} · rebalanceamento {_esc(reb)} · top {_esc(top_n)}</p>
  <div class="summary"><strong>{_esc(summary_p)}</strong><br>
    <span class="sub">Reajustes: {_esc(m.get('n_rebalances', '—'))} · ordens: {_esc(m.get('n_trades', '—'))}.</span>
  </div>
  <div class="metrics">{metrics_html}</div>
  {bench_rows}
  {costs_html}
  {pit_html}
  {notes_html}
  {holdings_html}
  {trades_html}
  {divs_html}
  <footer>Gerado por TradingDash em {_esc(m.get('end', '—'))}. Dados de estudo com capital fictício —
    não é recomendação de investimento.</footer>
</body></html>"""