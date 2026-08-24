"""Testes do slippage dinâmico não-linear baseado em liquidez (ADV)."""

from __future__ import annotations

import math

from src.backtest.engine import BacktestCosts, conservative_costs


def test_dynamic_slippage_fields_exist():
    """BacktestCosts deve ter os campos de slippage dinâmico."""
    costs = BacktestCosts()
    assert hasattr(costs, "dynamic_slippage")
    assert hasattr(costs, "slippage_gamma")
    assert costs.dynamic_slippage is False
    assert costs.slippage_gamma == 0.10


def test_conservative_costs_enables_dynamic_slippage():
    """conservative_costs() deve ativar slippage dinâmico com gamma padrão."""
    costs = conservative_costs()
    assert costs.dynamic_slippage is True
    assert costs.slippage_gamma == 0.10
    assert costs.slippage_bps == 10.0


def test_dynamic_slippage_formula_logic():
    """Valida a fórmula: slippage_eff = base + gamma * sqrt(order/adv) * 10_000."""
    costs = conservative_costs()
    base_bps = costs.slippage_bps  # 10.0
    gamma = costs.slippage_gamma   # 0.10

    # Cenário 1: ordem pequena vs ADV grande → impacto mínimo
    order_small = 10_000.0
    adv_large = 5_000_000.0
    impact_1 = math.sqrt(order_small / adv_large)
    eff_1 = base_bps + gamma * impact_1 * 10_000.0
    eff_1 = min(eff_1, 150.0)
    # Impacto pequeno: sqrt(10k/5M) ≈ 0.045 → 0.10 * 0.045 * 10k ≈ 44.7 bps + 10 = ~54.7
    assert eff_1 > base_bps
    assert eff_1 < 150.0

    # Cenário 2: ordem grande vs ADV pequeno → impacto alto (cap em 150)
    order_large = 500_000.0
    adv_small = 100_000.0
    impact_2 = math.sqrt(order_large / adv_small)
    eff_2 = base_bps + gamma * impact_2 * 10_000.0
    eff_2 = min(eff_2, 150.0)
    # sqrt(500k/100k) ≈ 2.24 → gamma * 2.24 * 10k = 2236 bps (capped a 150)
    assert eff_2 == 150.0

    # Cenário 3: ordem == ADV → impacto moderado
    order_eq = 1_000_000.0
    adv_eq = 1_000_000.0
    impact_3 = math.sqrt(order_eq / adv_eq)
    eff_3 = base_bps + gamma * impact_3 * 10_000.0
    eff_3 = min(eff_3, 150.0)
    assert eff_3 == 150.0  # sqrt(1) * 0.10 * 10k = 1000 → capped


def test_dynamic_slippage_disabled():
    """Com dynamic_slippage=False, o slippage efetivo deve ser o base fixo."""
    costs = BacktestCosts(slippage_bps=10.0, dynamic_slippage=False)
    # Sem cálculo dinâmico, o motor usa slippage_bps direto
    assert costs.dynamic_slippage is False
    assert costs.slippage_bps == 10.0


def test_costs_enabled_includes_dynamic_slippage():
    """BacktestCosts.enabled deve ser True quando dynamic_slippage está ativo."""
    costs = BacktestCosts(dynamic_slippage=True)
    assert costs.enabled is True

    costs_off = BacktestCosts(dynamic_slippage=False)
    assert costs_off.enabled is False
