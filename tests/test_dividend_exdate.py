"""Pacote: dividendos ao vivo com data-ex real (entitlement).

Valida que o crédito no paper respeita a DATA-EX (quem tinha ação no dia tem
direito), não a data de pagamento. Compra entre ex-date e pagamento NÃO recebe.
"""

from __future__ import annotations

import pytest

from src.portfolio.dividends_live import sync_paper_dividends
from src.portfolio.paper import PaperPortfolio


class _FakeProvider:
    """Provider determinístico com histórico de dividendos pré-definido."""

    name = "fake"

    def __init__(self, rows: list[dict]):
        self._rows = rows

    def get_dividend_history(self, tickers, start, end=None):
        import pandas as pd

        if not self._rows:
            return pd.DataFrame(columns=["date", "ticker", "amount", "ex_date", "payment_date"])
        return pd.DataFrame(self._rows)


_DIV_ROWS = [
    {
        "date": "2024-03-15",
        "ticker": "ITUB4",
        "amount": 1.0,
        "label": "DIVIDENDO",
        "ex_date": "2024-03-15",
        "payment_date": "2024-04-10",
    }
]


def test_buy_after_ex_before_payment_does_not_receive():
    """Comprar entre a data-ex e o pagamento NÃO dá direito ao provento."""
    p = PaperPortfolio.create(cash=100_000.0)
    # compra em 20/03 — depois do ex 15/03, antes do pagamento 10/04
    p.buy("ITUB4", 10.0, 30.0, ts="2024-03-20T10:00:00", note="t")

    res = sync_paper_dividends(
        p,
        _FakeProvider(_DIV_ROWS),
        end="2024-04-30",
        allow_monthly_estimate=False,
        max_days=540,
    )

    assert res["credited"] == 0
    assert p.cash == pytest.approx(100_000.0 - 300.0)  # só o custo da compra
    assert p.dividends == []


def test_buy_before_ex_receives():
    """Quem tinha ação na data-ex recebe o provento."""
    p = PaperPortfolio.create(cash=100_000.0)
    p.buy("ITUB4", 10.0, 30.0, ts="2024-03-01T10:00:00", note="t")

    res = sync_paper_dividends(
        p,
        _FakeProvider(_DIV_ROWS),
        end="2024-04-30",
        allow_monthly_estimate=False,
        max_days=540,
    )

    assert res["credited"] == 1
    ev = p.dividends[0]
    assert ev.ex_date == "2024-03-15"  # data-ex real, não a de pagamento
    assert ev.amount == 10.0  # 10 ações × R$1
    assert abs(p.cash - (100_000.0 - 300.0 + 10.0)) < 1e-6


def test_buy_day_before_ex_counts():
    """Compra na véspera da data-ex tem direito."""
    p = PaperPortfolio.create(cash=100_000.0)
    p.buy("ITUB4", 5.0, 30.0, ts="2024-03-14T09:00:00", note="t")

    sync_paper_dividends(
        p,
        _FakeProvider(_DIV_ROWS),
        end="2024-04-30",
        allow_monthly_estimate=False,
        max_days=540,
    )
    assert len(p.dividends) == 1
    assert p.dividends[0].amount == 5.0


def test_buy_on_ex_date_does_not_count():
    """Compra no próprio dia da data-ex não recebe."""
    p = PaperPortfolio.create(cash=100_000.0)
    p.buy("ITUB4", 5.0, 30.0, ts="2024-03-15T10:00:00", note="t")

    sync_paper_dividends(
        p,
        _FakeProvider(_DIV_ROWS),
        end="2024-04-30",
        allow_monthly_estimate=False,
        max_days=540,
    )
    assert len(p.dividends) == 0


def test_dedup_by_ex_date_even_when_payment_differs():
    """Mesma data-ex não pode ser creditada duas vezes (idempotência)."""
    p = PaperPortfolio.create(cash=100_000.0)
    p.buy("ITUB4", 10.0, 30.0, ts="2024-03-01T10:00:00", note="t")

    r1 = sync_paper_dividends(
        p, _FakeProvider(_DIV_ROWS), end="2024-04-30",
        allow_monthly_estimate=False, max_days=540,
    )
    r2 = sync_paper_dividends(
        p, _FakeProvider(_DIV_ROWS), end="2024-04-30",
        allow_monthly_estimate=False, max_days=540,
    )
    assert r1["credited"] == 1
    assert r2["credited"] == 0
    assert r2["skipped_duplicate"] == 1
    assert len(p.dividends) == 1