"""Contrato de dados — schemas rígidos para os DataFrames do app.

Todas as fontes (demo, yfinance, brapi) e consumidores (scoring, backtest)
trocam DataFrames com **o mesmo contrato de colunas**. Este módulo é a
fronteira única de validação/coerção:

- ``FUNDAMENTALS_SCHEMA`` — colunas que um snapshot fundamentalista pode ter
  (``(nome, tipo)``; ``Any`` = aceita qualquer valor).
- ``FUNDAMENTALS_REQUIRED`` — colunas sem as quais o scoring não faz sentido
  (mesmo assim, não derrubamos o app por falta delas).
- ``coerce_fundamentals`` — garante que um DataFrame de fundamentals respeite
  o contrato: remove duplicadas, preenche colunas ausentes com ``NaN``, força
  o dtype numérico nas colunas conhecidas. **Nunca levanta exceção** (best
  effort; a violação vira evento de observabilidade).
- ``coerce_ohlcv`` — idem para histórico de preços (formato longo).

Filosofia: validar NA fronteira (choke point) em vez de espalhar `if col in df`
por todo o código. A violação é registrada em ``data/logs`` (via monitoring)
para diagnóstico, sem quebrar a experiência.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

# Campos que cada linha de fundamentals pode ter e o dtype esperado.
FUNDAMENTALS_SCHEMA: tuple[tuple[str, Any], ...] = (
    ("ticker", str),
    ("name", str),
    ("sector", str),
    ("industry", str),
    ("price", float),
    ("market_cap", float),
    ("roe", float),
    ("roic", float),
    ("roa", float),
    ("net_margin", float),
    ("ebitda_margin", float),
    ("gross_margin", float),
    ("dividend_yield", float),
    ("payout", float),
    ("net_debt_ebitda", float),
    ("debt_equity", float),
    ("current_ratio", float),
    ("interest_coverage", float),
    ("pe", float),
    ("pb", float),
    ("ev_ebitda", float),
    ("peg", float),
    ("fcf_yield", float),
    ("revenue_cagr_5y", float),
    ("earnings_cagr_5y", float),
    ("dividend_cagr_5y", float),
    ("years_paying_dividend", float),
    ("fcf_positive", bool),
    ("currency", str),
    ("as_of", str),
    ("source", str),
    ("data_quality", str),
    ("meta_source", str),
    ("ticker_status", str),
)

# Mínimo para scoring significativo (não é gate — só reporta).
FUNDAMENTALS_REQUIRED: tuple[str, ...] = (
    "ticker",
    "name",
    "sector",
    "price",
    "roe",
    "dividend_yield",
)

# OHLCV longo: date, ticker, open, high, low, close, adj_close, volume
_OHLCV_COLS: tuple[str, ...] = (
    "date",
    "ticker",
    "open",
    "high",
    "low",
    "close",
    "adj_close",
    "volume",
)

# Mapeia nome → dtype para coerção numérica
_NUMERIC_COLS: dict[str, Any] = {name: kind for name, kind in FUNDAMENTALS_SCHEMA if kind is float}
_BOOL_COLS: dict[str, Any] = {name: kind for name, kind in FUNDAMENTALS_SCHEMA if kind is bool}


_OHLCV_REQUIRED: tuple[str, ...] = ("date", "ticker", "close")


def _schema_report(
    df: pd.DataFrame,
    op: str = "schema",
    *,
    required: tuple[str, ...] = FUNDAMENTALS_REQUIRED,
    known: set[str] | None = None,
) -> None:
    """Registra violações de schema na observabilidade (best effort, silencioso)."""
    columns = set(df.columns)
    missing_required = [c for c in required if c not in columns]
    allowed = known if known is not None else {k for k, _ in FUNDAMENTALS_SCHEMA}
    unexpected = [c for c in columns if c not in allowed]
    try:
        from src.monitoring import write_event

        write_event(
            {
                "op": op,
                "n_rows": int(len(df)),
                "n_cols": int(df.shape[1]),
                "missing_required": missing_required,
                "unexpected_cols": unexpected[:10],
            }
        )
    except Exception:
        pass


def coerce_fundamentals(df: pd.DataFrame, *, op: str = "schema_fundamentals") -> pd.DataFrame:
    """Normaliza um DataFrame de fundamentals para o contrato.

    - remove colunas duplicadas (mantém última)
    - preenche colunas do schema ausentes com NaN
    - converte colunas numéricas/bool para o dtype correto (erros → NaN)
    - NÃO remove colunas extras (demoraria a validar uso futuro)
    - NÃO levanta exceção: violações viram evento de observabilidade
    """
    if df is None:
        return pd.DataFrame()
    if df.empty:
        df = pd.DataFrame(columns=[k for k, _ in FUNDAMENTALS_SCHEMA])
    else:
        df = df.copy()
        if df.columns.duplicated().any():
            df = df.loc[:, ~df.columns.duplicated(keep="last")].copy()

        # Colunas ausentes do schema → preenche com NaN
        for col, _kind in FUNDAMENTALS_SCHEMA:
            if col not in df.columns:
                df[col] = pd.NA

        # Coerção numérica (erros de conversão → NaN, nunca quebra)
        for col in _NUMERIC_COLS:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        for col in _BOOL_COLS:
            if col in df.columns:
                df[col] = df[col].map(lambda v: v if pd.isna(v) else bool(v)).astype("object")

        # ticker/name/sector viram str quando disponíveis (NaN preserva)
        for col in ("ticker", "name", "sector"):
            if col in df.columns:
                df[col] = df[col].map(
                    lambda v: str(v) if pd.notna(v) else v
                )

    _schema_report(df, op=op)
    return df


def coerce_ohlcv(df: pd.DataFrame, *, op: str = "schema_ohlcv") -> pd.DataFrame:
    """Normaliza DataFrame de histórico (formato longo) para OHLCV padrão."""
    if df is None:
        return pd.DataFrame()
    if df.empty:
        return pd.DataFrame(columns=list(_OHLCV_COLS))
    out = df.copy()
    if out.columns.duplicated().any():
        out = out.loc[:, ~out.columns.duplicated(keep="last")].copy()
    if "date" in out.columns:
        out["date"] = pd.to_datetime(out["date"], errors="coerce")
    for col in ("open", "high", "low", "close", "adj_close"):
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")
    if "volume" in out.columns:
        out["volume"] = pd.to_numeric(out["volume"], errors="coerce")
    if "ticker" in out.columns:
        out["ticker"] = out["ticker"].astype(str)
    _schema_report(
        out,
        op=op,
        required=_OHLCV_REQUIRED,
        known=set(_OHLCV_COLS),
    )
    return out