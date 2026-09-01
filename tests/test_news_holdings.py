"""Notícias da carteira não recebem manchete genérica do Ibovespa."""

from __future__ import annotations

from src.data.news import fetch_headlines


def test_holdings_only_keeps_ticker_in_title(monkeypatch):
    def fake_rss(query, limit=6, attempts=2):
        return [
            {
                "title": "ITUB4 anuncia JCP recorde",
                "url": "https://example.com/itub",
                "source": "Valor",
                "tag": "mercado",
                "published": "01/09 10:00",
                "ticker": "",
            },
            {
                "title": "Ibovespa sobe com Wall Street",
                "url": "https://example.com/ibov",
                "source": "InfoMoney",
                "tag": "mercado",
                "published": "01/09 10:01",
                "ticker": "",
            },
        ]

    monkeypatch.setattr("src.data.news._fetch_google_rss", fake_rss)
    monkeypatch.setattr("src.data.news._fetch_yfinance_news", lambda *a, **k: [])
    df = fetch_headlines(
        ["ITUB4"],
        provider="demo",
        holdings_only=True,
        timeout_sec=5,
        limit=10,
    )
    titles = " ".join(df["title"].astype(str).tolist()) if df is not None and not df.empty else ""
    assert "ITUB4" in titles
    assert "Ibovespa" not in titles
