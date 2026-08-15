"""Pacote D: tipo de ativo B3 e retenção de IR nos dividendos."""

from __future__ import annotations

from src.data.asset_type import asset_kind, dividend_tax_rate, is_fii
from src.portfolio.paper import PaperPortfolio


def test_asset_kind_detection():
    assert asset_kind("MXRF11") == "fii"
    assert asset_kind("KNRI11") == "fii"
    assert asset_kind("ITUB4") == "acao"
    assert asset_kind("PETR4") == "acao"
    assert is_fii("HGLG11") is True
    assert is_fii("BBAS3") is False
    # Units da tese NÃO são FII
    assert asset_kind("TAEE11") == "acao"
    assert asset_kind("SANB11") == "acao"
    assert asset_kind("KLBN11") == "acao"
    assert asset_kind("ENGI11") == "acao"
    assert is_fii("TAEE11") is False


def test_dividend_tax_rate_default_isento():
    # Default: ação e FII sem IR
    assert dividend_tax_rate("ITUB4") == 0.0
    assert dividend_tax_rate("MXRF11") == 0.0


def test_jcp_modeling():
    # 50% como JCP retido a 15% → 7.5% efetivo
    assert abs(dividend_tax_rate("ITUB4", jcp_share=0.5) - 0.075) < 1e-9
    # FII sempre isento, mesmo com jcp_share alto (não tem JCP)
    assert dividend_tax_rate("MXRF11", jcp_share=0.5) == 0.0
    # share capado em [0,1]
    assert dividend_tax_rate("ITUB4", jcp_share=2.0) <= 0.15


def test_credit_with_tax():
    pf = PaperPortfolio.create(name="asset-t", cash=10_000)
    pf.buy("ITUB4", 100, 30.0)
    before = pf.cash
    # JCP 50%*15% = 7.5% de retenção
    pf.credit_dividend("ITUB4", 1.0, ex_date="2026-02-01", tax_rate=0.075)
    # 100 bruto, retido 7.5 → líquido 92.5
    assert abs((pf.cash - before) - 92.5) < 1e-6


def test_fii_credit_isento():
    pf = PaperPortfolio.create(name="fi-t", cash=10_000)
    pf.buy("MXRF11", 100, 10.0)
    before = pf.cash
    pf.credit_dividend("MXRF11", 0.8, ex_date="2026-02-01", tax_rate=0.0)
    # FII isento: 100 * 0.8 = 80 integral
    assert abs((pf.cash - before) - 80.0) < 1e-6