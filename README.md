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

## What we chose not to build

The submission focuses on the four requested library operations: opening an
account, transferring money, reading a balance, and reading transaction history.
The following features are outside this build's scope:

| Feature | What it is and why it was omitted |
|---|---|
| Web interface | Screens and forms for managing accounts and transfers. The brief accepts a tested library, which we demonstrate with a script. |
| HTTP API | Network endpoints that other applications can call. The operations are exposed directly as Python methods. |
| Interactive CLI | Terminal subcommands for entering individual requests. The existing demo runs a predefined walkthrough; a command parser was deferred. |
| Authentication and signup | Identifying users, logging them in, and registering them. The brief explicitly excludes these flows. |
| Deployment | Hosting and operating a running service. This assignment runs locally and requires no deployment. |
| Client/bank ownership and permissions | Associating accounts with clients or banks and controlling who may access them. We kept the model limited to accounts and transfers. |
| Multiple currencies and exchange | Currency-specific balances and conversion between currencies. This build uses CAD cents. |
| Fees and reversals | Charging for a transfer or recording a compensating transfer to undo one. Their additional business rules were outside the brief. |
| History pagination and timestamps | Returning history in smaller pages and recording when transfers occurred. History currently returns all successful transfers in persisted sequence order. |
| Combined balance/history snapshot | Reading both results at one shared database snapshot. They are separate operations in the brief and can observe different committed moments. |
| Schema migration tooling | Versioned changes to an existing database schema. This build creates its initial tables and indexes but has no upgrade framework. |
| Production operations | Backup/restore procedures, operational monitoring, and measured sustained-load performance. These were outside the local exercise; physical power-loss and corruption recovery are not established by our tests. |
| Automatic storage-error retries | Automatically resubmitting an operation after a database lock or storage error. Errors propagate to the caller, which can retry an uncertain transfer with the same key and details. |

## What we would do next

Proposed next steps, in priority order:

1. **Broaden correctness verification.** Extend the existing two-request
   concurrency tests to larger groups of competing requests and longer generated
   transfer sequences. Check balances, histories, retry outcomes, and conserved
   funds after each group, adding a regression test for any concrete finding.
2. **Add a small CLI.** Provide `open`, `transfer`, `balance`, and `history`
   commands that call the existing library, use a selected persistent database,
   and print clear results and errors. Test separate command invocations, invalid
   arguments, and retries. Dollar input could be parsed exactly into cents while
   retaining integer arithmetic in the service.
3. **Assess larger-service requirements if the scope grows.** Measure write
   contention before deciding whether to move to PostgreSQL. Define client/bank
   ownership, access rules, and backup/restore requirements for that larger scope.
   These are future design decisions, not features included in this submission.
