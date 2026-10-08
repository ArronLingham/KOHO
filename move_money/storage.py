"""Connection settings and the explicit write-transaction boundary."""

from contextlib import contextmanager
from pathlib import Path
import sqlite3
from collections.abc import Iterator

MAX_CENTS = 2**63 - 1
LOCK_TIMEOUT_SECONDS = 5.0

_ACCOUNT_SCHEMA = f"""
CREATE TABLE IF NOT EXISTS accounts (
    account_id INTEGER PRIMARY KEY CHECK (account_id > 0),
    starting_balance_cents INTEGER NOT NULL
        CHECK (starting_balance_cents BETWEEN 0 AND {MAX_CENTS}),
    balance_cents INTEGER NOT NULL
        CHECK (balance_cents BETWEEN 0 AND {MAX_CENTS})
) STRICT
"""

_TRANSFER_SCHEMA = f"""
CREATE TABLE IF NOT EXISTS transfers (
    sequence INTEGER PRIMARY KEY CHECK (sequence > 0),
    transfer_id TEXT NOT NULL UNIQUE
        CHECK (length(trim(transfer_id)) > 0 AND instr(transfer_id, char(0)) = 0),
    sender_id INTEGER NOT NULL REFERENCES accounts(account_id),
    recipient_id INTEGER NOT NULL REFERENCES accounts(account_id),
    amount_cents INTEGER NOT NULL CHECK (amount_cents BETWEEN 1 AND {MAX_CENTS}),
    CHECK (sender_id != recipient_id)
) STRICT
"""


@contextmanager
def _connection(database_path: Path) -> Iterator[sqlite3.Connection]:
    if sqlite3.sqlite_version_info < (3, 37, 0):
        raise RuntimeError("SQLite 3.37.0 or newer is required for STRICT tables")

    connection = sqlite3.connect(
        database_path,
        autocommit=True,
        timeout=LOCK_TIMEOUT_SECONDS,
    )
    try:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA read_uncommitted = OFF")
        yield connection
    finally:
        connection.close()


@contextmanager
def _write_transaction(connection: sqlite3.Connection) -> Iterator[None]:
    # Acquire SQLite's writer transaction before state-dependent reads.
    connection.execute("BEGIN IMMEDIATE")
    try:
        yield
        # With autocommit=True, use SQL, not Connection.commit()/rollback().
        connection.execute("COMMIT")
    except BaseException:
        if connection.in_transaction:
            connection.execute("ROLLBACK")
        raise


def _initialize(database_path: Path) -> None:
    with _connection(database_path) as connection:
        with _write_transaction(connection):
            connection.execute(_ACCOUNT_SCHEMA)
            connection.execute(_TRANSFER_SCHEMA)
            connection.execute(
                "CREATE INDEX IF NOT EXISTS transfers_sender "
                "ON transfers (sender_id, sequence)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS transfers_recipient "
                "ON transfers (recipient_id, sequence)"
            )
