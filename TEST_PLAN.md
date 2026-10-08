# Correctness evidence and remaining limits

The original assignment brief governs requirements. All four required operations
are implemented. Evidence includes separate processes, abrupt transfer exits, and
uncommitted reader visibility with the selected SQLite backend. Stage 4's review
found no actionable correctness defect; Stage 6 added the public-library demo.
A green suite establishes the checks below on the observed runtime, not all
possible executions or the author's final submission review.
Finite tests exercise counterexamples; general correctness also depends on input
validation, database constraints, transaction boundaries, and durable retry identity.

## Implemented Stage 1 checks

| Behavior | Evidence |
|---|---|
| Exact, nonnegative opening balances | Zero, one cent, ordinary amounts, maximum, and generated integer values |
| Unsupported inputs rejected without effects | Strings, booleans, floats including NaN/infinity, numeric wrappers, containers, coercion objects, negative/oversized integers; complete state snapshots |
| Account identities and reads | Positive unique generated IDs; missing accounts; invalid identifiers cannot become account 1 |
| Persistent state and exact totals | Reopen checks and four seeded 60-operation sequences checked against a separate Python model after each operation |
| Stored amount constraints | Direct invalid updates, SQL overflow, and multirow constraint failure preserve prior state |
| Transaction failure paths | Ordinary errors, interruptions, writer-lock timeout, commit-lock timeout, rollback, and connection reuse |
| Visibility and independent callers | Separate-reader visibility before/after commit; eight thread-owned account-creation connections and complete outcome collection |
| Process exit | Reopen after child exit before/after commit; expected state and SQLite integrity check |
| Test sensitivity | Four disposable mutations: accepting booleans, permitting negative stored balances, omitting commit, omitting rollback; unmodified controls must pass |

Public money inputs reject numeric strings. SQLite STRICT itself permits lossless
conversion of numeric strings into integers; that is explicitly tested and is why
database typing cannot replace public input validation. Strings remain appropriate
for database paths and the transfer identifier.

## Executed transfer evidence

| Rule | Executed scenarios and assertions |
|---|---|
| Balances never negative | `test_transfers.py` tests exact spending and rejection. `test_transfer_concurrency.py::test_competing_transfers_cannot_overspend` and `test_transfer_processes.py::test_separate_processes_competing_for_funds_cannot_overspend` force overlapping 8,000-cent attempts from A=10,000, B=C=0: one success/one insufficient result, A=2,000, destinations 8,000/0, total=10,000, one row, matching histories |
| All-or-nothing transfers | `test_transfer_failures.py` injects failures before credit/record, after insertion, and at busy begin/commit. `test_transfer_processes.py` exits real children after debit/credit/completed insertion, checks restored state after reopen, and confirms independent readers cannot see a paused debit. Failed attempts leave state/key unchanged and same-key retry succeeds |
| Same transfer applied once | Sequential and thread/process same-key cases return identical receipts; depleted sender replay succeeds; discarded response and actual child exit after commit before returning a receipt both replay once after reopen. Changed sender/recipient/amount conflict, including thread/process overlapping changed payloads; failed attempts do not consume keys |
| Exact amounts | One cent, 100 repeated one-cent transfers, maximum, exact recipient maximum, and overflow. All three numeric request fields reject 40 adversarial cases each. Four seeded 80-operation ledger models check every balance, row, history, total, bound, and reopen result |

Additional executed contract checks cover 17 invalid keys, exact Unicode/whitespace/
SQL-looking valid keys, nonexistent/self accounts, deterministic sequence order,
empty/missing history, opening-plus-history reconciliation, opposite-direction
overlapping transfers, and direct SQLite amount/foreign-key/distinct/unique checks.
Numeric strings are rejected by the public API; SQLite's lossless conversion through
direct SQL remains explicitly distinguished from that API contract.

The competing-transfer test uses one real temporary file and worker-owned
connections. It pauses the first caller after acquiring its real writer transaction;
SQLite tracing signals the second caller's `BEGIN IMMEDIATE` attempt while that
transaction remains held. Bounded events release the first and both outcomes are
collected. Lock errors, worker crashes, missing results, and timeouts fail the test.
The first caller is deliberately scheduled to win; this establishes overlapping
attempts and serialization at that boundary, not every possible schedule.

The process version uses `spawn`, verifies two different child IDs distinct from the
parent, and waits for both initialized services before starting. Bounded pipe messages
prove held-writer/second-BEGIN overlap, collect every outcome, and require normal
child exits. Cleanup terminates leftover test children. No application process lock
is used. Reopened account/receipt/history state must reconcile, `integrity_check`
must report `ok`, and `foreign_key_check` must be empty.

Abrupt-transfer tests forward real SQL through a child-only connection wrapper,
report the reached statement boundary and actual transaction state, and call
`os._exit(17)` without Python cleanup. Three pre-commit cases require original state
and successful same-key retry. A post-commit case requires one persisted receipt and
an unchanged replay; it exits before the service can return its business response.
The paused-debit case keeps the child alive while independent parent readers require
the original balances and empty histories, then checks the completed transfer.

`scripts/check_test_sensitivity.py` executed eight disposable mutation cases (seven
distinct code changes) with passing controls and required named test failures.
The three transfer changes ignore a
failed debit (detected by the actual competing-transfer test), skip committed replay
(detected by concurrent same-key checks), or commit after a transfer failure
(detected by injected rollback checks). Actual source hashes remained unchanged.
The failed-debit mutation is also detected by the separate-process competing test.
These deliberate experiments are not AI mistake narratives.

## Further evidence not yet established

- Every lock/read/write schedule, sustained load, performance benchmarks, physical
  power-loss/corruption recovery, backups, or all supported runtime versions.
  Verified combinations are Python 3.14.7 / SQLite 3.53.4 and fresh-checkout
  Python 3.12.8 / SQLite 3.45.3; this is not a complete version matrix.
- Production authorization, encryption, client/bank isolation, and multi-currency
  behavior; these are outside the assignment's current local library scope.
- The author's final README/build-log/submission review and missing personal/time
  facts. Stage 4's assistant critique is complete; final packaging evidence is in
  WORKING_NOTES.

## Verification and commit policy

- Run focused checks during development and the full currently implemented suite
  before each source/test milestone commit. Record actual results in working notes.
- Commit a small, coherent, passing feature or test improvement when completed.
  Do not reconstruct artificial earlier commits, rewrite history, or weaken tests.
- Keep future required checks marked pending until they execute against real code.
- Stop after the user-requested stage. Do not change storage without a selection.
- These checks do not establish physical power-loss recovery, corruption recovery,
  production authorization, encryption, or every possible execution schedule.
