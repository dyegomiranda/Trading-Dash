#!/usr/bin/env python3
"""Atualiza data/reference/b3_tickers.json via Yahoo Finance.

Uso:
  .venv/bin/python scripts/refresh_b3_metadata.py

Depois revise manualmente renomeações (ELET→AXIA etc.) em
src/data/reference.py (MANUAL_OVERRIDES).
"""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.config import B3_UNIVERSE  # noqa: E402
from src.data.reference import MANUAL_OVERRIDES, REFERENCE_PATH  # noqa: E402


def main() -> None:
    import yfinance as yf

    extra = list(MANUAL_OVERRIDES.keys()) + ["AXIA3", "AXIA6"]
    tickers = sorted(set(B3_UNIVERSE + extra))
    results: dict = {}
    for i, t in enumerate(tickers):
        sym = f"{t}.SA"
        try:
            info = yf.Ticker(sym).info or {}
            name = info.get("shortName") or info.get("longName")
            sector = info.get("sector")
            industry = info.get("industry")
            qt = info.get("quoteType")
            price = (
                info.get("currentPrice")
                or info.get("regularMarketPrice")
                or info.get("previousClose")
            )
            if not name and not sector and not price:
                results[t] = {
                    "ticker": t,
                    "status": "missing",
                    "name": None,
                    "sector": None,
                    "industry": None,
                    "source": "yfinance",
                }
            else:
                results[t] = {
                    "ticker": t,
                    "status": "active" if qt == "EQUITY" or price else "unknown",
                    "name": name,
                    "sector": sector,
                    "industry": industry,
                    "quote_type": qt,
                    "source": "yfinance",
                }
        except Exception as e:
            results[t] = {
                "ticker": t,
                "status": "error",
                "error": str(e)[:120],
                "source": "yfinance",
            }
        if (i + 1) % 40 == 0:
            print(f"progress {i+1}/{len(tickers)}")
            time.sleep(0.4)

    for t, ov in MANUAL_OVERRIDES.items():
        base = results.get(t, {"ticker": t, "source": "manual"})
        base.update(ov)
        base["ticker"] = t
        results[t] = base

    REFERENCE_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "description": (
            "Metadata B3. Demo usa nome/setor daqui; números demo são sintéticos. "
            "Bolsa real usa yfinance com fallback neste arquivo."
        ),
        "tickers": results,
    }
    REFERENCE_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("wrote", REFERENCE_PATH, "n=", len(results))


if __name__ == "__main__":
    main()
