import sqlite3

import pytest

from move_money.storage import _connection


def _stored_transfers(connection):
    return [tuple(row) for row in connection.execute("SELECT * FROM transfers ORDER BY sequence")]


@pytest.mark.parametrize("amount", [0, -1, 1.5, "not-a-number", None])
def test_database_rejects_invalid_transfer_amounts(service, database_path, amount):
    service.open_account(100)
    service.open_account(0)
    with _connection(database_path) as connection:
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO transfers (transfer_id, sender_id, recipient_id, amount_cents) "
                "VALUES ('invalid', 1, 2, ?)", (amount,),
            )
        assert _stored_transfers(connection) == []
    assert [service.get_balance(1), service.get_balance(2)] == [100, 0]


@pytest.mark.parametrize("sender,recipient", [(1, 1), (999, 2), (1, 999)])
def test_database_rejects_self_or_nonexistent_transfer_accounts(
    service, database_path, sender, recipient,
):
    service.open_account(100)
    service.open_account(0)
    with _connection(database_path) as connection:
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO transfers (transfer_id, sender_id, recipient_id, amount_cents) "
                "VALUES ('invalid', ?, ?, 1)", (sender, recipient),
            )
        assert _stored_transfers(connection) == []


def test_database_unique_key_cannot_replace_a_committed_receipt(service, database_path):
    service.open_account(100)
    service.open_account(0)
    service.transfer("unique", 1, 2, 10)
    with _connection(database_path) as connection:
        before = _stored_transfers(connection)
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO transfers (transfer_id, sender_id, recipient_id, amount_cents) "
                "VALUES ('unique', 1, 2, 20)"
            )
        assert _stored_transfers(connection) == before
    assert [service.get_balance(1), service.get_balance(2)] == [90, 10]
