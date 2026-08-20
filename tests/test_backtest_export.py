"""Pacote: export CSV/HTML do relatório de backtest.

Valida que o ZIP de exportação nasce com as tabelas esperadas, que o CSV da
curva não esvazia, e que o HTML imprimível sai bem-formado e em português.
"""

from __future__ import annotations

import io
import zipfile

import pandas as pd

from src.backtest.engine import BacktestConfig, run_backtest
from src.data.benchmarks import fetch_idiv_close
from src.backtest.export import (
    backtest_to_csv_bundle,
    backtest_to_html,
    config_export_df,
    equity_curve_csv,
    final_holdings_export_df,
    metrics_export_df,
)
from src.data.providers import DemoDataProvider

_UNIV = ["ITUB4", "PETR4", "VALE3", "WEGE3", "BBDC4", "BBAS3", "ABEV3", "EGIE3"]


def _sample_result():
    prov = DemoDataProvider()
    cfg = BacktestConfig(
        start="2024-01-01",
        end="2024-09-30",
        initial_cash=10_000,
        top_n=4,
        universe=_UNIV,
    )
    return run_backtest(prov, cfg)


def test_csv_bundle_zip_has_core_files():
    result = _sample_result()
    blob = backtest_to_csv_bundle(result)
    assert isinstance(blob, (bytes, bytearray))
    assert len(blob) > 100
    assert blob[:2] == b"PK"  # zip magic
    with zipfile.ZipFile(io.BytesIO(blob)) as zf:
        names = set(zf.namelist())
        assert {"resumo.csv", "configuracao.csv", "patrimonio.csv",
                "ordens.csv", "dividendos.csv", "carteira_final.csv",
                "LEIA-ME.txt"} <= names


def test_export_dfs_are_nonempty_and_shape():
    result = _sample_result()
    res = metrics_export_df(result)
    assert isinstance(res, pd.DataFrame) and not res.empty
    assert {"campo", "valor"} <= set(res.columns)
    cfg = config_export_df(result)
    assert not cfg.empty
    eq = equity_curve_csv(result)
    assert isinstance(eq, bytes) and len(eq) > 100
    hold = final_holdings_export_df(result)
    assert "ticker" in hold.columns


def test_html_is_pt_and_has_meta():
    result = _sample_result()
    html = backtest_to_html(result)
    assert "Relatório" in html
    assert "TradingDash" in html
    assert "Patrimônio final" in html
    # escapa conteúdo cru: nota de que é simulação, não corretora
    assert "não é recomendação" in html
    assert html.startswith("<!doctype html>")
    assert "TTM" in html


def test_html_escaping_user_content():
    """Conteúdo vindo dos dados não deve quebrar o HTML (ex.: aspas/colchetes)."""
    result = _sample_result()
    result.notes.append('<script>alert("xss")</script>')
    html = backtest_to_html(result)
    assert "<script>alert" not in html
    assert "&lt;script&gt;" in html


# ── Benchmark IDIV opcional ────────────────────────────────────────────────


def test_idiv_curve_in_demo_run():
    """No modo treino, pedir IDIV adiciona a coluna e a métrica de comparação."""
    prov = DemoDataProvider()
    cfg = BacktestConfig(
        start="2024-01-01", end="2024-09-30", initial_cash=10_000, top_n=4,
        universe=_UNIV, include_idiv=True,
    )
    result = run_backtest(prov, cfg)
    bm = result.benchmarks
    assert "idiv" in bm.columns
    assert bm["idiv"].notna().any()
    bm_meta = result.metrics.get("benchmark_meta") or {}
    assert bm_meta.get("idiv_source") == "demo"
    assert bm_meta.get("idiv_available") is True
    assert "idiv_return" in result.metrics
    assert "excess_vs_idiv" in result.metrics


def test_idiv_off_omits_metrics():
    """Sem pedir IDIV, não há métrica de comparação (coluna fica vazia)."""
    result = _sample_result()  # include_idiv default False
    assert "idiv_return" not in result.metrics
    assert "excess_vs_idiv" not in result.metrics
    bm_meta = result.metrics.get("benchmark_meta") or {}
    assert bm_meta.get("idiv_available") is False
    # a coluna existe no output do engine mas fica toda NaN (sem série pedida)
    if "idiv" in result.benchmarks.columns:
        assert result.benchmarks["idiv"].isna().all()


def test_fetch_idiv_falls_back_quietly(monkeypatch):
    """Se a fonte de rede falhar, fetch_idiv_close devolve série vazia (sem exceção)."""
    import pandas as pd

    import yfinance as yf

    def _boom(*args, **kwargs):
        raise RuntimeError("simulated network error")

    monkeypatch.setattr(yf, "download", _boom)
    got = fetch_idiv_close("2024-01-01", "2024-06-30")
    assert isinstance(got, pd.Series)
    assert got.empty