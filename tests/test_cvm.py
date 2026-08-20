"""Parser CVM DFP/ITR — fixtures in-memory, sem rede."""

from __future__ import annotations

import io
import zipfile

import pandas as pd

from src.data.cvm import (
    annualize_factor,
    digits_cnpj,
    extract_accounts,
    fundamentals_to_quarters,
    parse_cvm_zip,
    parse_statement_csv,
    parse_years_arg,
    statements_to_fundamentals,
)


_DRE_CSV = """CNPJ_CIA;DT_REFER;VERSAO;DENOM_CIA;CD_CVM;GRUPO_DF;ORDEM_EXERC;DT_INI_EXERC;DT_FIM_EXERC;CD_CONTA;DS_CONTA;VL_CONTA
07.526.557/0001-00;2022-12-31;1;AMBEV S.A.;2294;DF Consolidado - Demonstração do Resultado;ÚLTIMO;2022-01-01;2022-12-31;3.01;Receita de Venda de Bens e/ou Serviços;100000.00
07.526.557/0001-00;2022-12-31;1;AMBEV S.A.;2294;DF Consolidado - Demonstração do Resultado;ÚLTIMO;2022-01-01;2022-12-31;3.11;Lucro/Prejuízo Consolidado do Período;20000.00
07.526.557/0001-00;2022-12-31;1;AMBEV S.A.;2294;DF Individual - Demonstração do Resultado;ÚLTIMO;2022-01-01;2022-12-31;3.01;Receita;1.00
"""

_BPP_CSV = """CNPJ_CIA;DT_REFER;VERSAO;DENOM_CIA;CD_CVM;GRUPO_DF;ORDEM_EXERC;CD_CONTA;DS_CONTA;VL_CONTA
07.526.557/0001-00;2022-12-31;1;AMBEV S.A.;2294;DF Consolidado - Balanço Patrimonial Passivo;ÚLTIMO;2.03;Patrimônio Líquido Consolidado;80000.00
07.526.557/0001-00;2022-12-31;1;AMBEV S.A.;2294;DF Consolidado - Balanço Patrimonial Passivo;ÚLTIMO;2.01.04;Empréstimos e Financiamentos;5000.00
07.526.557/0001-00;2022-12-31;1;AMBEV S.A.;2294;DF Consolidado - Balanço Patrimonial Passivo;ÚLTIMO;2.02.01;Empréstimos e Financiamentos;7000.00
"""

_BPA_CSV = """CNPJ_CIA;DT_REFER;VERSAO;DENOM_CIA;CD_CVM;GRUPO_DF;ORDEM_EXERC;CD_CONTA;DS_CONTA;VL_CONTA
07.526.557/0001-00;2022-12-31;1;AMBEV S.A.;2294;DF Consolidado - Balanço Patrimonial Ativo;ÚLTIMO;1.01.01;Caixa e Equivalentes de Caixa;4000.00
"""


def _zip_bytes() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("dfp_cia_aberta_DRE_con_2022.csv", _DRE_CSV.encode("latin-1"))
        zf.writestr("dfp_cia_aberta_BPP_con_2022.csv", _BPP_CSV.encode("latin-1"))
        zf.writestr("dfp_cia_aberta_BPA_con_2022.csv", _BPA_CSV.encode("latin-1"))
    return buf.getvalue()


def test_digits_cnpj():
    assert digits_cnpj("07.526.557/0001-00") == "07526557000100"
    assert digits_cnpj("7526557000100") == "07526557000100"


def test_annualize_factor_q1_is_about_four():
    f = annualize_factor(pd.Timestamp("2022-01-01"), pd.Timestamp("2022-03-31"))
    assert 3.5 < f < 4.5
    f_year = annualize_factor(pd.Timestamp("2022-01-01"), pd.Timestamp("2022-12-31"))
    assert 0.95 < f_year < 1.05


def test_parse_years_arg():
    assert parse_years_arg("2020-2022") == [2020, 2021, 2022]
    assert parse_years_arg("2021,2023") == [2021, 2023]


def test_extract_accounts_prefers_consolidado():
    df = pd.read_csv(io.StringIO(_DRE_CSV), sep=";", dtype=str)
    out = extract_accounts(
        df,
        {"receita": ("3.01",), "lucro": ("3.11", "3.09")},
    )
    assert len(out) == 1
    assert abs(float(out.iloc[0]["receita"]) - 100000.0) < 1e-6
    assert abs(float(out.iloc[0]["lucro"]) - 20000.0) < 1e-6


def test_parse_zip_and_fundamentals():
    statements = parse_cvm_zip(_zip_bytes(), source="cvm_dfp")
    assert not statements.empty
    fund = statements_to_fundamentals(statements, {"07526557000100": "ABEV3"})
    assert list(fund["ticker"]) == ["ABEV3"]
    row = fund.iloc[0]
    assert abs(float(row["roe"]) - 0.25) < 0.01
    assert abs(float(row["net_margin"]) - 0.20) < 1e-6
    assert "price" not in fund.columns or pd.isna(row.get("price", float("nan")))
    assert "dividend_yield" not in fund.columns or pd.isna(row.get("dividend_yield", float("nan")))
    quarters = fundamentals_to_quarters(fund)
    assert "2022-12-31" in quarters
    assert quarters["2022-12-31"][0]["ticker"] == "ABEV3"


def test_parse_statement_csv_dre():
    df = parse_statement_csv(_DRE_CSV.encode("utf-8"), "dre")
    assert not df.empty
    assert df.iloc[0]["cnpj"] == "07526557000100"
