"""Testes dos cenários de estresse histórico pré-configurados."""

from __future__ import annotations

from datetime import date

from src.backtest.engine import STRESS_SCENARIOS


def test_stress_scenarios_exist():
    """STRESS_SCENARIOS deve conter os 4 cenários pré-definidos."""
    assert len(STRESS_SCENARIOS) >= 4
    expected_keys = {"corona_crash", "selic_spike", "recovery_rally", "full_cycle"}
    assert expected_keys.issubset(set(STRESS_SCENARIOS.keys()))


def test_each_scenario_has_required_fields():
    """Cada cenário deve ter title, desc, start e end."""
    for key, scenario in STRESS_SCENARIOS.items():
        assert "title" in scenario, f"{key} falta 'title'"
        assert "desc" in scenario, f"{key} falta 'desc'"
        assert "start" in scenario, f"{key} falta 'start'"
        assert "end" in scenario, f"{key} falta 'end'"


def test_scenario_dates_are_valid():
    """As datas start e end devem ser parsáveis e start < end."""
    for key, scenario in STRESS_SCENARIOS.items():
        start = date.fromisoformat(scenario["start"])
        end = date.fromisoformat(scenario["end"])
        assert start < end, f"{key}: start ({start}) deve ser anterior a end ({end})"


def test_corona_crash_period():
    """Corona Crash deve cobrir o período da pandemia em 2020."""
    sc = STRESS_SCENARIOS["corona_crash"]
    start = date.fromisoformat(sc["start"])
    end = date.fromisoformat(sc["end"])
    assert start.year == 2020
    assert end.year == 2020
    # Deve cobrir pelo menos março 2020 (o pior mês)
    assert start <= date(2020, 3, 1)
    assert end >= date(2020, 6, 30)


def test_selic_spike_period():
    """Choque de Juros deve cobrir 2021-2022."""
    sc = STRESS_SCENARIOS["selic_spike"]
    start = date.fromisoformat(sc["start"])
    end = date.fromisoformat(sc["end"])
    assert start.year == 2021
    assert end.year == 2022


def test_recovery_rally_period():
    """Rally deve cobrir 2023-2024."""
    sc = STRESS_SCENARIOS["recovery_rally"]
    start = date.fromisoformat(sc["start"])
    end = date.fromisoformat(sc["end"])
    assert start.year == 2023
    assert end.year == 2024


def test_full_cycle_spans_multiple_years():
    """Ciclo Completo deve cobrir pelo menos 5 anos."""
    sc = STRESS_SCENARIOS["full_cycle"]
    start = date.fromisoformat(sc["start"])
    end = date.fromisoformat(sc["end"])
    assert (end - start).days >= 365 * 5


def test_scenario_titles_are_descriptive():
    """Títulos devem ter comprimento razoável e conter emojis ou texto descritivo."""
    for key, scenario in STRESS_SCENARIOS.items():
        title = scenario["title"]
        assert len(title) >= 10, f"{key}: título muito curto"
        desc = scenario["desc"]
        assert len(desc) >= 20, f"{key}: descrição muito curta"
