# Move the Money

## How to run

Requires Python 3.12+ with SQLite 3.37.0+.

From the repository folder, create an environment and install the project and test dependencies:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install --no-cache-dir -e '.[dev]'
```

Run the demonstration:

```sh
.venv/bin/python scripts/demo.py
```

The demo opens accounts, transfers money, reads balances and histories, and checks
retries and rejected requests. It creates a temporary database and removes it when
finished.

## How to run tests

After completing the setup above, run the full test suite:

```sh
.venv/bin/python -m pytest -q
```

Run the competing-transfer test on its own:

```sh
.venv/bin/python -m pytest -q tests/test_transfer_concurrency.py::test_competing_transfers_cannot_overspend
```

Run the test-sensitivity checks, which introduce deliberate defects in disposable
copies and check whether the selected tests detect them:

```sh
.venv/bin/python scripts/check_test_sensitivity.py
```
