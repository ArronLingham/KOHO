# Correctness evidence and remaining limits

The original assignment brief governs requirements. Stage 2 implements the four
required operations with the selected Python + SQLite backend. A green suite
establishes the checks below on the observed runtime, not all possible executions
or completion of later review/submission stages.
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
| Balances never negative | `test_transfers.py` tests exact spending and rejection. `test_transfer_concurrency.py::test_competing_transfers_cannot_overspend` forces overlapping 8,000-cent attempts from A=10,000, B=C=0: one success/one insufficient result, A=2,000, destinations 8,000/0, total=10,000, one row, matching histories |
| All-or-nothing transfers | `test_transfer_failures.py` injects failures before credit, before record insertion, after insertion, and at a busy commit. Complete accounts/records/history are unchanged; same-key retry succeeds after removing the failure |
| Same transfer applied once | Sequential/concurrent same-key cases return identical receipts; depleted sender replay succeeds; discarded response followed by reopen/retry moves once. Changed sender/recipient/amount conflict, including concurrent changed payload; failed attempts do not consume keys |
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

`scripts/check_test_sensitivity.py` executed seven disposable mutations with passing
controls and required named test failures. The three transfer mutations ignore a
failed debit (detected by the actual competing-transfer test), skip committed replay
(detected by concurrent same-key checks), or commit after a transfer failure
(detected by injected rollback checks). Actual source hashes remained unchanged.
These deliberate experiments are not AI mistake narratives.

## Further evidence not yet established

- Transfer races between separate processes and process termination during an
  actual transfer; existing child-process checks concern account writes only.
- Every lock/read/write schedule, sustained load, performance benchmarks, physical
  power-loss/corruption recovery, backups, or all supported runtime versions.
- Production authorization, encryption, client/bank isolation, and multi-currency
  behavior; these are outside the assignment's current local library scope.
- Later user-controlled critique and final README/build-log/submission review.

## Verification and commit policy

- Run focused checks during development and the full currently implemented suite
  before each source/test milestone commit. Record actual results in working notes.
- Commit a small, coherent, passing feature or test improvement when completed.
  Do not reconstruct artificial earlier commits, rewrite history, or weaken tests.
- Keep future required checks marked pending until they execute against real code.
- Stop after the user-requested stage. Do not change storage without a selection.
- These checks do not establish physical power-loss recovery, corruption recovery,
  production authorization, encryption, or every possible execution schedule.
