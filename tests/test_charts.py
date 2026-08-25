"""Rosca sem rótulo sobreposto e médias dos 4 pilares."""

from __future__ import annotations

import pandas as pd

from src.ui.charts import donut_allocation
from src.ui.components import pillar_means


def test_donut_hover_uses_full_name():
    fig = donut_allocation(["LREN3"], [100.0])
    hover = list(fig.data[0].hovertext)
    assert hover
    assert "LREN3" in str(hover[0])
    assert "Renner" in str(hover[0])


def test_donut_labels_on_slices_with_percent():
    fig = donut_allocation(["ITUB4", "WEGE3", "TAEE11"], [40.0, 35.0, 25.0])
    pie = fig.data[0]
    assert pie.textinfo == "label+percent"
    assert pie.textposition == "outside"
    assert "ITUB4" in list(pie.labels)
    assert fig.layout.showlegend is False
    center_xs = [a.x for a in (fig.layout.annotations or [])]
    assert not center_xs or all(abs(float(x) - 0.5) < 1e-6 for x in center_xs)


def test_donut_keeps_all_slices():
    labels = [f"T{i}" for i in range(12)]
    values = [20.0] + [1.0] * 11
    fig = donut_allocation(labels, values)
    names = list(fig.data[0].labels)
    assert "Outros" not in names
    assert len(names) == 12
    hover = list(fig.data[0].hovertext)
    assert len(hover) == 12


def test_pillar_means_none_when_missing():
    empty = pd.DataFrame({"ticker": ["A"]})
    assert pillar_means(empty) == (None, None, None, None)
    df = pd.DataFrame(
        {
            "score_quality": [80.0, 60.0],
            "score_dividends": [70.0, None],
            "score_financial_health": [None, None],
            "score_valuation": [50.0, 50.0],
        }
    )
    q, d, h, v = pillar_means(df)
    assert q == 70.0
    assert d == 70.0
    assert h is None
    assert v == 50.0
