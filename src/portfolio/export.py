"""Exportação da carteira paper (CSV) para o usuário baixar e estudar."""

from __future__ import annotations

import io
import zipfile
from datetime import datetime
from typing import Any

import pandas as pd

from src.portfolio.dividends_live import dividends_frame
from src.portfolio.paper import PaperPortfolio
from src.services import format_brl, format_pct


def holdings_export_df(
    portfolio: PaperPortfolio,
    prices: dict[str, float] | None = None,
) -> pd.DataFrame:
    prices = prices or {}
    df = portfolio.holdings_frame(prices)
    if df.empty:
        return pd.DataFrame(
            columns=[
                "ticker",
                "quantidade",
                "preco_medio",
                "preco_atual",
                "valor_atual",
                "custo",
                "lucro_prejuizo",
                "lucro_prejuizo_pct",
                "peso",
                "tipo",
            ]
        )
    out = df.copy()
    out = out.rename(
        columns={
            "shares": "quantidade",
            "avg_price": "preco_medio",
            "price": "preco_atual",
            "market_value": "valor_atual",
            "cost": "custo",
            "pnl": "lucro_prejuizo",
            "pnl_pct": "lucro_prejuizo_pct",
            "weight": "peso",
            "bucket": "tipo",
        }
    )
    return out


def trades_export_df(portfolio: PaperPortfolio) -> pd.DataFrame:
    if not portfolio.trades:
        return pd.DataFrame(
            columns=["data", "lado", "ticker", "quantidade", "preco", "valor", "obs"]
        )
    rows = []
    for t in portfolio.trades:
        rows.append(
            {
                "data": t.ts,
                "lado": "compra" if t.side == "buy" else "venda",
                "ticker": t.ticker,
                "quantidade": t.shares,
                "preco": t.price,
                "valor": t.amount,
                "obs": t.note,
            }
        )
    return pd.DataFrame(rows)


def summary_export_df(
    portfolio: PaperPortfolio,
    prices: dict[str, float] | None = None,
) -> pd.DataFrame:
    s = portfolio.summary(prices)
    return pd.DataFrame(
        [
            {"campo": "nome_carteira", "valor": s["name"]},
            {"campo": "caixa", "valor": s["cash"]},
            {"campo": "investido", "valor": s["invested"]},
            {"campo": "patrimonio_total", "valor": s["equity"]},
            {"campo": "capital_inicial", "valor": s["initial_cash"]},
            {"campo": "lucro_prejuizo", "valor": s["pnl"]},
            {"campo": "lucro_prejuizo_pct", "valor": s["pnl_pct"]},
            {"campo": "dividendos_recebidos", "valor": s["dividends_received"]},
            {"campo": "n_empresas", "valor": s["n_positions"]},
            {"campo": "n_ordens", "valor": s["n_trades"]},
            {"campo": "atualizado_em", "valor": s["updated_at"]},
            {"campo": "exportado_em", "valor": datetime.utcnow().isoformat()},
        ]
    )


def portfolio_to_csv_bundle(
    portfolio: PaperPortfolio,
    prices: dict[str, float] | None = None,
) -> bytes:
    """Gera um ZIP com CSVs: resumo, posições, ordens, dividendos."""
    prices = prices or {}
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        files = {
            "resumo.csv": summary_export_df(portfolio, prices),
            "posicoes.csv": holdings_export_df(portfolio, prices),
            "ordens.csv": trades_export_df(portfolio),
            "dividendos.csv": dividends_frame(portfolio),
        }
        for name, df in files.items():
            zf.writestr(name, df.to_csv(index=False).encode("utf-8-sig"))
        # README curto em PT
        zf.writestr(
            "LEIA-ME.txt",
            (
                "TradingDash — export da conta de treino\n"
                "=====================================\n"
                "Arquivos:\n"
                "- resumo.csv — caixa, patrimônio, dividendos totais\n"
                "- posicoes.csv — ações que você tem agora\n"
                "- ordens.csv — compras e vendas\n"
                "- dividendos.csv — dividendos já creditados em caixa\n\n"
                "Isto é dinheiro de treino (paper). Não é extrato de corretora.\n"
            ).encode("utf-8"),
        )
    return buf.getvalue()


def single_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8-sig")


def friendly_summary_lines(
    portfolio: PaperPortfolio,
    prices: dict[str, float] | None = None,
) -> list[str]:
    s = portfolio.summary(prices)
    return [
        f"Carteira: {s['name']}",
        f"Patrimônio: {format_brl(s['equity'])}",
        f"Caixa: {format_brl(s['cash'])}",
        f"Investido: {format_brl(s['invested'])}",
        f"Dividendos já creditados: {format_brl(s['dividends_received'])}",
        f"Empresas: {s['n_positions']} · Ordens: {s['n_trades']}",
        f"Resultado vs capital inicial: {format_brl(s['pnl'])} ({format_pct(s['pnl_pct'])})",
    ]
