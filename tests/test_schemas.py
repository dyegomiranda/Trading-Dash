"""Pacote: tipagem rígida dos DataFrames — schema e validação de fronteira.

Garante que ``src/data/schemas.py`` normalize o contrato de dados sem quebrar
o app: DataFrame bem-formado passa intacto; colunas ausentes viram NaN;
valores numéricos em formato de texto são convertidos; duplicatas somem; e
um frame vazio vira o schema mínimo (nunca exceção).
"""

from __future__ import annotations

import pandas as pd

from src.data.schemas import (
    FUNDAMENTALS_REQUIRED,
    FUNDAMENTALS_SCHEMA,
    coerce_fundamentals,
    coerce_ohlcv,
)


def _well_formed() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "ticker": "ITUB4",
                "name": "Itaú Unibanco",
                "sector": "Banks",
                "industry": "Banks",
                "price": 32.5,
                "market_cap": 2e11,
                "roe": 0.21,
                "roic": 0.19,
                "roa": 0.03,
                "net_margin": 0.22,
                "ebitda_margin": 0.3,
                "gross_margin": 0.5,
                "dividend_yield": 0.055,
                "payout": 0.45,
                "net_debt_ebitda": 0.5,
                "debt_equity": 0.4,
                "current_ratio": 1.4,
                "interest_coverage": 8.0,
                "pe": 10.2,
                "pb": 1.8,
                "ev_ebitda": 7.0,
                "peg": 1.2,
                "fcf_yield": 0.04,
                "revenue_cagr_5y": 0.08,
                "earnings_cagr_5y": 0.12,
                "dividend_cagr_5y": 0.06,
                "years_paying_dividend": 12,
                "fcf_positive": True,
                "currency": "BRL",
                "as_of": "2026-01-01",
                "source": "demo",
                "data_quality": "synthetic_fundamentals",
                "meta_source": "reference",
                "ticker_status": "ok",
            }
        ]
    )


def test_schema_well_formed_passes_through():
    df = coerce_fundamentals(_well_formed())
    assert len(df) == 1
    assert df.loc[0, "ticker"] == "ITUB4"
    assert df.loc[0, "roe"] == 0.21


def test_missing_columns_filled_nan():
    df = coerce_fundamentals(pd.DataFrame({"ticker": ["PETR4"], "price": [25.0]}))
    assert "roe" in df.columns
    assert "dividend_yield" in df.columns
    assert pd.isna(df.loc[0, "roe"])


def test_numeric_strings_coerced():
    df = coerce_fundamentals(
        pd.DataFrame({"ticker": ["VALE3"], "price": ["60,5"], "roe": ["0.15"]})
    )
    # "60,5" não é decimal válido (vírgula) → NaN; "0.15" vira float
    assert pd.isna(df.loc[0, "price"]) or df.loc[0, "price"] == 60.5
    assert df.loc[0, "roe"] == 0.15


def test_boolean_coerced():
    df = coerce_fundamentals(pd.DataFrame({"ticker": ["WEGE3"], "fcf_positive": [1]}))
    assert bool(df.loc[0, "fcf_positive"]) is True


def test_duplicate_columns_deduped():
    # coluna duplicada só acontece de fato com MultiIndex/concat, não dict literal
    raw = pd.concat(
        [
            pd.DataFrame({"ticker": ["ITUB4"], "roe": [0.1]}),
            pd.DataFrame({"roe": [0.2]}),
        ],
        axis=1,
    )
    assert raw.columns.duplicated().any()  # pré-condição: existem duplicatas
    df = coerce_fundamentals(raw)
    assert not df.columns.duplicated().any()


def test_none_becomes_empty_schema_frame():
    df = coerce_fundamentals(None)
    assert isinstance(df, pd.DataFrame)
    assert df.empty


def test_empty_frame_becomes_schema_columns():
    df = coerce_fundamentals(pd.DataFrame())
    assert set(df.columns) == {k for k, _ in FUNDAMENTALS_SCHEMA}


def test_required_columns_are_present_in_schema():
    schema_cols = {k for k, _ in FUNDAMENTALS_SCHEMA}
    assert set(FUNDAMENTALS_REQUIRED) <= schema_cols


def test_ohlcv_coerces_dtypes():
    df = coerce_ohlcv(
        pd.DataFrame(
            {
                "date": ["2026-01-02", "2026-01-03"],
                "ticker": ["ITUB4", "ITUB4"],
                "open": [30.0, "31.0"],
                "high": [31.0, "32.0"],
                "low": [29.5, 30.5],
                "close": [30.8, "31.5"],
                "adj_close": [30.0, 30.7],
                "volume": [1000, 2000],
            }
        )
    )
    assert len(df) == 2
    assert pd.api.types.is_datetime64_any_dtype(df["date"])
    assert pd.api.types.is_numeric_dtype(df["close"])


def test_ohlcv_empty_keeps_schema_columns():
    df = coerce_ohlcv(pd.DataFrame())
    assert list(df.columns) == [
        "date",
        "ticker",
        "open",
        "high",
        "low",
        "close",
        "adj_close",
        "volume",
    ]