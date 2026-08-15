"""Pacote A: dividendos no paper + export CSV."""

from __future__ import annotations

from datetime import timedelta


from src.data.providers import DemoDataProvider
from src.portfolio.dividends_live import dividends_frame, sync_paper_dividends
from src.portfolio.export import portfolio_to_csv_bundle, holdings_export_df
from src.portfolio.paper import PaperPortfolio
from src.utils import utcnow


def test_shares_at_from_trades():
    pf = PaperPortfolio.create(name="div-test", cash=50_000)
    t0 = (utcnow() - timedelta(days=30)).isoformat()
    t1 = (utcnow() - timedelta(days=10)).isoformat()
    pf.buy("ITUB4", 100, 30.0, ts=t0)
    pf.sell("ITUB4", 40, 32.0, ts=t1)
    mid = utcnow() - timedelta(days=20)
    assert abs(pf.shares_at("ITUB4", mid) - 100) < 1e-6
    assert abs(pf.shares_at("ITUB4", utcnow()) - 60) < 1e-6


def test_credit_dividend_dedup():
    pf = PaperPortfolio.create(name="div-test2", cash=10_000)
    pf.buy("PETR4", 50, 40.0, ts="2024-01-01T00:00:00")
    e1 = pf.credit_dividend("PETR4", 1.0, ts="2024-06-01T00:00:00", ex_date="2024-06-01", shares=50)
    e2 = pf.credit_dividend("PETR4", 1.0, ts="2024-06-01T00:00:00", ex_date="2024-06-01", shares=50)
    assert e1 is not None
    assert e2 is None
    assert abs(e1.amount - 50.0) < 1e-6
    assert abs(pf.summary()["dividends_received"] - 50.0) < 1e-6


def test_sync_demo_dividends():
    pf = PaperPortfolio.create(name="div-demo", cash=100_000)
    # compra no passado distante para pegar divs simulados do demo
    past = (utcnow() - timedelta(days=400)).isoformat()
    pf.buy("ITUB4", 200, 25.0, ts=past)
    cash_before = pf.cash
    prov = DemoDataProvider()
    result = sync_paper_dividends(pf, prov, max_days=500)
    # demo gera pagamentos semestrais — pode ou não haver no intervalo
    assert "credited" in result
    assert result["total_brl"] >= 0
    # segunda sync não duplica
    n1 = result["credited"]
    cash_mid = pf.cash
    result2 = sync_paper_dividends(pf, prov, max_days=500)
    assert result2["credited"] == 0
    assert abs(pf.cash - cash_mid) < 1e-6
    if n1 > 0:
        assert pf.cash > cash_before
        assert not dividends_frame(pf).empty


def test_export_zip_nonempty():
    pf = PaperPortfolio.create(name="exp", cash=5_000)
    pf.buy("VALE3", 10, 60.0)
    pf.credit_dividend("VALE3", 0.5, ex_date="2025-01-15", shares=10)
    blob = portfolio_to_csv_bundle(pf, {"VALE3": 62.0})
    assert isinstance(blob, (bytes, bytearray))
    assert len(blob) > 100
    assert b"posicoes.csv" in blob or blob[:2] == b"PK"  # zip magic
    hold = holdings_export_df(pf, {"VALE3": 62.0})
    assert not hold.empty
    assert "ticker" in hold.columns
