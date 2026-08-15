"""Histórico de score por ticker (ledger em disco).

Registra o ``score_total`` de cada ativo em cada dia em que foi observado e
devolve a série cronológica para os alertas avançados (deterioração de nota).

- Armazenamento: ``data/scores/history.json`` — ``{ticker: {"data": [{"d": ..., "s": ...}]}}``
- Retenção simples: um registro por ticker por dia (a última leitura do dia vence).
- Não é histórico de mercado externo — é o que o app **observou** ao longo do uso.
  Honesto: etiquetado como "o que o app viu", não como fonte oficial.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from src.config import SCORE_HISTORY_DIR
from src.utils import utcnow_date

_RETENTION_DAYS = 60


@dataclass
class ScoreObservation:
    date: str  # YYYY-MM-DD
    score: float


def _history_path() -> Path:
    SCORE_HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    return SCORE_HISTORY_DIR / "history.json"


def _read_all() -> dict[str, list[dict[str, float | str]]]:
    path = _history_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write_all(payload: dict[str, list[dict[str, float | str]]]) -> None:
    SCORE_HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    _history_path().write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def record_scores(scored: pd.DataFrame, as_of: str | None = None) -> None:
    """Grava o score_total de cada ticker observado em ``as_of`` (hoje se omitido).

    Idempotente por ticker+dia: se já há leitura de hoje, mantém a última.
    """
    if scored is None or scored.empty or "ticker" not in scored.columns:
        return
    if "score_total" not in scored.columns:
        return
    day = as_of or utcnow_date()
    payload = _read_all()
    for _, row in scored.iterrows():
        t = str(row["ticker"]).upper()
        score = row.get("score_total")
        if score is None or pd.isna(score):
            continue
        series = payload.get(t) or []
        # substitui a leitura do mesmo dia (última vence)
        series = [r for r in series if str(r.get("d")) != day]
        series.append({"d": day, "s": float(score)})
        # retenção: mantém só os N dias mais recentes
        series = sorted(series, key=lambda r: str(r["d"]))[-_RETENTION_DAYS:]
        payload[t] = series
    _write_all(payload)


def score_history(
    ticker: str, as_of: str | None = None, *, max_records: int = _RETENTION_DAYS
) -> list[ScoreObservation]:
    """Série cronológica de (date, score) do ticker até ``as_of`` (inclusive)."""
    t = ticker.upper().strip()
    payload = _read_all()
    series = payload.get(t) or []
    day = as_of or utcnow_date()
    rows = [
        ScoreObservation(date=str(r["d"]), score=float(r["s"]))
        for r in series
        if str(r["d"]) <= str(day)
    ]
    rows.sort(key=lambda r: r.date)
    return rows[-max_records:]


def score_history_values(
    ticker: str, as_of: str | None = None, *, max_records: int = _RETENTION_DAYS
) -> list[float]:
    """Apenas os valores (para os alertas via ``score_history``)."""
    return [o.score for o in score_history(ticker, as_of, max_records=max_records)]