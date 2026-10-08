# Move the Money

A small Python + SQLite library for opening funded accounts, transferring money,
reading current balances, and reading transaction histories. Business rules live
in `MoneyService`; the executable demo uses that same public interface.

## Run and test

Requires Python 3.12+ with SQLite 3.37.0+ (`STRICT` tables). Verified combinations
are Python 3.14.7 / SQLite 3.53.4 and a fresh Python 3.12.8 / SQLite 3.45.3
environment. There are no runtime dependencies; pytest 9.1.1 is the development
dependency.

From the repository folder:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install --no-cache-dir -e '.[dev]'
.venv/bin/python scripts/demo.py
.venv/bin/python -m pytest -q
```

The demo creates and removes a fresh temporary database. It opens 10,000/0 CAD-cent
accounts, transfers 8,000, replays the original receipt, and rejects a changed
payload, an overspend, and a money string without changing state. It finishes with
balances 2,000/8,000, conserved total=10,000, and one transfer appearing as outgoing
and incoming in the two histories. Unexpected outcomes fail the demo.

Run the required competing-transfer proof separately:

```sh
.venv/bin/python -m pytest -q tests/test_transfer_concurrency.py::test_competing_transfers_cannot_overspend
```

It overlaps two different-key 8,000-cent requests from A=10,000 to B=C=0. It
requires one success, one `InsufficientFunds`, A=2,000, destination balances
8,000/0, total=10,000, one persisted transfer, and matching histories. Independent
connections and bounded coordination verify a held writer and the second caller's
actual `BEGIN IMMEDIATE` attempt. Lock errors or missing outcomes fail the test.

Further focused checks:

```sh
.venv/bin/python -m pytest -q tests/test_transfer_failures.py
.venv/bin/python -m pytest -q tests/test_transfer_processes.py
.venv/bin/python scripts/check_test_sensitivity.py
```

The clean-checkout suite passed all 372 cases. Selected sensitivity checks detected
8/8 deliberate mutations in disposable copies, with passing unmodified controls
and unchanged actual source. See [TEST_PLAN.md](TEST_PLAN.md) for mapped evidence
and [WORKING_NOTES.md](WORKING_NOTES.md) for exact executed checkpoints.

## Public contract

```python
from move_money import MoneyService

service = MoneyService("money.db")  # A local file, not :memory:.
sender = service.open_account(10_000)
recipient = service.open_account(0)
receipt = service.transfer("payment-1", sender.account_id, recipient.account_id, 8000)
balance = service.get_balance(sender.account_id)  # 2000 cents
history = service.get_history(sender.account_id)  # One outgoing entry
```

All amounts are plain Python integers in CAD cents. Opening balances accept
`0..2**63-1`, transfers `1..2**63-1`, and account IDs `1..2**63-1`. Strings, floats,
booleans, wrappers/subclasses, conversion objects, and out-of-range values raise
`InvalidInput`. Valid but absent accounts raise `AccountNotFound`; new self-transfers
are invalid. Insufficient funds and recipient overflow raise `InsufficientFunds`
and `BalanceOverflow`, preserving balances and transfer records.

Transfer keys are global within the database: nonblank plain strings, valid UTF-8,
without NUL characters, compared exactly without trimming or normalization.

- Same key and details: return the original frozen receipt without another movement,
  even after balances change or the database is reopened.
- Same committed key and changed valid details: `TransferConflict`, before current
  funds/existence/self-transfer checks. Input type/range validation still runs first.
- Failed uncommitted attempt: no receipt is stored; the key remains available.

**Current balances are stored and updated on every successful transfer.**
`get_balance` reads that stored value; it does not sum history. Opening plus total
incoming minus total outgoing is a reconciliation check. Opening funding is stored
separately and is not a transfer-history entry. History contains successful
transfers only, ordered by persisted sequence; each frozen entry contains the
canonical receipt and its incoming/outgoing direction. Empty history returns `[]`.
Balance and history are separate operations, each reading committed state.

## How the four rules are enforced

| Required rule | Mechanism and evidence |
|---|---|
| Never negative | Writer transaction before decisions, conditional debit, stored bounds; exact-spending and thread/process competing-transfer tests |
| All or nothing | Debit, credit, and receipt in one explicit transaction; injected failures, busy-commit rollback, abrupt pre-commit exits, and reader visibility tests |
| Applied at most once | Unique persisted key and replay before business checks; overlapping retries/conflicts and post-commit exit followed by replay |
| Exact amounts | Plain integer validation, STRICT bounded integer columns, overflow checks; one-cent/max cases and independent seeded ledger models |

Each operation owns its connection. Writes use SQL `BEGIN IMMEDIATE`, `COMMIT`, and
`ROLLBACK`; success returns after commit. Connections use `autocommit=True`, enabled
foreign keys, disabled dirty reads, and a five-second lock timeout. SQLite errors
propagate; there is no automatic retry loop. An uncertain caller retries the same
key and payload. SQLite STRICT allows lossless numeric-string conversion through
direct SQL, so public validation is essential. External SQL writes are not a
supported money API.

SQLite permits one write transaction at a time across connections/processes on the
same local file. This makes the serialization boundary explicit, with write
throughput as the tradeoff. Readers can delay a commit; a timeout causes rollback
and a storage error. See [SQLite transactions](https://www.sqlite.org/lang_transaction.html).

## Scope, limits, and next step

The assignment accepts a library. UI, HTTP API, authentication, signup, deployment,
client/bank ownership, and multi-currency conversion were excluded. File access
depends on operating-system permissions. History has no pagination/timestamps;
schema changes have no versioned migration tool.

Evidence covers finite controlled schedules on those two runtime combinations.
It does not establish every execution, sustained-load performance, physical power-loss or disk
corruption recovery, backup procedures, or all supported runtime versions. Abrupt
process exits are not physical power-loss simulations.

The next engineering hour would vary the controlled competing-transfer winner
order and generated ledger seeds, adding a regression for any concrete finding.
The remaining submission step is the author's review of personal/time fields in
[BUILD_LOG.md](BUILD_LOG.md).
See [SUBMISSION.md](SUBMISSION.md) for delivery checks and the short demo outline.
