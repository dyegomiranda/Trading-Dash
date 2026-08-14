"""Headlines reais com links (Google News RSS + yfinance)."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import quote_plus, urlparse, parse_qs, unquote
from urllib.request import Request, urlopen

import pandas as pd

from src.data.universe import normalize_ticker, to_yf_symbol


def _google_news_link(link: str) -> str:
    """Tenta extrair URL final de redirects do Google News."""
    if not link:
        return link
    try:
        # formato comum: ...?url=https%3A%2F%2F...
        qs = parse_qs(urlparse(link).query)
        if "url" in qs and qs["url"]:
            return unquote(qs["url"][0])
    except Exception:
        pass
    return link


def _fetch_google_rss(query: str, limit: int = 6) -> list[dict[str, Any]]:
    url = (
        "https://news.google.com/rss/search?"
        f"q={quote_plus(query)}&hl=pt-BR&gl=BR&ceid=BR:pt-419"
    )
    req = Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
        },
    )
    items: list[dict[str, Any]] = []
    try:
        with urlopen(req, timeout=12) as resp:
            raw = resp.read()
        root = ET.fromstring(raw)
        channel = root.find("channel")
        if channel is None:
            return []
        for item in channel.findall("item")[:limit]:
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            source_el = item.find("source")
            source = (source_el.text or "Google News").strip() if source_el is not None else "Google News"
            pub = item.findtext("pubDate") or ""
            published = "—"
            if pub:
                try:
                    published = parsedate_to_datetime(pub).strftime("%d/%m %H:%M")
                except Exception:
                    published = pub[:16]
            if not title or not link:
                continue
            items.append(
                {
                    "title": title,
                    "ticker": "",
                    "source": source,
                    "tag": "mercado",
                    "published": published,
                    "url": _google_news_link(link),
                }
            )
    except Exception:
        return []
    return items


def _fetch_yfinance_news(tickers: list[str], limit: int = 8) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    try:
        import yfinance as yf
    except Exception:
        return []

    for t in tickers[:8]:
        try:
            tk = yf.Ticker(to_yf_symbol(t))
            news = getattr(tk, "news", None) or []
            for n in news[:3]:
                if not isinstance(n, dict):
                    continue
                content = n.get("content") if isinstance(n.get("content"), dict) else None
                if content:
                    title = content.get("title") or n.get("title")
                    link = None
                    cu = content.get("canonicalUrl") or {}
                    if isinstance(cu, dict):
                        link = cu.get("url")
                    pub = content.get("pubDate") or content.get("displayTime") or ""
                    provider = content.get("provider") or {}
                    source = (
                        provider.get("displayName")
                        if isinstance(provider, dict)
                        else "Yahoo Finance"
                    ) or "Yahoo Finance"
                else:
                    title = n.get("title")
                    link = n.get("link") or n.get("url")
                    pub = n.get("publisher") or ""
                    source = n.get("publisher") or "Yahoo Finance"
                if not title or not link:
                    continue
                published = str(pub)[:16] if pub else "—"
                items.append(
                    {
                        "title": str(title),
                        "ticker": t,
                        "source": str(source),
                        "tag": "empresa",
                        "published": published,
                        "url": str(link),
                    }
                )
                if len(items) >= limit:
                    return items
        except Exception:
            continue
    return items


def fetch_headlines(
    tickers: list[str] | None = None,
    *,
    provider: str = "demo",
    limit: int = 10,
    timeout_sec: float | None = None,
) -> pd.DataFrame:
    """Headlines reais com URL clicável (com timeout global).

    Estratégia:
    1) Google News RSS (links reais) — poucas queries
    2) yfinance news (opcional, se ainda faltar)
    3) se tudo falhar, devolve vazio (sem fake)
    """
    from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout

    from src.config import get_settings

    tickers = [normalize_ticker(t) for t in (tickers or []) if t][:10]
    settings = get_settings()
    deadline = float(
        timeout_sec
        if timeout_sec is not None
        else getattr(settings, "news_timeout_sec", 8.0) or 8.0
    )

    def _work() -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        queries: list[str] = []
        if tickers:
            tq = " OR ".join(tickers[:3])
            queries.append(f"({tq}) (ações OR dividendos OR B3)")
        queries.append("dividendos B3 ações")
        queries.append("Ibovespa dividendos")

        for q in queries[:3]:
            batch = _fetch_google_rss(q, limit=max(3, limit // 2))
            for it in batch:
                title_u = it["title"].upper()
                for t in tickers:
                    if t.upper() in title_u:
                        it["ticker"] = t
                        break
                if not it.get("ticker") and tickers:
                    it["ticker"] = tickers[0]
                it["tag"] = (
                    "tese"
                    if "dividend" in q.lower() or "renda" in q.lower()
                    else "mercado"
                )
            items.extend(batch)
            if len(items) >= limit:
                break

        if len(items) < limit and tickers and provider == "yfinance":
            items.extend(_fetch_yfinance_news(tickers[:3], limit=limit - len(items)))

        seen: set[str] = set()
        unique: list[dict[str, Any]] = []
        for it in items:
            key = re.sub(r"\s+", " ", it["title"].lower()).strip()
            if key in seen or not it.get("url"):
                continue
            seen.add(key)
            unique.append(it)
            if len(unique) >= limit:
                break
        return unique

    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            fut = pool.submit(_work)
            unique = fut.result(timeout=deadline)
    except FuturesTimeout:
        unique = []
    except Exception:
        unique = []

    return pd.DataFrame(unique)
