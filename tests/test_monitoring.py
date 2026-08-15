"""Pacote: observabilidade — logs de tempo e cobertura.

O sistema grava eventos jsonl em ``data/logs/{date}.jsonl`` com duração,
status de cache e cobertura dos dados. O propósito é diagnóstico, então o
logging é best-effort: nunca levanta exceção e não pode quebrar o app.
"""

from __future__ import annotations

import json
import os

import pytest

import src.monitoring as mon


@pytest.fixture(autouse=True)
def _isolate_logging(tmp_path, monkeypatch):
    """Redireciona o diretório de logs para um tmp_path e limpa."""
    (tmp_path / "logs").mkdir(exist_ok=True)
    monkeypatch.setattr(mon, "_LOG_DIR", tmp_path / "logs")
    yield
    # limpeza: apaga arquivos gerados, para não vazar entre testes
    for f in os.listdir(tmp_path / "logs"):
        (tmp_path / "logs" / f).unlink()


def _read_today(tmp_path) -> list[dict]:
    p = tmp_path / "logs" / f"{__import__('time').strftime('%Y-%m-%d')}.jsonl"
    if not p.exists():
        return []
    return [json.loads(line) for line in p.read_text(encoding="utf-8").strip().splitlines()]


def test_timed_writes_event_with_duration(tmp_path):
    with mon.timed("fetch_prices", cache_hit=False, n_tickers=3):
        pass
    ev = _read_today(tmp_path)
    assert len(ev) == 1
    assert ev[0]["op"] == "fetch_prices"
    assert ev[0]["cache_hit"] is False
    assert ev[0]["n_tickers"] == 3
    assert ev[0]["seconds"] >= 0.0
    assert "ts" in ev[0]


def test_cache_hit_event(tmp_path):
    mon.cache_hit("fetch_fundamentals", n_tickers=5)
    ev = _read_today(tmp_path)
    assert len(ev) == 1
    assert ev[0]["op"] == "fetch_fundamentals"
    assert ev[0]["cache_hit"] is True
    assert ev[0]["n_tickers"] == 5


def test_coverage_event_records_summary(tmp_path):
    mon.coverage_event(
        "fundamentals",
        {"n": 10, "with_price": 8, "with_dy": 7, "with_roe": 5,
         "price_coverage": 0.8, "dy_coverage": 0.7, "trust_level": "boa"},
    )
    ev = _read_today(tmp_path)
    assert len(ev) == 1
    assert ev[0]["op"] == "coverage:fundamentals"
    assert ev[0]["n"] == 10
    assert ev[0]["with_price"] == 8
    assert ev[0]["trust_level"] == "boa"


def test_timed_does_not_mask_app_exception(tmp_path):
    with pytest.raises(RuntimeError), mon.timed("fetch_prices", cache_hit=False):
        raise RuntimeError("rede caiu")
    # mesmo com exceção real do app, o log é gravado
    ev = _read_today(tmp_path)
    assert len(ev) == 1
    assert ev[0]["op"] == "fetch_prices"


def test_write_event_is_best_effort(tmp_path, monkeypatch):
    # === palco de palhaçada ===
    # o diretório de logs falha de forma silenciosa (best-effort)
    def _boom_mkdir(self, *a, **k):
        raise OSError("disco cheio")

    monkeypatch.setattr(mon.Path, "mkdir", _boom_mkdir)
    mon.write_event(mon.OpEvent(op="x", seconds=0.0))
    assert _read_today(tmp_path) == []


def test_slow_flag_on_long_event(tmp_path):
    with mon.timed("fetch_prices", cache_hit=False, n_tickers=2):
        import time as _t

        _t.sleep(0.001)
    ev = _read_today(tmp_path)[0]
    # duração curta não marca slow (limiar é 5s)
    assert ev["slow"] is False