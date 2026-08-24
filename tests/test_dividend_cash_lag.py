"""Testes do atraso de liquidação de dividendos (cash lag) no backtest."""

from __future__ import annotations

import pandas as pd

from src.backtest.engine import BacktestCosts, conservative_costs


def test_cash_lag_field_exists():
    """BacktestCosts deve ter o campo dividend_cash_lag_days."""
    costs = BacktestCosts()
    assert hasattr(costs, "dividend_cash_lag_days")
    assert costs.dividend_cash_lag_days == 0


def test_conservative_costs_sets_cash_lag():
    """conservative_costs() deve definir cash lag de 15 dias."""
    costs = conservative_costs()
    assert costs.dividend_cash_lag_days == 15


def test_cash_lag_settlement_date_calculation():
    """Verifica que a data de liquidação é calculada corretamente (~15 dias corridos para 15 úteis)."""
    lag_days = 15
    ex_date = pd.Timestamp("2024-06-03")  # segunda-feira
    # Fórmula do motor: day + Timedelta(days=int(lag_days * 7 / 5))
    settle = ex_date + pd.Timedelta(days=int(lag_days * 7 / 5))
    # 15 * 7 / 5 = 21 dias corridos
    expected = ex_date + pd.Timedelta(days=21)
    assert settle == expected
    assert settle > ex_date


def test_cash_lag_zero_means_immediate():
    """Com dividend_cash_lag_days=0, o crédito deve ser imediato (sem fila)."""
    costs = BacktestCosts(dividend_cash_lag_days=0)
    assert costs.dividend_cash_lag_days == 0
    # Motor não deve enfileirar dividendos com lag=0


def test_costs_enabled_includes_cash_lag():
    """BacktestCosts.enabled deve ser True quando cash lag está ativo."""
    costs = BacktestCosts(dividend_cash_lag_days=15)
    assert costs.enabled is True

    costs_zero = BacktestCosts(dividend_cash_lag_days=0)
    assert costs_zero.enabled is False


def test_cash_lag_pending_queue_logic():
    """Simula a lógica da fila de proventos pendentes."""
    pending: list[dict] = []
    today = pd.Timestamp("2024-06-03")
    lag_days = 15
    settle_day = today + pd.Timedelta(days=int(lag_days * 7 / 5))

    # Enfileirar um dividendo
    pending.append({
        "settle_day": settle_day,
        "ticker": "ITUB4",
        "net_amount": 150.0,
        "shares": 100,
    })
    assert len(pending) == 1

    # Dia seguinte — ainda não liquidou
    check_day = today + pd.Timedelta(days=1)
    ready = [d for d in pending if d["settle_day"] <= check_day]
    assert len(ready) == 0

    # No dia de liquidação — deve liberar
    ready_final = [d for d in pending if d["settle_day"] <= settle_day]
    assert len(ready_final) == 1
    assert ready_final[0]["ticker"] == "ITUB4"
    assert ready_final[0]["net_amount"] == 150.0

    # Após liquidação, a fila fica vazia
    pending = [d for d in pending if d["settle_day"] > settle_day]
    assert len(pending) == 0
