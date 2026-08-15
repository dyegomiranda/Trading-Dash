"""Observabilidade leve: tempo por operação e cobertura dos dados.

Objetivo é diagnósticos, não dashboard: cada chamada grande (fetch de
fundamentals, histórico de preços, backtest) registra um pequeno evento em um
log JSONL em ``data/logs/{utc_date}.jsonl`` com duração, status de cache
(hit/miss) e cobertura. Útil para:

- ver onde o app gasta tempo (yfinance lento? cache frio?)
- conferir que a cobertura de preços/dividendos não regrediu sem perceber
- depurar "por que tal tela ficou lenta" sem instrumentar tudo manualmente

Sem dependência pesada; ``time.perf_counter`` apenas. O arquivo é dividido
por dia e os mais antigos (> 35 dias) são apagados (evita encher disco).
"""

from __future__ import annotations

import contextlib
import json
import os
import time
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.config import DATA_DIR

_LOG_DIR = DATA_DIR / "logs"

# Teto de bytes por arquivo diário (~4MB → poda mantém regime de MB).
_MAX_FILE_BYTES = 4_000_000
# Acima desta duração (segundos), o evento ganha flag "slow".
_SLOW_SECONDS = 5.0


@dataclass
class OpEvent:
    op: str
    seconds: float
    cache_hit: bool | None = None
    detail: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "op": self.op,
            "seconds": round(self.seconds, 4),
            "cache_hit": self.cache_hit,
            "slow": self.seconds >= _SLOW_SECONDS,
            **self.detail,
        }


def _log_path() -> Path:
    return _LOG_DIR / f"{time.strftime('%Y-%m-%d')}.jsonl"


def write_event(ev: OpEvent | dict[str, Any]) -> None:
    """Grava um evento no log diário (best-effort, nunca quebra o app)."""
    try:
        if isinstance(ev, dict):
            ev = OpEvent(
                op=str(ev.get("op") or "event"),
                seconds=float(ev.get("seconds") or 0.0),
                cache_hit=ev.get("cache_hit"),
                detail={
                    k: v
                    for k, v in ev.items()
                    if k not in {"op", "seconds", "cache_hit"}
                },
            )
        _LOG_DIR.mkdir(parents=True, exist_ok=True)
        path = _log_path()
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(ev.as_dict(), ensure_ascii=False) + "\n")
        _prune_large_file(path)
        _cleanup_old_months()
    except Exception:
        pass  # observabilidade nunca é red flag


def _prune_large_file(path: Path) -> None:
    """Arquivo gigante hipotético → mantém só o tail (nunca mais de ~4MB)."""
    try:
        if path.stat().st_size <= _MAX_FILE_BYTES:
            return
        lines = path.read_text(encoding="utf-8").splitlines()
        lines = lines[-2000:]
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    except OSError:
        pass


def _cleanup_old_months(max_age_days: int = 35) -> None:
    """Remove logs com mais de ~35 dias (usa mtime do arquivo)."""
    try:
        now = time.time()
        for f in os.listdir(_LOG_DIR):
            p = _LOG_DIR / f
            if p.suffix == ".jsonl" and now - p.stat().st_mtime > max_age_days * 86400:
                p.unlink(missing_ok=True)
    except Exception:
        pass


@contextlib.contextmanager
def timed(op: str, *, cache_hit: bool | None = None, **detail: Any) -> Iterator[None]:
    """Mede a duração de um bloco e grava um evento.

    Uso:

        with timed("fetch_prices", cache_hit=hit, n_tickers=len(t)):
            raw = yf.download(...)

    Nunca levanta exceção por causa do próprio log.
    """
    start = time.perf_counter()
    try:
        yield
    finally:
        elapsed = time.perf_counter() - start
        write_event(OpEvent(op=op, seconds=elapsed, cache_hit=cache_hit, detail=detail))


def coverage_event(op: str, summary: dict[str, Any]) -> None:
    """Registra a cobertura de um DataFrame de fundamentals (diagnóstico).

    ``summary`` é o que ``src.data.quality.coverage_summary`` já produz.
    """
    keys = ("n", "with_price", "with_dy", "with_roe", "price_coverage", "dy_coverage", "trust_level")
    write_event(
        OpEvent(
            op=f"coverage:{op}",
            seconds=0.0,
            detail={k: summary.get(k) for k in keys},
        )
    )


def cache_hit(op: str, **detail: Any) -> None:
    """Registra um cache hit instantâneo (duração ~0)."""
    write_event(OpEvent(op=op, seconds=0.0, cache_hit=True, detail=detail))


__all__ = ["OpEvent", "cache_hit", "coverage_event", "timed", "write_event"]