"""Walk-forward simples: treino (in-sample) vs teste cego (out-of-sample).

Não otimiza parâmetros. Parte o período do ensaio em dois pedaços no tempo
e mede se o resultado do segundo é parecido com o do primeiro. Isso não
“prova” a tese — só deixa o overfitting visível.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from itertools import product
import math
from typing import Any

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


@dataclass
class GridSearchResult:
    """Resultado de um grid search no walk-forward analysis."""
    best_params: dict[str, Any]
    best_sharpe: float
    best_wf_report: WalkForwardReport
    all_results: list[tuple[dict[str, Any], float, WalkForwardReport]]


def _equity_series(result: BacktestResult) -> pd.Series:
    eq = result.equity_curve.copy()
    if "date" in eq.columns:
        eq["date"] = pd.to_datetime(eq["date"])
        eq = eq.set_index("date")
    s = pd.to_numeric(eq["equity"], errors="coerce").dropna().sort_index()
    return s


def _calculate_sharpe_ratio(equity_curve: pd.DataFrame, risk_free_rate: float = 0.0) -> float:
    """
    Calcula o Sharpe Ratio anualizado.

    Args:
        equity_curve: DataFrame com colunas 'date' e 'equity'
        risk_free_rate: taxa livre de risco anualizada (padrão: 0.0)

    Returns:
        Sharpe Ratio anualizado ou -inf se não houver dados suficientes
    """
    if equity_curve is None or equity_curve.empty or "equity" not in equity_curve.columns:
        return -math.inf

    equity = pd.to_numeric(equity_curve["equity"], errors="coerce")
    if len(equity) < 2:
        return -math.inf

    # Calcular retornos diários
    daily_returns = equity.pct_change().dropna()
    if len(daily_returns) == 0:
        return -math.inf

    # Estatísticas anualizadas (252 pregões úteis por ano)
    annual_return = daily_returns.mean() * 252
    annual_volatility = daily_returns.std() * math.sqrt(252)

    if annual_volatility == 0:
        return -math.inf if annual_return <= risk_free_rate else math.inf

    sharpe = (annual_return - risk_free_rate) / annual_volatility
    return sharpe


def _calculate_cagr(equity: pd.Series) -> float:
    """Calcula o CAGR (Compound Annual Growth Rate)."""
    if len(equity) < 2:
        return 0.0
    start, end = float(equity.iloc[0]), float(equity.iloc[-1])
    if start <= 0 or end <= 0:
        return 0.0
    days = (equity.index[-1] - equity.index[0]).days
    if days <= 0:
        return 0.0
    years = days / 365.25
    return float((end / start) ** (1 / years) - 1)


def _calculate_annual_volatility(equity_curve: pd.DataFrame) -> float:
    """Calcula a volatilidade anualizada."""
    if equity_curve is None or equity_curve.empty or "equity" not in equity_curve.columns:
        return 0.0

    equity = pd.to_numeric(equity_curve["equity"], errors="coerce")
    if len(equity) < 2:
        return 0.0

    daily_returns = equity.pct_change().dropna()
    if len(daily_returns) == 0:
        return 0.0

    return float(daily_returns.std() * math.sqrt(252))


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


def grid_search_walk_forward(
    provider: DataProvider,
    base_config: BacktestConfig,
    param_grid: dict[str, list[Any]],
    *,
    fraction: float = 0.70,
    max_combinations: int | None = None,
    risk_free_rate: float = 0.115,  # CDI anual padrão
) -> GridSearchResult:
    """
    Executa um grid search de parâmetros no walk-forward analysis.

    Args:
        provider: Provedor de dados
        base_config: Configuração básica do backtest (será sobrescrita pelos parâmetros da grade)
        param_grid: Dicionário onde chaves são nomes dos parâmetros e valores são listas de valores a testar
        fraction: Fração do período para usar como in-sample (padrão: 0.70)
        max_combinations: Número máximo de combinações a testar (None = todas)
        risk_free_rate: Taxa livre de risco anualizada para cálculo do Sharpe Ratio

    Returns:
        GridSearchResult com os melhores parâmetros encontrados e todos os resultados

    Example:
        param_grid = {
            "top_n": [8, 12, 15],
            "min_score": [50, 55, 60],
            "rebalance": ["M", "Q"],
            "core_weight": [0.6, 0.7, 0.8]
        }
    """
    if not param_grid:
        # Se não há grade para pesquisar, executa walk-forward normal com a config base
        result = run_backtest(provider, base_config)
        wf_report = evaluate_walk_forward(result, fraction=fraction)
        sharpe = _calculate_sharpe_ratio(result.equity_curve, risk_free_rate)
        return GridSearchResult(
            best_params={},
            best_sharpe=sharpe,
            best_wf_report=wf_report,
            all_results=[({}, sharpe, wf_report)]
        )

    # Gerar todas as combinações de parâmetros
    param_names = list(param_grid.keys())
    param_values = list(param_grid.values())
    all_combinations = list(product(*param_values))

    # Limitar número de combinações se especificado
    if max_combinations is not None and len(all_combinations) > max_combinations:
        # Amostragem uniforme para não favorecer combinações específicas
        step = len(all_combinations) // max_combinations
        if step < 1:
            step = 1
        all_combinations = all_combinations[::step][:max_combinations]

    best_sharpe = -math.inf
    best_params = {}
    best_wf_report = None
    all_results = []

    for i, combination in enumerate(all_combinations):
        # Criar configuração atual
        config_dict = base_config.__dict__.copy()

        # Sobrescrever parâmetros da grade
        for name, value in zip(param_names, combination):
            config_dict[name] = value

        # Criar nova configuração
        try:
            config = BacktestConfig(**config_dict)
        except Exception:
            # Se a configuração for inválida, pular esta combinação
            continue

        # Executar backtest
        try:
            result = run_backtest(provider, config)
        except Exception:
            # Se o backtest falhar, atribuir Sharpe muito baixo
            sharpe = -math.inf
            wf_report = None
        else:
            wf_report = evaluate_walk_forward(result, fraction=fraction)
            # Escolhe no TREINO (IS). Usar a curva inteira vazaria o teste.
            sharpe = float(wf_report.is_cagr) if wf_report is not None else -math.inf

        # Armazenar resultado
        result_tuple = (dict(zip(param_names, combination)), sharpe, wf_report)
        all_results.append(result_tuple)

        # Atualizar melhor resultado
        if sharpe > best_sharpe:
            best_sharpe = sharpe
            best_params = dict(zip(param_names, combination))
            best_wf_report = wf_report

    # Se nenhum resultado válido foi encontrado, retornar resultado padrão
    if best_wf_report is None and all_results:
        # Pegar o primeiro resultado válido ou o último se nenhum for válido
        valid_results = [r for r in all_results if r[1] > -math.inf]
        if valid_results:
            _, best_sharpe, best_wf_report = valid_results[0]
            best_params = valid_results[0][0]
        else:
            _, best_sharpe, best_wf_report = all_results[-1]
            best_params = all_results[-1][0]

    return GridSearchResult(
        best_params=best_params,
        best_sharpe=best_sharpe,
        best_wf_report=best_wf_report,
        all_results=all_results
    )