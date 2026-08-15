"""Rosca sem rótulo sobreposto e médias dos 4 pilares."""

from __future__ import annotations

import pandas as pd

from src.ui.charts import donut_allocation
from src.ui.components import pillar_means


def test_donut_puts_percent_in_legend_not_on_slice():
    fig = donut_allocation(["ITUB4", "WEGE3", "TAEE11"], [40.0, 35.0, 25.0])
    pie = fig.data[0]
    assert pie.textinfo == "none"
    labels = list(pie.labels)
    assert any("ITUB4" in str(x) and "%" in str(x) for x in labels)


def test_donut_groups_tiny_slices():
    labels = [f"T{i}" for i in range(12)]
    values = [20.0] + [1.0] * 11
    fig = donut_allocation(labels, values)
    names = " ".join(str(x) for x in fig.data[0].labels)
    assert "Outros" in names
    assert len(fig.data[0].labels) <= 9


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
