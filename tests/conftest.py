import pytest

from move_money import MoneyService


@pytest.fixture
def database_path(tmp_path):
    return tmp_path / "accounts.db"


@pytest.fixture
def service(database_path):
    return MoneyService(database_path)
