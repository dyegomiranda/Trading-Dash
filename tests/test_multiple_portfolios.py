"""Pacote: múltiplas carteiras paper (registro, criação, exclusão)."""

from __future__ import annotations

import pytest

from src.portfolio.paper import (
    PaperPortfolio,
    delete_portfolio,
    list_portfolios,
    load_portfolio,
    portfolio_path,
    save_portfolio,
)


@pytest.fixture(autouse=True)
def _isolate_portfolio_dir(tmp_path, monkeypatch):
    """Testes de carteira não devem tocar nas carteiras reais do usuário."""
    monkeypatch.setattr("src.portfolio.paper.PORTFOLIO_DIR", tmp_path)
    monkeypatch.setattr("src.config.PORTFOLIO_DIR", tmp_path)
    yield
    # limpa o diretório isolado
    import shutil

    if tmp_path.exists():
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_load_creates_default_when_missing():
    p = load_portfolio("paper-main")
    assert p.name == "paper-main"
    assert list_portfolios() == ["paper-main"]
    assert portfolio_path("paper-main").exists()


def test_switch_creates_and_lists_multiple():
    save_portfolio(PaperPortfolio.create(name="paper-main"))
    save_portfolio(PaperPortfolio.create(name="meta-2030"))
    save_portfolio(PaperPortfolio.create(name="teste-rapido"))
    names = list_portfolios()
    # "paper-main" vem primeiro (estável), depois alfabético
    assert names[0] == "paper-main"
    assert set(names) == {"paper-main", "meta-2030", "teste-rapido"}


def test_each_portfolio_has_own_cash():
    a = PaperPortfolio.create(name="a", cash=1000.0)
    b = PaperPortfolio.create(name="b", cash=9000.0)
    save_portfolio(a)
    save_portfolio(b)
    loaded_a = load_portfolio("a")
    loaded_b = load_portfolio("b")
    assert loaded_a.cash == 1000.0
    assert loaded_b.cash == 9000.0
    # isolar: compra em "a" não afeta "b"
    loaded_a.buy("ITUB4", 5, 30.0)
    save_portfolio(loaded_a)
    assert float(load_portfolio("a").positions["ITUB4"].shares) == 5.0
    assert load_portfolio("b").positions == {}


def test_delete_portfolio():
    save_portfolio(PaperPortfolio.create(name="descartavel"))
    assert "descartavel" in list_portfolios()
    assert delete_portfolio("descartavel") is True
    assert "descartavel" not in list_portfolios()
    # apagar de novo → False (não existe)
    assert delete_portfolio("descartavel") is False


def test_cannot_delete_default():
    save_portfolio(PaperPortfolio.create(name="paper-main"))
    with pytest.raises(ValueError):
        delete_portfolio("paper-main")
    assert "paper-main" in list_portfolios()


def test_portfolio_path_sanitizes_name():
    # espaços e símbolos são removidos (só alnum + `-`/`_` sobrevivem)
    assert portfolio_path("guia do investidor").name == "guiadoinvestidor.json"
    assert portfolio_path("página!!").name == "página.json"


def test_delete_missing_returns_false():
    assert delete_portfolio("nao-existe") is False