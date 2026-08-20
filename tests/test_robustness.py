"""Testes da simulação de Monte Carlo e robustez estatística."""

from __future__ import annotations

import pandas as pd
import pytest

from src.backtest.robustness import run_monte_carlo


def test_monte_carlo_execution():
    # Curva sintética de 100 dias
    dates = pd.date_range("2024-01-01", periods=100, freq="B")
    eq_values = [10_000.0 * (1.0005 ** i) for i in range(100)]
    eq_df = pd.DataFrame({"date": dates, "equity": eq_values})

    mc = run_monte_carlo(eq_df, initial_cash=10_000.0, n_simulations=100, horizon_days=50)

    assert mc.n_simulations == 100
    assert mc.horizon_days == 50
    assert 0.0 <= mc.prob_positive_return <= 1.0
    assert 0.0 <= mc.prob_beat_cdi <= 1.0
    assert mc.percentiles["p10"] <= mc.percentiles["p50"] <= mc.percentiles["p90"]
    assert len(mc.simulated_final_equities) == 100
    assert not mc.simulated_paths.empty
    assert "p50_path" in mc.simulated_paths.columns


def test_monte_carlo_insufficient_history():
    eq_df = pd.DataFrame({"date": ["2024-01-01", "2024-01-02"], "equity": [10000.0, 10010.0]})
    with pytest.raises(ValueError, match="Histórico insuficiente"):
        run_monte_carlo(eq_df)
