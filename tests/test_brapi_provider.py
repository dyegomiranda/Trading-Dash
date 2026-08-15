"""Pacote: provider brapi (fonte B3 dedicada) — sem rede, com mocks."""

from __future__ import annotations

from unittest import mock

import pandas as pd

from src.data.providers import get_provider
from src.data.providers_brapi import BrapiDataProvider


def _fake_resp(payload: dict):
    resp = mock.Mock()
    resp.raise_for_status.return_value = None
    resp.json.return_value = payload
    return resp


def _quote_payload(ticker: str, **overrides) -> dict:
    payload = {
        "results": [
            {
                "symbol": ticker,
                "longName": f"{ticker} S.A.",
                "regularMarketPrice": 30.0,
                "priceEarnings": 10.0,
                "earningsPerShare": 3.0,
                "marketCap": 4e9,
            }
        ]
    }
    payload["results"][0].update(overrides)
    return payload


def test_name_and_factory():
    assert BrapiDataProvider().name == "brapi"
    assert get_provider("brapi").name == "brapi"


def test_get_fundamentals_maps_quote():
    prov = BrapiDataProvider()
    div_payload = {
        "results": [
            {
                "dividendsData": {
                    "cashDividends": [
                        {
                            "exDate": "2026-08-10T13:00:00.000Z",
                            "paymentDate": "2026-08-20T13:00:00.000Z",
                            "rate": 0.5,
                            "label": "DIVIDENDO",
                        },
                        {
                            "exDate": "2026-02-10T13:00:00.000Z",
                            "paymentDate": "2026-02-20T13:00:00.000Z",
                            "rate": 0.5,
                            "label": "DIVIDENDO",
                        },
                    ]
                }
            }
        ]
    }
    with mock.patch(
        "requests.get",
        side_effect=[
            _fake_resp(_quote_payload("ITUB4")),  # quote
            _fake_resp(div_payload),  # dividends (últimos 12m)
        ],
    ):
        df = prov.get_fundamentals(["ITUB4"])
    assert not df.empty
    row = df.iloc[0]
    assert row["ticker"] == "ITUB4"
    assert row["source"] == "brapi"
    # PE mapeado; ROE honestamente None (plano gratuito não traz)
    assert abs(row["pe"] - 10.0) < 1e-9
    assert row["roe"] is None
    assert row["fcf_positive"] is None or (row["fcf_positive"] != row["fcf_positive"])
    assert row["peg"] is None or (row["peg"] != row["peg"])
    # Dy real: 1.0 em 12m / preço 30
    assert abs(row["dividend_yield"] - (1.0 / 30.0)) < 1e-6


def test_get_fundamentals_handles_errors():
    prov = BrapiDataProvider()
    with mock.patch(
        "requests.get", side_effect=Exception("network down")
    ):
        df = prov.get_fundamentals(["PETR4"])
    assert df.empty
    # Segunda chamada não deve depender de rede (cache), mas com erro fica vazio <== OK


def test_get_price_history_long():
    prov = BrapiDataProvider()
    # brapi devolve "date" como timestamp Unix em segundos e "adjustedClose"
    from datetime import datetime, timezone

    d1 = int(datetime(2024, 1, 2, tzinfo=timezone.utc).timestamp())
    d2 = int(datetime(2024, 1, 3, tzinfo=timezone.utc).timestamp())
    hist_payload = {
        "results": [
            {
                "historicalDataPrice": [
                    {"date": d1, "open": 10, "high": 11, "low": 9, "close": 10.5, "adjustedClose": 9.8, "volume": 1000},
                    {"date": d2, "open": 10.5, "high": 11.5, "low": 10, "close": 11, "adjustedClose": 10.7, "volume": 1200},
                ]
            }
        ]
    }
    with mock.patch("requests.get", return_value=_fake_resp(hist_payload)):
        df = prov.get_price_history(["VALE3"], start="2024-01-01", end="2024-01-31")
    assert not df.empty
    assert set(df.columns) >= {"date", "ticker", "open", "high", "low", "close", "adj_close", "volume"}
    assert set(df["ticker"]) == {"VALE3"}
    assert df["date"].isna().sum() == 0
    # adjustedClose foi usado como adj_close
    assert abs(df.iloc[0]["adj_close"] - 9.8) < 1e-9


def test_get_dividend_history():
    prov = BrapiDataProvider()
    div_payload = {
        "results": [
            {
                "dividendsData": {
                    "cashDividends": [
                        {
                            "lastDatePrior": "2024-03-19T13:00:00.000Z",
                            "paymentDate": "2024-03-20T13:00:00.000Z",
                            "rate": 1.25,
                            "label": "DIVIDENDO",
                        },
                        {
                            "lastDatePrior": "2024-06-19T13:00:00.000Z",
                            "paymentDate": "2024-06-20T13:00:00.000Z",
                            "rate": 1.5,
                            "label": "JCP",
                        },
                    ]
                }
            }
        ]
    }
    with mock.patch("requests.get", return_value=_fake_resp(div_payload)):
        df = prov.get_dividend_history(["BBAS3"], start="2024-01-01", end="2024-12-31")
    assert not df.empty
    assert set(df.columns) == {"date", "ticker", "amount", "label", "ex_date", "payment_date"}
    assert len(df) == 2
    assert abs(df["amount"].sum() - 2.75) < 1e-9
    assert set(df["label"]) == {"DIVIDENDO", "JCP"}
    # lastDatePrior (data-com) → ex = dia seguinte
    assert set(df["ex_date"].dt.strftime("%Y-%m-%d")) == {"2024-03-20", "2024-06-20"}


def test_get_dividend_history_uses_real_ex_date():
    """O que separa quem recebe é a data-ex (exDate), não o pagamento."""
    prov = BrapiDataProvider()
    div_payload = {
        "results": [
            {
                "dividendsData": {
                    "cashDividends": [
                        {
                            "exDate": "2024-03-15T13:00:00.000Z",
                            "paymentDate": "2024-04-10T13:00:00.000Z",
                            "rate": 1.25,
                            "label": "DIVIDENDO",
                        },
                        {
                            "exDate": "2024-05-20T13:00:00.000Z",
                            "paymentDate": "2024-06-20T13:00:00.000Z",
                            "rate": 1.5,
                            "label": "JCP",
                        },
                    ]
                }
            }
        ]
    }
    with mock.patch("requests.get", return_value=_fake_resp(div_payload)):
        # consulta cobre os pagamentos, mas a janela de FILTRO é pela data-ex
        df = prov.get_dividend_history(["BBAS3"], start="2024-03-01", end="2024-04-01")
    # só o provento com ex-date 2024-03-15 cai na janela
    assert len(df) == 1
    assert df.iloc[0]["ex_date"].strftime("%Y-%m-%d") == "2024-03-15"
    assert df.iloc[0]["payment_date"].strftime("%Y-%m-%d") == "2024-04-10"


def test_get_latest_prices_reads_close():
    prov = BrapiDataProvider()
    # get_latest_prices pede os últimos ~14 dias; usa data recente
    from src.utils import utcnow

    from datetime import timezone

    recent = (pd.Timestamp(utcnow()) - pd.Timedelta(days=2)).to_pydatetime().replace(tzinfo=timezone.utc)
    hist_payload = {
        "results": [{"historicalDataPrice": [{"date": int(recent.timestamp()), "close": 42.5}]}]
    }
    with mock.patch("requests.get", return_value=_fake_resp(hist_payload)):
        s = prov.get_latest_prices(["B3SA3"])
    assert not s.empty
    assert abs(s["B3SA3"] - 42.5) < 1e-9


def test_empty_universe_is_empty_frame():
    df = BrapiDataProvider().get_fundamentals([])
    assert isinstance(df, pd.DataFrame)
    assert df.empty