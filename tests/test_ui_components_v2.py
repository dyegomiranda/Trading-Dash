"""Testes para os novos componentes visuais da UI 2.0 (sem jargões, metas e notícias)."""

from __future__ import annotations

import pandas as pd

from src.ui.components import (
    render_goal_milestones,
    render_news_feed_cards,
    render_stock_health_meters,
)


def test_render_stock_health_meters_healthy(monkeypatch):
    rendered = []
    import streamlit as st

    monkeypatch.setattr(st, "markdown", lambda text, **kwargs: rendered.append(text))

    sample_row = {
        "ticker": "BBAS3",
        "pe": 4.5,
        "net_debt_ebitda": 0.5,
        "fcf_positive": True,
        "dividend_yield": 0.085,
        "payout": 0.45,
        "roe": 0.21,
    }
    render_stock_health_meters(sample_row)
    assert len(rendered) == 1
    html_output = rendered[0]
    assert "Preço Atrativo" in html_output
    assert "Finanças Sólidas" in html_output
    assert "Renda Forte" in html_output
    assert "Altamente Rentável" in html_output


def test_render_stock_health_meters_alert(monkeypatch):
    rendered = []
    import streamlit as st

    monkeypatch.setattr(st, "markdown", lambda text, **kwargs: rendered.append(text))

    sample_row = {
        "ticker": "RISK3",
        "pe": 35.0,
        "net_debt_ebitda": 4.5,
        "fcf_positive": False,
        "dividend_yield": 0.01,
        "payout": 1.2,
        "roe": 0.02,
    }
    render_stock_health_meters(sample_row)
    assert len(rendered) == 1
    html_output = rendered[0]
    assert "Preço Esticado" in html_output
    assert "Dívida Elevada" in html_output
    assert "Risco de Corte" in html_output
    assert "Baixa Eficiência" in html_output


def test_render_stock_health_meters_none(monkeypatch):
    rendered = []
    import streamlit as st

    monkeypatch.setattr(st, "markdown", lambda text, **kwargs: rendered.append(text))

    render_stock_health_meters(None)
    assert len(rendered) == 0


def test_render_goal_milestones(monkeypatch):
    rendered = []
    import streamlit as st

    monkeypatch.setattr(st, "markdown", lambda text, **kwargs: rendered.append(text))

    render_goal_milestones(current_monthly_income=600.0)
    assert len(rendered) == 1
    html_output = rendered[0]
    assert "R$ 450" in html_output
    assert "R$ 2.000" in html_output
    assert "R$ 5.000" in html_output
    assert "R$ 20.000" in html_output
    assert "Conquistada" in html_output


def test_render_news_feed_cards(monkeypatch):
    rendered = []
    import streamlit as st

    monkeypatch.setattr(st, "markdown", lambda text, **kwargs: rendered.append(text))

    df = pd.DataFrame(
        [
            {
                "title": "Banco do Brasil lucra forte no trimestre",
                "url": "https://example.com/bb",
                "source": "Valor",
                "published": "Hoje",
                "ticker": "BBAS3",
                "sentiment": "positive",
                "sentiment_label": "Positiva",
            }
        ]
    )
    render_news_feed_cards(df)
    assert len(rendered) == 1
    html_output = rendered[0]
    assert "Banco do Brasil lucra forte" in html_output
    assert "td-sentiment-pill positive" in html_output


def test_tour_force_active(monkeypatch):
    import streamlit as st
    from src.ui.onboarding import mark_onboarding_done, render_onboarding_if_needed

    st.session_state["onboarding_done"] = True
    st.session_state["tour_force_active"] = True
    monkeypatch.setattr(st, "markdown", lambda *a, **kw: None)
    monkeypatch.setattr(st, "progress", lambda *a, **kw: None)
    monkeypatch.setattr("src.ui.onboarding._has_portfolio_positions", lambda: True)

    # When tour_force_active is True, it must render the tour even if positions exist
    assert render_onboarding_if_needed() is True

    mark_onboarding_done()
    assert st.session_state.get("tour_force_active") is False
    assert st.session_state.get("onboarding_done") is True


def test_expanded_universe_369():
    from src.data.universe import get_universe
    from src.services import load_scored_universe

    univ = get_universe(mode="full")
    assert len(univ) >= 369

    # Score exactly 369 tickers with demo provider
    result = load_scored_universe(provider_name="demo", tickers=univ[:369])
    assert result.scored is not None
    assert len(result.scored) == 369

