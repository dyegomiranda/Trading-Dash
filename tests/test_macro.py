"""Pacote: regime macro (Selic/IPCA) e inclinação setorial — sem rede."""

from __future__ import annotations

from unittest import mock

import pandas as pd

from src.thesis.macro import (
    apply_sector_tilt,
    classify_regime,
    fetch_macro_state,
    macro_tilt_from_override,
    sector_tilt,
    sector_tilt_from_override,
)


def _state_dict():
    # selic_aa e ipca_12m já vêm normalizados em PERCENTUAL anual
    # (ex.: selic_aa 5.5 = 5,5% a.a.; ipca_12m 3.0 = 3,0% em 12m).
    return {
        "selic_aa": 5.5,
        "ipca_12m": 3.0,
        "real_rate": 2.43,
        "available": True,
        "as_of": "2026-08-01",
        "error": None,
    }


def test_classify_regime_restrictive_high_real():
    assert classify_regime(6.0) == "restrictive"
    assert classify_regime(4.0) == "restrictive"
    assert classify_regime(2.5) == "cautious"
    assert classify_regime(0.5) == "expansionary"
    assert classify_regime(-1.0) == "expansionary"
    assert classify_regime(None) == "cautious"


def test_sector_tilt_restrictive_boosts_defensive():
    t = sector_tilt("restrictive")
    assert t["Utilities"] > 1.0
    assert t["Technology"] < 1.0  # crescimento perde peso em juros altos
    assert t["Consumer Cyclical"] < 1.0


def test_sector_tilt_expansionary_boosts_growth():
    t = sector_tilt("expansionary")
    assert t["Technology"] > 1.0  # crescimento favorecido em juros baixos
    assert t["Utilities"] < 1.0  # defensiva perde um pouco de peso relativo


def test_sector_tilt_cautious_neutral():
    t = sector_tilt("cautious")
    assert all(v == 1.0 for v in t.values())


def test_apply_sector_tilt_renormalizes():
    df = pd.DataFrame(
        {
            "ticker": ["A", "B", "C"],
            "sector": ["Utilities", "Technology", "Utilities"],
            "target_weight": [0.3, 0.4, 0.3],
        }
    )
    tilt = {"Utilities": 1.12, "Technology": 0.93}
    out = apply_sector_tilt(df, tilt)
    assert abs(out["target_weight"].sum() - 1.0) < 1e-9
    # Utilities ganhou espaço relativo vs tecnologia
    utils_before = 0.6
    tech_before = 0.4
    utils_after = out.loc[out["sector"] == "Utilities", "target_weight"].sum()
    tech_after = out.loc[out["sector"] == "Technology", "target_weight"].sum()
    assert utils_after > utils_before
    assert tech_after < tech_before


def test_apply_sector_tilt_no_op_without_tilt():
    df = pd.DataFrame({"ticker": ["A"], "sector": ["X"], "target_weight": [1.0]})
    assert apply_sector_tilt(df, {}) is df
    # tilt que não cobre nenhum setor presente → pesos inalterados
    out = apply_sector_tilt(df, {"Y": 2.0})
    assert out["target_weight"].iloc[0] == 1.0


def test_apply_sector_tilt_ignores_missing_sector_col():
    df = pd.DataFrame({"ticker": ["A"], "target_weight": [1.0]})
    out = apply_sector_tilt(df, {"Utilities": 2.0})
    assert out["target_weight"].iloc[0] == 1.0


@mock.patch(
    "src.thesis.macro.fetch_macro_state",
    return_value={**_state_dict(), "real_rate": 2.43},
)
def test_sector_tilt_from_override_auto_cautious(mock_state):
    regime, tilt, info = sector_tilt_from_override("auto")
    assert regime == "cautious"
    assert all(v == 1.0 for v in tilt.values())
    assert info["available"] is True


@mock.patch(
    "src.thesis.macro.fetch_macro_state",
    return_value={**_state_dict(), "real_rate": 6.0},
)
def test_sector_tilt_from_override_auto_restrictive(mock_state):
    regime, tilt, info = sector_tilt_from_override("auto")
    assert regime == "restrictive"
    assert tilt["Utilities"] > 1.0
    assert info["available"] is True


def test_macro_tilt_from_override_off_is_none():
    assert macro_tilt_from_override("off") is None
    assert macro_tilt_from_override("") is None
    assert macro_tilt_from_override(None) is None


def test_macro_tilt_from_override_manual():
    t = macro_tilt_from_override("restrictive")
    assert t is not None
    assert t["Utilities"] > 1.0


def test_fetch_macro_state_normalizes_units():
    """SGS 432 (meta Selic) já é % a.a.; SGS 433 (IPCA) é % mensal (12 prints)."""
    idx = pd.date_range("2025-09-01", periods=12, freq="MS")
    selic = pd.Series([14.75], index=[pd.Timestamp("2026-08-14")])
    ipca = pd.Series([0.30] * 12, index=idx)
    with (
        mock.patch("src.thesis.macro.utcnow", return_value=pd.Timestamp("2026-08-14")),
        mock.patch(
            "src.thesis.macro._fetch_bcb_series",
            side_effect=lambda code, *a, **k: selic if code == 432 else ipca,
        ),
    ):
        st = fetch_macro_state()
    assert abs(st["selic_aa"] - 14.75) < 1e-6
    assert 2.0 < float(st["ipca_12m"]) < 5.0
    assert st["available"] is True