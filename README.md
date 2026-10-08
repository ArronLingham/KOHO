# Move the Money

A Python + SQLite library for the KOHO assignment. **Stage 2:** open funded
accounts, transfer money, retrieve balances, and retrieve incoming/outgoing history.
Transfers have persisted retry identity and stable receipts. The test suite covers
the four required invariants, including overlapping transfers competing for funds.

## Setup and tests

Requires Python 3.12+ with SQLite 3.37.0+ (for `STRICT` tables).
The runtime uses only Python's standard library; pytest is a development dependency.

From the repository folder:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install --no-cache-dir -e '.[dev]'
.venv/bin/python -m pytest -q
```

## Account, transfer, retry, and history example

```sh
.venv/bin/python - <<'PY'
from pathlib import Path
from tempfile import TemporaryDirectory
from move_money import MoneyService

with TemporaryDirectory() as directory:
    service = MoneyService(Path(directory) / "example.db")
    funded = service.open_account(10_000)
    empty = service.open_account(0)
    receipt = service.transfer("example-payment", funded.account_id, empty.account_id, 8000)
    replay = service.transfer("example-payment", funded.account_id, empty.account_id, 8000)
    assert replay == receipt
    print("funded:", service.get_balance(funded.account_id), "cents")
    print("empty:", service.get_balance(empty.account_id), "cents")
    print("receipt:", receipt)
    print("sender history:", service.get_history(funded.account_id))
    print("recipient history:", service.get_history(empty.account_id))
PY
```

The balances printed are 2,000 and 8,000 cents. The first receipt has sequence 1;
the replay adds no transfer or history entry. Each account has one history entry
referring to that same receipt, with its own incoming/outgoing direction.

## Behavior contract

All amounts are plain Python integers in CAD cents. Opening balances accept
`0..2**63-1`; transfer amounts accept `1..2**63-1`. Account IDs are generated positive
plain integers in the same signed range. Booleans, numeric strings, floats, numeric
wrappers/subclasses, conversion objects, and out-of-range values raise `InvalidInput`.
A valid but missing account raises `AccountNotFound`; a new self-transfer is invalid.

`transfer(transfer_id, sender_id, recipient_id, amount_cents)` returns a frozen
`TransferReceipt` containing the persisted sequence and request details. A key is a
nonblank plain string containing valid UTF-8 text without NUL characters. Keys are
global within the database and compared exactly; whitespace is not trimmed and text
is not normalized. Strings are appropriate for keys and paths, never money or IDs.

- Same key and same details: return the original receipt without another movement,
  even after balances change or the database is reopened.
- Same committed key and different valid details: raise `TransferConflict` before
  current funds, account existence, or self-transfer checks. Input type/range checks
  still run first.
- Failed uncommitted attempt: leave no transfer record and keep the key available.
- Insufficient sender funds: raise `InsufficientFunds`. Recipient overflow: raise
  `BalanceOverflow`. Both preserve every balance and transfer record.

`get_history(account_id)` returns a list of frozen `HistoryEntry` values, each with
`transfer` and `direction` (`incoming` or `outgoing`), ordered by persisted sequence.
Only successful transfers appear. Opening funding is separate; reconcile balances
as opening plus incoming minus outgoing. Existing empty histories return `[]`.

## Transactions and invariant evidence

| Invariant | Enforcement and executable evidence |
|---|---|
| Never negative | Writer lock before reads; conditional debit; stored nonnegative checks; exact spending, insufficient funds, and controlled competing-transfer test |
| All or nothing | One explicit transaction for debit, credit, and receipt; injected failures after debit/credit/insertion and at commit restore complete state |
| Apply at most once | Unique persisted key; committed lookup before business checks; sequential/concurrent replay, payload conflicts, and discarded-response/reopen checks |
| Exact amounts | Plain integer inputs and STRICT integer storage with bounds; one-cent/max/overflow tests and seeded ledger comparisons with exact totals |

Each operation owns a connection to a local database file. Writes acquire SQL
`BEGIN IMMEDIATE` before state-dependent reads; debit, credit, and canonical transfer
record commit together. Success returns only after SQL `COMMIT`; exceptions roll
back an active transaction. Python connections use `autocommit=True`, foreign keys
enabled, dirty reads disabled, and a five-second lock timeout. SQLite storage errors
propagate to callers; they are not converted into insufficient funds or success.
There is no automatic retry loop. A caller uncertain about success retries the same
key and payload.

SQLite STRICT permits lossless numeric-string conversion through direct SQL. The
public API rejects those strings explicitly. Database constraints are a second
defense; they do not make arbitrary external database writes a supported money API.
Opening accounts introduces funding; transfers conserve the existing total.

SQLite permits one writer at a time, including across processes using the same
local database file. The overlap tests hold the first real writer transaction and
trace the second caller's `BEGIN IMMEDIATE` attempt before releasing the first.
Each worker creates its own connection. Unexpected exceptions, lock errors, missing
outcomes, and timeouts fail these tests. This exercises contention at the writer
boundary, not simultaneous execution inside two writer transactions.

## Limits and next steps

This is a local, single-currency assignment library. No UI, HTTP API, authentication,
signup, deployment, client/bank ownership model, or multi-currency conversion is
included. Protect database-file access through the host operating system. Receipts
have a stable sequence, not timestamps, and history is currently returned in full.

Tests use the observed local Python/SQLite runtime and finite controlled schedules.
Physical power loss, disk corruption/recovery, backups, process-level transfer races,
and a runtime-version matrix have not been established. A reader can delay a commit;
if contention outlasts the timeout, the operation raises a storage error and rolls
back. Existing database schema changes are not managed by a versioned migration tool.

Many simultaneous writers or shared server access would justify PostgreSQL. Account
count alone is not the deciding factor; SQLite can handle substantial local datasets.
See the [SQLite usage guidance](https://www.sqlite.org/whentouse.html). The selected
backend remains SQLite; PostgreSQL has not been implemented or benchmarked here.

Next, after user review: complete any further Stage 3 evidence requested, then the
bounded critique and final submission documentation. No later stage or publishing
action runs automatically. See [WORKING_NOTES.md](WORKING_NOTES.md) for actual
checkpoints and [TEST_PLAN.md](TEST_PLAN.md) for mapped evidence and remaining limits.

## Verification scope

The current suite contains 363 passing cases on the observed runtime: account and
transfer validation, generated account/transfer models, history reconciliation,
real SQLite rollback/lock/commit failures, overlapping transfer/retry/conflict
attempts, concurrent account creation, and account process-exit checks.

Run the assignment's named competing-transfer check independently:

```sh
.venv/bin/python -m pytest -q tests/test_transfer_concurrency.py::test_competing_transfers_cannot_overspend
```

It requires A=10,000, B=C=0; two different keys requesting 8,000 each; one success,
one insufficient-funds result, A=2,000, destinations 8,000/0, conserved total=10,000,
one persisted transfer, and consistent histories.

To check that selected tests detect intentionally weakened code in disposable copies:

```sh
.venv/bin/python scripts/check_test_sensitivity.py
```

This experiment checks seven selected mutations, including failed-debit handling,
committed replay, and rollback after transfer failure. Each unmodified control must
pass, each named mutated test must fail, and actual source hashes must remain
unchanged. Disposable copies are removed. These are planned test experiments, not
accidental AI mistakes or proof of every possible fault.
