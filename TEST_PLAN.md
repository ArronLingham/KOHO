# Correctness evidence and pending acceptance tests

The original assignment brief governs requirements. A green suite currently
verifies the implemented account foundation, not completion of the assignment.
Transfer/history behavior is intentionally pending the user's Stage 2 prompt.
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
for database paths and the planned transfer identifier.

## Required transfer rules — PENDING

None of the scenarios below is currently counted as a passing transfer test.

| Rule | Required scenarios and assertions |
|---|---|
| Balances never negative | Exact-balance spending; insufficient-funds rejection; controlled competing A→B/A→C attempts for 8,000 cents each from A=10,000, B=C=0; one success and one insufficient-funds result; A=2,000, destinations 8,000/0, total=10,000, one transfer row |
| All-or-nothing transfers | Inject failures after debit, after credit, while recording transfer, and at commit where practical; balances/history/retry records unchanged on failure; committed records reconcile both account histories |
| Same transfer applied once | Sequential and concurrent same-key submissions; replay after sender depletion; commit with lost response followed by reopen/retry; one debit/credit/record and identical stored receipt |
| Exact amounts | One-cent and repeated small transfers; integer amounts throughout; every unsupported amount type rejected; maximum and recipient-overflow boundaries; exact conservation checked after completed operations |

Additional contract tests will cover changed sender/recipient/amount for an existing
key, concurrent conflicting payloads, blank/nonstring transfer IDs, nonexistent
accounts, self-transfers, retrying a failed uncommitted attempt, deterministic
incoming/outgoing history, and reconciliation from opening balances.

The competing-transfer test must use one real temporary file, worker-owned
connections, bounded coordination with evidence of overlapping attempts, and
complete outcome collection. Lock errors, worker crashes, missing results, or
timeouts are failures. A two-worker barrier after writer-lock acquisition is invalid.
Once transfers exist, add reproducible model-based transfer sequences and a
disposable mutation check for the actual transfer concurrency test.

## Verification and commit policy

- Run focused checks during development and the full currently implemented suite
  before each source/test milestone commit. Record actual results in working notes.
- Commit a small, coherent, passing feature or test improvement when completed.
  Do not reconstruct artificial earlier commits, rewrite history, or weaken tests.
- Keep future required checks marked pending until they execute against real code.
- Stop after the user-requested stage. Do not change storage without a selection.
- These checks do not establish physical power-loss recovery, corruption recovery,
  production authorization, encryption, or every possible execution schedule.
