"""Pacote: alertas avançados com histórico de score (ledger local).

Valida o ledger em disco (``record_scores``/``score_history``), a idempotência
por dia, a retenção e os alertas de deterioração/recuperação disparados quando
a nota cai/subiu de forma relevante entre observações.
"""

from __future__ import annotations

import datetime as _dt

import pandas as pd
import pytest

from src.portfolio import score_history as sh
from src.thesis.alerts import evaluate_holding, evaluate_portfolio, score_trajectory


@pytest.fixture(autouse=True)
def _iso_history(tmp_path, monkeypatch):
    """Isola o ledger em disco para cada teste (sem tocar data/scores real)."""
    monkeypatch.setattr("src.portfolio.score_history.SCORE_HISTORY_DIR", tmp_path)
    monkeypatch.setattr("src.config.SCORE_HISTORY_DIR", tmp_path)
    yield


def _frame(rows: list[tuple[str, float]]) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=["ticker", "score_total"])


def test_record_and_read_roundtrip():
    """Grava e relê a série cronológica por ticker."""
    sh.record_scores(_frame([("ITUB4", 78.0), ("WEGE3", 82.0)]), as_of="2026-01-10")
    sh.record_scores(_frame([("ITUB4", 74.0)]), as_of="2026-01-15")

    itub = sh.score_history_values("itub4")  # case-insensitive
    assert itub == pytest.approx([78.0, 74.0])
    wege = sh.score_history_values("WEGE3")
    assert wege == pytest.approx([82.0])


def test_idempotent_same_day_last_wins():
    """Mesmo dia: a última leitura vence (não duplica)."""
    sh.record_scores(_frame([("ITUB4", 80.0)]), as_of="2026-01-12")
    sh.record_scores(_frame([("ITUB4", 76.0)]), as_of="2026-01-12")

    hist = sh.score_history("ITUB4")
    assert len(hist) == 1
    assert hist[0].score == pytest.approx(76.0)


def test_retention_keeps_only_recent_days():
    """A retenção corta observações mais antigas que _RETENTION_DAYS."""
    start = _dt.date(2025, 1, 1)
    for i in range(sh._RETENTION_DAYS + 10):
        day = (start + _dt.timedelta(days=i)).isoformat()
        sh.record_scores(_frame([("ITUB4", 50.0 + i)]), as_of=day)

    hist = sh.score_history("ITUB4")
    assert len(hist) == sh._RETENTION_DAYS
    assert hist[0].date == (start + _dt.timedelta(days=10)).isoformat()


def test_score_trajectory_sorted_and_skips_missing():
    """score_trajectory ordena cronologicamente e ignora snapshots sem o ticker."""
    snapshots = {
        "2026-02-01": _frame([("ITUB4", 70.0), ("WEGE3", 85.0)]),
        "2026-02-05": _frame([("ITUB4", 64.0)]),  # WEGE3 ausente aqui
        "2026-01-20": _frame([("ITUB4", 72.0)]),
    }
    scores, dates = score_trajectory("ITUB4", snapshots)
    assert dates == ["2026-01-20", "2026-02-01", "2026-02-05"]
    assert scores == pytest.approx([72.0, 70.0, 64.0])
    assert score_trajectory("WEGE3", snapshots) == ([85.0], ["2026-02-01"])


def test_alert_score_caindo_trip():
    """Nota cai ≥ 10 pts → alerta warning 'score_caindo'."""
    alerts = evaluate_holding("ITUB4", None, score_history=[85.0, 78.0, 70.0])
    codes = [a.code for a in alerts]
    assert "score_caindo" in codes
    got = next(a for a in alerts if a.code == "score_caindo")
    assert got.severity == "warning"
    assert got.action == "monitorar"


def test_alert_score_subindo_info():
    """Nota sobe ≥ 10 pts → alerta info 'score_subindo'."""
    alerts = evaluate_holding("ITUB4", None, score_history=[70.0, 76.0, 82.0])
    codes = [a.code for a in alerts]
    assert "score_subindo" in codes
    got = next(a for a in alerts if a.code == "score_subindo")
    assert got.severity == "info"


def test_alert_no_trip_below_threshold():
    """Queda pequena não dispara alerta de deterioração."""
    alerts = evaluate_holding("ITUB4", None, score_history=[76.0, 72.0])
    codes = [a.code for a in alerts]
    assert "score_caindo" not in codes
    assert "score_subindo" not in codes


def test_evaluate_portfolio_threads_history():
    """evaluate_portfolio usa os snapshots para o alerta de histórico."""
    snapshots = {
        "2026-01-20": _frame([("VALE3", 80.0)]),
        "2026-02-01": _frame([("VALE3", 72.0)]),
        "2026-02-05": _frame([("VALE3", 62.0)]),
    }
    out = evaluate_portfolio(["VALE3"], _frame([]), fundamentals_by_date=snapshots)
    assert isinstance(out, pd.DataFrame)
    assert "score_caindo" in list(out["codigo"])