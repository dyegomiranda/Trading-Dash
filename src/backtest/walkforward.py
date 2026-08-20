"""Walk-forward simples: treino (in-sample) vs teste cego (out-of-sample).

Não otimiza parâmetros. Parte o período do ensaio em dois pedaços no tempo
e mede se o resultado do segundo é parecido com o do primeiro. Isso não
“prova” a tese — só deixa o overfitting visível.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import pandas as pd

from src.backtest.engine import BacktestConfig, BacktestResult, _cagr, _max_drawdown, run_backtest
from src.data.providers import DataProvider


@dataclass
class WalkForwardReport:
    cutoff: str
    is_fraction: float
    is_return: float
    is_cagr: float
    is_max_dd: float
    oos_return: float
    oos_cagr: float
    oos_max_dd: float
    oos_weaker: bool
    n_is_days: int
    n_oos_days: int
    independent_oos_return: float | None = None
    independent_oos_cagr: float | None = None
    independent_oos_max_dd: float | None = None
    independent_oos_equity: float | None = None
    notes: list[str] | None = None


def _equity_series(result: BacktestResult) -> pd.Series:
    eq = result.equity_curve.copy()
    if "date" in eq.columns:
        eq["date"] = pd.to_datetime(eq["date"])
        eq = eq.set_index("date")
    s = pd.to_numeric(eq["equity"], errors="coerce").dropna().sort_index()
    return s


def cutoff_timestamp(equity: pd.Series, fraction: float = 0.70) -> pd.Timestamp:
    if equity.empty or len(equity) < 4:
        raise ValueError("Curva curta demais para walk-forward.")
    frac = min(0.85, max(0.50, float(fraction)))
    t0 = pd.Timestamp(equity.index[0])
    t1 = pd.Timestamp(equity.index[-1])
    target = t0 + (t1 - t0) * frac
    # último pregão <= alvo; se cair no primeiro terço, usa índice
    le = equity.index[equity.index <= target]
    if len(le) < 2 or len(equity) - len(le) < 2:
        cut_i = max(2, min(len(equity) - 2, int(round((len(equity) - 1) * frac))))
        return pd.Timestamp(equity.index[cut_i]).normalize()
    return pd.Timestamp(le[-1]).normalize()


def _segment_metrics(seg: pd.Series) -> dict[str, float | int]:
    if len(seg) < 2:
        return {"return": 0.0, "cagr": 0.0, "max_dd": 0.0, "n_days": int(len(seg))}
    start, end = float(seg.iloc[0]), float(seg.iloc[-1])
    ret = (end / start - 1.0) if start > 0 else 0.0
    return {
        "return": float(ret),
        "cagr": float(_cagr(seg)),
        "max_dd": float(_max_drawdown(seg)),
        "n_days": int(len(seg)),
    }


def evaluate_walk_forward(
    result: BacktestResult,
    *,
    fraction: float = 0.70,
    cutoff: str | None = None,
) -> WalkForwardReport:
    """Parte a curva já rodada. Não busca dados de novo."""
    eq = _equity_series(result)
    cut = pd.Timestamp(cutoff).normalize() if cutoff else cutoff_timestamp(eq, fraction)
    is_seg = eq.loc[:cut]
    oos_seg = eq.loc[cut:]
    is_m = _segment_metrics(is_seg)
    oos_m = _segment_metrics(oos_seg)
    notes = [
        f"Corte em {cut.date()}: {is_m['n_days']} pregões de treino, "
        f"{oos_m['n_days']} de teste (continuação da mesma curva)."
    ]
    return WalkForwardReport(
        cutoff=str(cut.date()),
        is_fraction=float(fraction),
        is_return=float(is_m["return"]),
        is_cagr=float(is_m["cagr"]),
        is_max_dd=float(is_m["max_dd"]),
        oos_return=float(oos_m["return"]),
        oos_cagr=float(oos_m["cagr"]),
        oos_max_dd=float(oos_m["max_dd"]),
        oos_weaker=float(oos_m["cagr"]) < float(is_m["cagr"]),
        n_is_days=int(is_m["n_days"]),
        n_oos_days=int(oos_m["n_days"]),
        notes=notes,
    )


def run_independent_oos(
    provider: DataProvider,
    config: BacktestConfig,
    cutoff: str,
) -> BacktestResult:
    """Recomeça no corte com o mesmo capital — teste cego das regras, não da curva."""
    oos_cfg = replace(config, start=str(cutoff), fundamentals_by_date=dict(config.fundamentals_by_date))
    return run_backtest(provider, oos_cfg)


def attach_independent(report: WalkForwardReport, oos: BacktestResult) -> WalkForwardReport:
    m = oos.metrics
    report.independent_oos_return = float(m.get("total_return") or 0.0)
    report.independent_oos_cagr = float(m.get("cagr") or 0.0)
    report.independent_oos_max_dd = float(m.get("max_drawdown") or 0.0)
    report.independent_oos_equity = float(m.get("final_equity") or 0.0)
    extra = report.notes or []
    extra.append(
        "OOS independente: mesma tese, capital novo, só datas depois do corte."
    )
    report.notes = extra
    return report
