"""Módulo de Análise de Robustez e Simulação de Monte Carlo.

Avalia a estabilidade estatística da tese através de:
1. Simulação estocástica de Monte Carlo (bootstrap de retornos diários).
2. Faixas de probabilidade e intervalos de confiança (p10, p50, p90).
3. Probabilidade de superar benchmarks (CDI / Ibovespa).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class MonteCarloResult:
    n_simulations: int
    horizon_days: int
    initial_cash: float
    percentiles: dict[str, float]  # p10, p25, p50, p75, p90
    simulated_final_equities: list[float]
    simulated_total_returns: list[float]
    simulated_max_drawdowns: list[float]
    prob_positive_return: float
    prob_beat_cdi: float
    simulated_paths: pd.DataFrame  # Sample paths for chart plotting


def run_monte_carlo(
    equity_curve: pd.DataFrame,
    initial_cash: float = 100_000.0,
    n_simulations: int = 250,
    horizon_days: int = 252,
    cdi_annual_rate: float = 0.115,
    seed: int | None = 42,
) -> MonteCarloResult:
    """Executa simulação de Monte Carlo via bootstrap de retornos históricos diários.

    Gera caminhos estocásticos de evolução patrimonial para estimar a faixa
    probabilística de resultados no mundo real.
    """
    if equity_curve is None or equity_curve.empty or "equity" not in equity_curve.columns:
        raise ValueError("Curva de patrimônio inválida para simulação de Monte Carlo.")

    eq = pd.to_numeric(equity_curve["equity"], errors="coerce").dropna()
    if len(eq) < 10:
        raise ValueError("Histórico insuficiente para Monte Carlo (mínimo 10 pregões).")

    daily_rets = eq.pct_change().dropna().to_numpy()
    if len(daily_rets) == 0:
        raise ValueError("Sem retornos válidos calculáveis.")

    rng = np.random.default_rng(seed)
    
    # Gerar matriz de retornos sorteados: shape (horizon_days, n_simulations)
    sampled_indices = rng.choice(len(daily_rets), size=(horizon_days, n_simulations), replace=True)
    sampled_returns = daily_rets[sampled_indices]

    # Trajetórias cumulativas
    growth_factors = 1.0 + sampled_returns
    cum_growth = np.vstack([np.ones((1, n_simulations)), np.cumprod(growth_factors, axis=0)])
    simulated_paths_matrix = initial_cash * cum_growth

    final_equities = simulated_paths_matrix[-1, :]
    total_returns = (final_equities / initial_cash) - 1.0

    # Drawdowns simulados
    running_max = np.maximum.accumulate(simulated_paths_matrix, axis=0)
    drawdowns = (simulated_paths_matrix - running_max) / running_max
    max_drawdowns = np.min(drawdowns, axis=0)

    # Benchmark CDI no mesmo horizonte
    cdi_daily = (1.0 + cdi_annual_rate) ** (1.0 / 252.0) - 1.0
    cdi_terminal_return = ((1.0 + cdi_daily) ** horizon_days) - 1.0

    prob_positive = float(np.mean(total_returns > 0))
    prob_beat_cdi = float(np.mean(total_returns > cdi_terminal_return))

    percentiles = {
        "p10": float(np.percentile(total_returns, 10)),
        "p25": float(np.percentile(total_returns, 25)),
        "p50": float(np.percentile(total_returns, 50)),
        "p75": float(np.percentile(total_returns, 75)),
        "p90": float(np.percentile(total_returns, 90)),
        "p10_equity": float(np.percentile(final_equities, 10)),
        "p50_equity": float(np.percentile(final_equities, 50)),
        "p90_equity": float(np.percentile(final_equities, 90)),
        "mean_max_drawdown": float(np.mean(max_drawdowns)),
        "p90_max_drawdown": float(np.percentile(max_drawdowns, 10)),  # pior 10%
    }

    # Amostra de caminhos para plotagem limpa (ex: 30 caminhos)
    n_sample_plot = min(30, n_simulations)
    sample_df = pd.DataFrame(
        simulated_paths_matrix[:, :n_sample_plot],
        columns=[f"sim_{i+1}" for i in range(n_sample_plot)],
    )
    sample_df["day"] = np.arange(horizon_days + 1)
    sample_df["p50_path"] = np.percentile(simulated_paths_matrix, 50, axis=1)
    sample_df["p10_path"] = np.percentile(simulated_paths_matrix, 10, axis=1)
    sample_df["p90_path"] = np.percentile(simulated_paths_matrix, 90, axis=1)

    return MonteCarloResult(
        n_simulations=n_simulations,
        horizon_days=horizon_days,
        initial_cash=initial_cash,
        percentiles=percentiles,
        simulated_final_equities=final_equities.tolist(),
        simulated_total_returns=total_returns.tolist(),
        simulated_max_drawdowns=max_drawdowns.tolist(),
        prob_positive_return=prob_positive,
        prob_beat_cdi=prob_beat_cdi,
        simulated_paths=sample_df,
    )
