# Move the Money

A Python + SQLite library for the KOHO assignment. **Stage 1 only:** account
creation and balance lookup are implemented. Transfers, retry handling, and
transaction history are pending; the four transfer invariants are not yet verified.

## Setup and tests

Requires Python 3.12+ with SQLite 3.37.0+ (for `STRICT` tables).
The runtime uses only Python's standard library; pytest is a development dependency.

From the repository folder:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install --no-cache-dir -e '.[dev]'
.venv/bin/python -m pytest -q
```

## Account example

```sh
.venv/bin/python - <<'PY'
from pathlib import Path
from tempfile import TemporaryDirectory
from move_money import MoneyService

with TemporaryDirectory() as directory:
    service = MoneyService(Path(directory) / "example.db")
    funded = service.open_account(10_000)
    empty = service.open_account(0)
    print("funded:", service.get_balance(funded.account_id), "cents")
    print("empty:", service.get_balance(empty.account_id), "cents")
PY
```

All amounts are integer CAD cents. Opening balances must be between zero and
`2**63 - 1`, inclusive. Booleans, floats, strings, negative values, and out-of-range
values raise `InvalidInput`. Account identifiers are generated positive integers;
looking up a valid but missing identifier raises `AccountNotFound`.

Each operation opens and closes its own connection to a local file. Account creation
uses SQL `BEGIN IMMEDIATE` and a single SQL `COMMIT`; exceptions roll back the active
transaction. Connections use `autocommit=True`, foreign keys enabled, dirty reads
disabled, and a five-second lock timeout. Storage errors remain explicit errors.
Strict columns and database checks defend stored amounts as well as input validation.

SQLite permits one writer at a time. The next stage will place the complete transfer
decision, debit, credit, and successful transfer record inside this same boundary.
Opening funding adds money to the system; conservation will apply to transfers.

No UI, HTTP API, authentication, signup, or deployment is included. Next: implement
atomic transfers, stable receipts, retry/conflict handling, and successful-transfer
history, then verify competing transfers using independent connections.

See [WORKING_NOTES.md](WORKING_NOTES.md) for factual development checkpoints.

## Verification scope

The expanded Stage 1 suite includes adversarial inputs, generated account request
sequences, SQLite lock/commit failures, rollback, concurrent account creation, and
child-process exit before/after commit. Transfers and their four invariants remain
pending. See [TEST_PLAN.md](TEST_PLAN.md) for the evidence matrix and acceptance plan.

To check that selected tests detect intentionally weakened code in disposable copies:

```sh
.venv/bin/python scripts/check_test_sensitivity.py
```

This experiment checks four selected mutations and preserves actual source files.
It is not an accidental AI mistake or proof of every possible fault.
