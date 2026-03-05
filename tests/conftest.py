"""
Pytest configuration and shared fixtures.
"""
import pytest


@pytest.fixture
def session_id() -> str:
    """A stable session ID for tests."""
    return "test_session_001"


@pytest.fixture
def property_address() -> str:
    return "742 Evergreen Terrace, Austin, TX 78701"


@pytest.fixture
def listing_price() -> float:
    return 485_000.0


@pytest.fixture
def buyer_budget() -> float:
    return 460_000.0


@pytest.fixture
def seller_minimum() -> float:
    return 445_000.0
