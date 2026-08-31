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


def _fetch_google_rss(query: str, limit: int = 6, attempts: int = 2) -> list[dict[str, Any]]:
    url = (
        "https://news.google.com/rss/search?"
        f"q={quote_plus(query)}&hl=pt-BR&gl=BR&ceid=BR:pt-419"
    )
    user_agents = [
        (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
    ]
    for attempt in range(attempts):
        req = Request(url, headers={"User-Agent": user_agents[attempt % len(user_agents)]})
        try:
            with urlopen(req, timeout=15) as resp:
                raw = resp.read()
            root = ET.fromstring(raw)
            channel = root.find("channel")
            if channel is None:
                continue
            items: list[dict[str, Any]] = []
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
            if items:
                return items
        except Exception:
            continue
    return []


def _fetch_yfinance_news(tickers: list[str], limit: int = 8) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    try:
        import yfinance as yf
        from src.data.yf_quiet import silence_yfinance

        silence_yfinance()
    except Exception:
        return []

    for t in tickers[:8]:
        try:
            from src.data.yf_retry import fetch_with_retry

            tk = yf.Ticker(to_yf_symbol(t))
            news = fetch_with_retry(
                lambda: (getattr(tk, "news", None) or []),
                what=f"notícias {t}",
                max_attempts=2,
            )
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


POSITIVE_KEYWORDS = (
    "dividendo",
    "jcp",
    "provento",
    "lucro",
    "alta",
    "cresce",
    "recorde",
    "recompra",
    "eleva",
    "expansão",
    "aquisição",
    "otimismo",
    "supera",
    "paga",
    "distribui",
)
NEGATIVE_KEYWORDS = (
    "prejuízo",
    "queda",
    "despenca",
    "investigação",
    "corte",
    "fraude",
    "processo",
    "recuperação judicial",
    "crise",
    "rebaixada",
    "multa",
    "dívida",
    "cai",
    "risco",
)


def classify_sentiment(title: str) -> tuple[str, str, str]:
    """Retorna (sentiment_code, badge_label, badge_color)."""
    t = title.lower()
    pos_score = sum(1 for kw in POSITIVE_KEYWORDS if kw in t)
    neg_score = sum(1 for kw in NEGATIVE_KEYWORDS if kw in t)
    if neg_score > pos_score:
        return "negative", "⚠️ Alerta / Risco", "#EF4444"
    if pos_score > neg_score:
        return "positive", "🟢 Positiva / Proventos", "#10B981"
    return "neutral", "🟡 Notícia / Mercado", "#6B7280"


def fetch_headlines(
    tickers: list[str] | None = None,
    *,
    provider: str = "demo",
    limit: int = 10,
    timeout_sec: float | None = None,
) -> pd.DataFrame:
    """Headlines reais com URL clicável e classificação de sentimento."""
    from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout

    from src.config import get_settings

    tickers = [normalize_ticker(t) for t in (tickers or []) if t][:10]
    settings = get_settings()
    deadline = float(
        timeout_sec
        if timeout_sec is not None
        else getattr(settings, "news_timeout_sec", 6.0) or 6.0
    )

    def _work() -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        queries: list[str] = []
        if tickers:
            tq = " OR ".join(tickers[:3])
            queries.append(f"({tq}) (ações OR dividendos OR B3)")
        queries.append("dividendos B3 ações")
        queries.append("Ibovespa dividendos")

        with ThreadPoolExecutor(max_workers=len(queries)) as q_pool:
            futures = [q_pool.submit(_fetch_google_rss, q, max(3, limit // 2)) for q in queries]
            for fut, q in zip(futures, queries):
                try:
                    batch = fut.result(timeout=4.0)
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
                except Exception:
                    continue

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

    cols = [
        "title",
        "ticker",
        "source",
        "tag",
        "published",
        "url",
        "sentiment",
        "sentiment_label",
        "sentiment_color",
    ]
    if not unique:
        return pd.DataFrame(columns=cols)
    for it in unique:
        code, label, color = classify_sentiment(str(it.get("title", "")))
        it["sentiment"] = code
        it["sentiment_label"] = label
        it["sentiment_color"] = color
    df = pd.DataFrame(unique)
    for c in cols:
        if c not in df.columns:
            df[c] = ""
    return df[cols]



