"""Checagens CVM/cadastro: lucro/caixa, setor, governança — sem nota 0–10."""

from __future__ import annotations

import pandas as pd

from src.data.providers import YFinanceDataProvider, _cadastro_only_row
from src.data.reference import control_label, listing_segment, tag_along_pct
from src.thesis.checks import build_quality_checks


def test_cadastro_only_row_does_not_invent_fundamentals():
    row = _cadastro_only_row("ITUB4")
    assert row["ticker"] == "ITUB4"
    assert row["roe"] is None
    assert row["dividend_yield"] is None
    assert row["price"] == 0.0
    assert row["data_quality"] == "unavailable"
    assert "Renner" not in str(row["name"])  # não pega ticker errado


def test_yfinance_fundamentals_do_not_call_demo(monkeypatch):
    import inspect

    src = inspect.getsource(YFinanceDataProvider.get_fundamentals)
    assert "DemoDataProvider" not in src
    assert "reference_enriched" not in src


def test_listing_segment_from_b3_name_suffix():
    assert listing_segment("AALR3") == "Novo Mercado"
    assert tag_along_pct("AALR3") == 1.0
    assert listing_segment("ABCB4") == "Nível 2"
    assert tag_along_pct("ABCB4") == 1.0


def test_control_label_curated_state_owned():
    assert control_label("PETR4") == "estatal federal"
    assert control_label("BBAS3") == "estatal federal"
    assert control_label("ITUB4") is None


def test_checks_profit_streak_and_fcf(monkeypatch):
    snaps = {}
    for year, lucro, fcf in (
        (2020, 100.0, 90.0),
        (2021, 110.0, 95.0),
        (2022, 120.0, 100.0),
        (2023, 130.0, 110.0),
        (2024, 140.0, 120.0),
    ):
        snaps[f"{year}-12-31"] = pd.DataFrame(
            [
                {
                    "ticker": "FAKE3",
                    "lucro": lucro,
                    "fcf": fcf,
                    "source": "cvm_dfp",
                    "as_of": f"{year}-12-31",
                }
            ]
        )

    meta = {"ticker": "FAKE3", "name": "FAKE ON NM", "sector": "Utilities"}
    monkeypatch.setattr("src.thesis.checks.load_pit_fundamentals", lambda: snaps)
    monkeypatch.setattr("src.thesis.checks.get_pit_origin", lambda: "cvm_dfp_itr")
    monkeypatch.setattr("src.thesis.checks.get_ticker_meta", lambda t: meta)
    monkeypatch.setattr("src.data.reference.get_ticker_meta", lambda t: meta)

    q = build_quality_checks("FAKE3")
    by_id = {i.id: i for i in q.items}
    assert by_id["lucro_caixa"].status == "ok"
    assert "5 anos" in by_id["lucro_caixa"].detail
    assert "FCF/lucro" in by_id["lucro_caixa"].detail
    assert by_id["setor"].status == "ok"
    assert by_id["governanca"].status == "ok"
    assert q.n_ok == 3


def test_checks_loss_year_is_warning(monkeypatch):
    snaps = {
        "2022-12-31": pd.DataFrame(
            [{"ticker": "LOSS3", "lucro": 50.0, "fcf": 40.0, "source": "cvm_dfp"}]
        ),
        "2023-12-31": pd.DataFrame(
            [{"ticker": "LOSS3", "lucro": 40.0, "fcf": 10.0, "source": "cvm_dfp"}]
        ),
        "2024-12-31": pd.DataFrame(
            [{"ticker": "LOSS3", "lucro": -10.0, "fcf": 5.0, "source": "cvm_dfp"}]
        ),
    }
    monkeypatch.setattr("src.thesis.checks.load_pit_fundamentals", lambda: snaps)
    monkeypatch.setattr("src.thesis.checks.get_pit_origin", lambda: "cvm_dfp_itr")
    q = build_quality_checks("LOSS3")
    lucro = next(i for i in q.items if i.id == "lucro_caixa")
    assert lucro.status == "warn"
    assert "prejuízo" in lucro.detail.lower()


def test_checks_unknown_without_pit(monkeypatch):
    monkeypatch.setattr("src.thesis.checks.load_pit_fundamentals", lambda: {})
    monkeypatch.setattr("src.thesis.checks.get_pit_origin", lambda: "cvm_dfp_itr")
    q = build_quality_checks("XXXX3")
    lucro = next(i for i in q.items if i.id == "lucro_caixa")
    assert lucro.status == "unknown"
    assert q.n_ok <= 1
