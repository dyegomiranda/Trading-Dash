"""Carteira paper money (dinheiro fictício) com persistência local."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import pandas as pd

from src.config import PORTFOLIO_DIR, get_settings
from src.data.universe import normalize_ticker
from src.utils import utcnow_date, utcnow_iso


@dataclass
class Position:
    ticker: str
    shares: float
    avg_price: float
    bucket: str = "core"

    def market_value(self, price: float) -> float:
        return self.shares * price


@dataclass
class Trade:
    id: str
    ts: str
    side: str  # buy | sell
    ticker: str
    shares: float
    price: float
    amount: float
    note: str = ""


@dataclass
class DividendEvent:
    id: str
    ts: str
    ticker: str
    amount: float
    shares: float
    note: str = ""
    amount_per_share: float = 0.0
    ex_date: str = ""  # YYYY-MM-DD — chave para não creditar duas vezes


@dataclass
class PaperPortfolio:
    name: str = "paper-main"
    cash: float = 100_000.0
    initial_cash: float = 100_000.0
    currency: str = "BRL"
    positions: dict[str, Position] = field(default_factory=dict)
    trades: list[Trade] = field(default_factory=list)
    dividends: list[DividendEvent] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: utcnow_iso())
    updated_at: str = field(default_factory=lambda: utcnow_iso())

    @classmethod
    def create(cls, name: str = "paper-main", cash: float | None = None) -> PaperPortfolio:
        initial = cash if cash is not None else get_settings().paper_initial_cash
        return cls(name=name, cash=initial, initial_cash=initial)

    def _touch(self) -> None:
        self.updated_at = utcnow_iso()

    def set_capital(
        self,
        new_capital: float,
        prices: dict[str, float] | None = None,
        *,
        reset_positions: bool = False,
    ) -> None:
        """Define o patrimônio de treino.

        - reset_positions=True: zera posições e coloca tudo em caixa.
        - caso contrário: ajusta o caixa para que patrimônio ≈ new_capital
          (mantém posições; se investido > novo capital, exige reset).
        """
        if new_capital <= 0:
            raise ValueError("Capital deve ser maior que zero")
        prices = prices or {}
        if reset_positions or not self.positions:
            self.positions = {}
            self.cash = float(new_capital)
            self.initial_cash = float(new_capital)
            self.trades = []
            self.dividends = []
            self._touch()
            return

        invested = sum(
            pos.shares * prices.get(t, pos.avg_price) for t, pos in self.positions.items()
        )
        if invested > new_capital + 1e-6:
            raise ValueError(
                "O valor investido atual é maior que o novo capital. "
                "Marque 'zerar posições' ou venda ativos antes."
            )
        self.cash = float(new_capital - invested)
        self.initial_cash = float(new_capital)
        self._touch()

    def buy_value(
        self,
        ticker: str,
        value_brl: float,
        price: float,
        bucket: str = "core",
        note: str = "alocacao-manual",
    ) -> Trade:
        """Compra pelo valor em R$ (converte em quantidade de ações fracionária)."""
        if value_brl <= 0 or price <= 0:
            raise ValueError("Valor e preço devem ser > 0")
        shares = value_brl / price
        return self.buy(ticker, shares, price, bucket=bucket, note=note)

    def buy(
        self,
        ticker: str,
        shares: float,
        price: float,
        bucket: str = "core",
        note: str = "",
        ts: str | None = None,
        *,
        fee_bps: float = 0.0,
        slippage_bps: float = 0.0,
    ) -> Trade:
        ticker = normalize_ticker(ticker)
        if shares <= 0 or price <= 0:
            raise ValueError("shares e price devem ser > 0")
        exec_price = price * (1.0 + slippage_bps / 10_000.0)
        amount = shares * exec_price
        fee = amount * fee_bps / 10_000.0
        total_cost = amount + fee
        if total_cost > self.cash + 1e-9:
            raise ValueError(f"Caixa insuficiente: precisa {total_cost:.2f}, tem {self.cash:.2f}")
        self.cash -= total_cost
        pos = self.positions.get(ticker)
        if pos is None:
            self.positions[ticker] = Position(ticker=ticker, shares=shares, avg_price=exec_price, bucket=bucket)
        else:
            new_shares = pos.shares + shares
            pos.avg_price = (pos.avg_price * pos.shares + exec_price * shares) / new_shares
            pos.shares = new_shares
            pos.bucket = bucket or pos.bucket
        trade = Trade(
            id=str(uuid4()),
            ts=ts or utcnow_iso(),
            side="buy",
            ticker=ticker,
            shares=shares,
            price=exec_price,
            amount=amount,
            note=note if not fee else f"{note} (fee {fee:.2f})",
        )
        self.trades.append(trade)
        self._touch()
        return trade

    def sell(
        self,
        ticker: str,
        shares: float,
        price: float,
        note: str = "",
        ts: str | None = None,
        *,
        fee_bps: float = 0.0,
        slippage_bps: float = 0.0,
        capital_gains_rate: float = 0.0,
    ) -> Trade:
        ticker = normalize_ticker(ticker)
        pos = self.positions.get(ticker)
        if pos is None or shares > pos.shares + 1e-9:
            raise ValueError("Posição insuficiente para venda")
        if shares <= 0 or price <= 0:
            raise ValueError("shares e price devem ser > 0")
        exec_price = price * (1.0 - slippage_bps / 10_000.0)
        amount = shares * exec_price
        fee = amount * fee_bps / 10_000.0
        gain = (exec_price - pos.avg_price) * shares
        cg_tax = max(0.0, gain) * float(capital_gains_rate or 0.0)
        self.cash += amount - fee - cg_tax
        pos.shares -= shares
        if pos.shares <= 1e-9:
            del self.positions[ticker]
        extra = []
        if fee:
            extra.append(f"fee {fee:.2f}")
        if cg_tax:
            extra.append(f"IR ganho {cg_tax:.2f}")
        trade = Trade(
            id=str(uuid4()),
            ts=ts or utcnow_iso(),
            side="sell",
            ticker=ticker,
            shares=shares,
            price=exec_price,
            amount=amount,
            note=f"{note} ({', '.join(extra)})" if extra else note,
        )
        self.trades.append(trade)
        self._touch()
        return trade

    def shares_at(self, ticker: str, as_of: datetime | str | pd.Timestamp) -> float:
        """Quantidade de ações do ticker na data (pelo histórico de ordens)."""
        ticker = normalize_ticker(ticker)
        as_ts = pd.Timestamp(as_of)
        if as_ts.tzinfo is not None:
            as_ts = as_ts.tz_localize(None)
        shares = 0.0
        for t in self.trades:
            if normalize_ticker(t.ticker) != ticker:
                continue
            t_ts = pd.Timestamp(t.ts)
            if t_ts.tzinfo is not None:
                t_ts = t_ts.tz_localize(None)
            if t_ts <= as_ts:
                if t.side == "buy":
                    shares += float(t.shares)
                elif t.side == "sell":
                    shares -= float(t.shares)
        return max(0.0, shares)

    def _dividend_keys(self) -> set[str]:
        keys: set[str] = set()
        for d in self.dividends:
            day = (d.ex_date or (d.ts[:10] if d.ts else "")).strip()
            if day:
                keys.add(f"{normalize_ticker(d.ticker)}|{day}")
        return keys

    def credit_dividend(
        self,
        ticker: str,
        amount_per_share: float,
        ts: str | None = None,
        note: str = "",
        *,
        shares: float | None = None,
        ex_date: str | None = None,
        skip_if_duplicate: bool = True,
        tax_rate: float = 0.0,
    ) -> DividendEvent | None:
        """Credita dividendo em caixa.

        Se ``shares`` for informado, usa essa quantidade (ex.: posição na data-ex).
        Caso contrário, usa a posição atual.

        ``tax_rate`` aplica retenção de imposto fracional (ex.: 0.15 = IR sobre
        JCP/FII) e registra o valor líquido creditado. Default 0 = sem imposto.
        """
        ticker = normalize_ticker(ticker)
        if amount_per_share <= 0:
            return None

        day = (ex_date or (ts[:10] if ts else "") or utcnow_date())[:10]
        if skip_if_duplicate and f"{ticker}|{day}" in self._dividend_keys():
            return None

        if shares is None:
            pos = self.positions.get(ticker)
            if pos is None:
                return None
            qty = float(pos.shares)
        else:
            qty = float(shares)
        if qty <= 1e-12:
            return None

        gross = qty * amount_per_share
        retention = gross * float(tax_rate) if tax_rate else 0.0
        total = gross - retention
        self.cash += total
        event = DividendEvent(
            id=str(uuid4()),
            ts=ts or utcnow_iso(),
            ticker=ticker,
            amount=total,
            shares=qty,
            note=note if not retention else f"{note} (IR retido {retention:.2f})",
            amount_per_share=float(amount_per_share),
            ex_date=day,
        )
        self.dividends.append(event)
        self._touch()
        return event

    def rebalance_to_weights(
        self,
        weights: dict[str, float],
        prices: dict[str, float],
        buckets: dict[str, str] | None = None,
        note: str = "rebalance",
        ts: str | None = None,
        *,
        fee_bps: float = 0.0,
        slippage_bps: float = 0.0,
        capital_gains_rate: float = 0.0,
    ) -> list[Trade]:
        """Rebalanceia para pesos alvo usando valor total (caixa + posições)."""
        buckets = buckets or {}
        total_value = self.total_value(prices)
        if total_value <= 0:
            return []

        # Vende o que não está no alvo ou está acima
        trades: list[Trade] = []
        target_tickers = {normalize_ticker(t) for t in weights}
        for t in list(self.positions.keys()):
            if t not in target_tickers:
                pos = self.positions[t]
                px = prices.get(t)
                if px and pos.shares > 0:
                    trades.append(
                        self.sell(
                            t,
                            pos.shares,
                            px,
                            note=f"{note}:sair",
                            ts=ts,
                            fee_bps=fee_bps,
                            slippage_bps=slippage_bps,
                            capital_gains_rate=capital_gains_rate,
                        )
                    )

        # Ajusta cada alvo
        for t, w in weights.items():
            t = normalize_ticker(t)
            px = prices.get(t)
            if not px or px <= 0 or w <= 0:
                continue
            target_value = total_value * w
            current_shares = self.positions[t].shares if t in self.positions else 0.0
            current_value = current_shares * px
            delta_value = target_value - current_value
            # micro-ajuste: 0,1% do patrimônio ou R$ 1 (o maior)
            threshold = max(total_value * 0.001, 1.0)
            if abs(delta_value) < threshold:
                continue
            shares = abs(delta_value) / px
            bucket = buckets.get(t, "core")
            if delta_value > 0:
                exec_price = px * (1.0 + slippage_bps / 10_000.0)
                fee_mult = 1.0 + fee_bps / 10_000.0
                unit = exec_price * fee_mult
                max_shares = self.cash / unit if unit > 0 else 0
                shares = min(shares, max_shares)
                if shares * exec_price >= 1:
                    try:
                        trades.append(
                            self.buy(
                                t,
                                shares,
                                px,
                                bucket=bucket,
                                note=note,
                                ts=ts,
                                fee_bps=fee_bps,
                                slippage_bps=slippage_bps,
                            )
                        )
                    except ValueError:
                        continue
            else:
                pos = self.positions.get(t)
                if pos:
                    shares = min(shares, pos.shares)
                    if shares * px >= 1:
                        trades.append(
                            self.sell(
                                t,
                                shares,
                                px,
                                note=note,
                                ts=ts,
                                fee_bps=fee_bps,
                                slippage_bps=slippage_bps,
                                capital_gains_rate=capital_gains_rate,
                            )
                        )
        return trades

    def total_value(self, prices: dict[str, float]) -> float:
        value = self.cash
        for t, pos in self.positions.items():
            px = prices.get(t, pos.avg_price)
            value += pos.shares * px
        return value

    def holdings_frame(self, prices: dict[str, float] | None = None) -> pd.DataFrame:
        prices = prices or {}
        rows = []
        for t, pos in self.positions.items():
            px = prices.get(t, pos.avg_price)
            mv = pos.shares * px
            cost = pos.shares * pos.avg_price
            rows.append(
                {
                    "ticker": t,
                    "shares": pos.shares,
                    "avg_price": pos.avg_price,
                    "price": px,
                    "market_value": mv,
                    "cost": cost,
                    "pnl": mv - cost,
                    "pnl_pct": (mv / cost - 1) if cost else 0,
                    "bucket": pos.bucket,
                }
            )
        df = pd.DataFrame(rows)
        if not df.empty:
            total = df["market_value"].sum() + self.cash
            df["weight"] = df["market_value"] / total if total else 0
            df = df.sort_values("market_value", ascending=False)
        return df

    def summary(self, prices: dict[str, float] | None = None) -> dict[str, Any]:
        prices = prices or {}
        equity = self.total_value(prices)
        invested = sum(
            p.shares * prices.get(t, p.avg_price) for t, p in self.positions.items()
        )
        div_total = sum(d.amount for d in self.dividends)
        return {
            "name": self.name,
            "cash": self.cash,
            "invested": invested,
            "equity": equity,
            "initial_cash": self.initial_cash,
            "pnl": equity - self.initial_cash,
            "pnl_pct": (equity / self.initial_cash - 1) if self.initial_cash else 0,
            "dividends_received": div_total,
            "n_positions": len(self.positions),
            "n_trades": len(self.trades),
            "updated_at": self.updated_at,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "cash": self.cash,
            "initial_cash": self.initial_cash,
            "currency": self.currency,
            "positions": {k: asdict(v) for k, v in self.positions.items()},
            "trades": [asdict(t) for t in self.trades],
            "dividends": [asdict(d) for d in self.dividends],
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PaperPortfolio:
        positions = {
            k: Position(**v) for k, v in (data.get("positions") or {}).items()
        }
        trades = [Trade(**{k: t[k] for k in t if k in Trade.__dataclass_fields__}) for t in data.get("trades") or []]
        dividends = []
        for d in data.get("dividends") or []:
            # Compatível com JSONs antigos (sem ex_date / amount_per_share)
            payload = {k: d[k] for k in d if k in DividendEvent.__dataclass_fields__}
            if "ex_date" not in payload or not payload.get("ex_date"):
                ts = str(payload.get("ts") or "")
                payload["ex_date"] = ts[:10] if len(ts) >= 10 else ""
            if "amount_per_share" not in payload:
                sh = float(payload.get("shares") or 0)
                amt = float(payload.get("amount") or 0)
                payload["amount_per_share"] = (amt / sh) if sh > 0 else 0.0
            dividends.append(DividendEvent(**payload))
        return cls(
            name=data.get("name", "paper-main"),
            cash=float(data.get("cash", 0)),
            initial_cash=float(data.get("initial_cash", data.get("cash", 0))),
            currency=data.get("currency", "BRL"),
            positions=positions,
            trades=trades,
            dividends=dividends,
            created_at=data.get("created_at", utcnow_iso()),
            updated_at=data.get("updated_at", utcnow_iso()),
        )


def portfolio_path(name: str = "paper-main") -> Path:
    PORTFOLIO_DIR.mkdir(parents=True, exist_ok=True)
    safe = "".join(c for c in name if c.isalnum() or c in "-_") or "paper-main"
    return PORTFOLIO_DIR / f"{safe}.json"


def list_portfolios() -> list[str]:
    """Nomes das carteiras paper salvas em disco (conteúdo de data/portfolio/)."""
    PORTFOLIO_DIR.mkdir(parents=True, exist_ok=True)
    if not PORTFOLIO_DIR.exists():
        return []
    names = [p.stem for p in PORTFOLIO_DIR.glob("*.json")]
    # "paper-main" primeiro se existir (estabilidade para quem não mexeu)
    names.sort(key=lambda n: (n != "paper-main", n.lower()))
    return names or []


def delete_portfolio(name: str) -> bool:
    """Remove uma carteira salva. Retorna False se não existir."""
    if name == "paper-main":
        raise ValueError("A carteira padrão 'paper-main' não pode ser apagada.")
    path = portfolio_path(name)
    if not path.exists():
        return False
    path.unlink()
    return True


def save_portfolio(portfolio: PaperPortfolio) -> Path:
    path = portfolio_path(portfolio.name)
    path.write_text(json.dumps(portfolio.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def load_portfolio(name: str = "paper-main", create_if_missing: bool = True) -> PaperPortfolio:
    path = portfolio_path(name)
    if path.exists():
        return PaperPortfolio.from_dict(json.loads(path.read_text(encoding="utf-8")))
    if create_if_missing:
        p = PaperPortfolio.create(name=name)
        save_portfolio(p)
        return p
    raise FileNotFoundError(path)
