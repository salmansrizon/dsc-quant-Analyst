"""Model-layer invariants (#62). The interface rejects nonsense before it can
reach a query — a zero buy_price is a SQL division by zero in the P&L formula."""
import pytest
from pydantic import ValidationError

from backend.models import PortfolioAdd, PortfolioUpdate


def test_portfolio_add_rejects_a_zero_buy_price():
    with pytest.raises(ValidationError):
        PortfolioAdd(symbol="GP", buy_price=0, quantity=10)


def test_portfolio_add_rejects_a_negative_buy_price():
    with pytest.raises(ValidationError):
        PortfolioAdd(symbol="GP", buy_price=-5, quantity=10)


def test_portfolio_add_rejects_non_positive_quantity():
    with pytest.raises(ValidationError):
        PortfolioAdd(symbol="GP", buy_price=100, quantity=0)


def test_portfolio_add_accepts_a_valid_holding():
    p = PortfolioAdd(symbol="GP", buy_price=257.5, quantity=10)
    assert p.buy_price == 257.5


def test_portfolio_update_rejects_a_zero_buy_price():
    with pytest.raises(ValidationError):
        PortfolioUpdate(buy_price=0)
