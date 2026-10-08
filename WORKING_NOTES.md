# Factual working notes

These are checkpoint notes, not the final one-page build log. Personal observations
and judgments must come from the user; none are attributed to them here.

## Planning and authorization

- The supplied brief is authoritative; architecture recommendations are optional.
- The user initially reported 5 minutes already used and 235 minutes remaining.
  Those were supplied values at Stage 0, not current timer readings.
- The user selected Python + SQLite and subsequently authorized Stage 1.
- One agent is being used. Stage 1's proposed budget is 20 minutes. The latest
  actual elapsed/remaining assignment time is unknown; the user owns the timer.
- First Stage 1 tool checkpoint: 2026-10-08 01:15:02 UTC. This is an observed
  timestamp, not the assignment start time or a total elapsed-time measurement.
- Actual model/reasoning settings: not independently verified in this session.

## Stage 1 setup and decisions

- Initially the folder contained the planning packet and had no Git repository.
  Git was initialized on branch `main`; no earlier project history existed.
- Observed runtime: Python 3.14.7, SQLite 3.53.4.
- A local `.venv` was created. pytest was initially unavailable.
- The initial pytest installation failed because the sandbox could not resolve
  PyPI. An authorized network-enabled retry installed pytest 9.1.1 successfully.
  The pip cache inspection was unavailable because its cache directory was not writable.
- AI proposed the account service, input checks, explicit SQL transactions, and
  tests. The implementation uses integer cents and a file-backed database; no
  transfer, retry, history, CLI, or deployment feature has been implemented.
- Database checks and strict integer columns supplement Python validation.
  `type(value) is int` excludes booleans. This is deliberate validation, not a
  discovered AI incident.
- Python's documented `autocommit=True` behavior requires SQL `COMMIT`/`ROLLBACK`;
  connection `.commit()`/`.rollback()` would have no effect. The implementation
  deliberately uses SQL statements. This was checked in the Python documentation.
- The original planning packet is ignored by Git because it contains personal
  recruiting/planning context. Environment, cache, and local database files are
  also ignored.

## Verification checkpoint

- Setup commands executed successfully: `python3 -m venv .venv`, followed by
  `.venv/bin/python -m pip install --no-cache-dir -e '.[dev]'`. The local library
  and its declared development dependency installed successfully.
- `.venv/bin/python -m pytest -q`: **38 passed in 0.08s**, exit code 0.
  Covered exact opening balances (zero, one cent, 10,000 cents, maximum), invalid
  amounts/identifiers including booleans, missing accounts, separate accounts,
  reopen persistence, direct database constraint failures, SQL arithmetic
  overflow, connection settings, rollback of an injected account insert failure,
  and visibility before/after commit on independent connections.
- The README account example ran successfully and printed `funded: 10000 cents`
  and `empty: 0 cents`. It used a fresh temporary database and removed it afterward.
- Verification tool checkpoint: 2026-10-08 01:20:09 UTC. This timestamp does not
  establish the user's total assignment time or remaining allowance.
- `.venv/bin/python -m pip check`: exit code 0, no broken requirements found.
- The source/configuration diff was inspected by the assistant. Git's ignore
  check confirmed that the planning packet, environment, pytest cache, and package
  metadata are excluded. The user has not yet supplied a personal review judgment.
- This rollback check concerns account insertion/the transaction helper. It does
  not establish transfer atomicity, concurrent overspending prevention, retry
  correctness, power-loss recovery, or behavior on every supported runtime.
- Related commit: none made yet. A milestone message will be proposed after review.
  Git has eight new files marked with intent-to-add so their uncommitted diff is
  reviewable; no artificial history or intentionally broken commit was created.
- No concrete incorrect AI claim or proposal has been identified during Stage 1.
  No mistake narrative or user rejection decision has been manufactured.
- Remaining uncertainty: transfer behavior and its four invariants are not
  implemented or established; the required competing-transfer test is pending.
  Only the observed Python/SQLite runtime has been exercised so far.

## Validation follow-up authorization

- The user requested more rigorous invariant/input tests and more frequent,
  smaller commits for recovery. Storage alternatives were requested for discussion;
  no change away from the selected SQLite backend has been authorized.
- Proposed budget for the Stage 1 validation follow-up: 15 minutes. Actual total
  assignment elapsed/remaining time is still unknown.
- Before changing the tests, `.venv/bin/python -m pytest -q` again reported
  **38 passed in 0.08s**, exit code 0. The source diff was reviewed and had no
  whitespace errors. This existing foundation will become the first real commit;
  its already-created features are not being split into invented earlier milestones.
- Whether to proceed with Stage 2 was asked separately because the user originally
  required a stage prompt before transfer implementation.
- Baseline milestone created: `0f4beed` — `Add account creation and exact-cent validation`.

## Adversarial input checkpoint

- Added 39 unsupported input cases for each public operation, including numeric/
  Unicode/SQL-looking strings, booleans, floats/NaN/infinities, containers, numeric
  wrappers/subclasses, conversion objects, and out-of-range integers. Each rejected
  operation is checked against a full before/after snapshot of existing accounts.
- Added four reproducible, seeded 60-operation sequences. A separate Python model
  predicts balances after each operation and database reopen. Assertions check all
  accounts, exact integer types, nonnegative/range bounds, and exact opening totals.
  These are account-operation sequences, not transfer-conservation evidence.
- `.venv/bin/python -m pytest -q`: **120 passed in 0.35s**, exit code 0.
- No runtime feature or storage backend changed at this checkpoint.
- Input-test milestone created: `3e1c555` —
  `Exercise adversarial account inputs and generated sequences`.

## Storage-failure checkpoint

- The user answered the scope question: strengthen Stage 1 and stop for review.
  Transfers/history and their acceptance tests remain pending for later stages.
- Added real SQLite tests for a blocked `BEGIN IMMEDIATE`, a blocked `COMMIT`,
  rollback of multiple changes after errors/interruptions, and a failed multirow
  update. Lock errors must propagate rather than become a business rejection.
- The commit-contention test shortens its connection's busy timeout to 20 ms,
  confirms both SQL `COMMIT` and `ROLLBACK` were attempted, checks restored state,
  then verifies that the connection can successfully perform another transaction.
- Eight barrier-coordinated threads create accounts with worker-owned connections;
  all results are collected and identifiers, balances, and opening totals checked.
  This is account-creation evidence, not the required competing-transfer test.
- Child processes exit explicitly before or after commit. Reopen checks confirm
  only committed account writes persist, and SQLite integrity checks return `ok`.
  This does not simulate physical power loss, disk corruption, or transfer retries.
- A separate test demonstrates SQLite STRICT's permitted lossless numeric-string
  conversion while requiring the public account API to reject the same string.
- `.venv/bin/python -m pytest -q`: **130 passed in 0.53s**, exit code 0.
- Storage-test milestone created: `27548e1` —
  `Verify SQLite contention rollback and process-exit behavior`.

## Test-sensitivity and final review checkpoint

- Added `scripts/check_test_sensitivity.py`. It copies source/tests into temporary
  directories inside the ignored `.venv`, runs an unmodified control, applies one
  deliberate mutation to the copy, and requires the named test to fail with pytest
  exit code 1. Collection errors and a failing unmodified control do not count.
- `.venv/bin/python scripts/check_test_sensitivity.py`: exit code 0. **4/4 selected
  mutations detected**: accepting booleans, allowing negative stored balances,
  omitting commit, and omitting rollback. All four controls passed. Source hashes
  matched before/after, and disposable copies were removed. These are planned test
  experiments, not observed AI mistakes or complete mutation coverage.
- Final `.venv/bin/python -m pytest -q`: **130 passed in 0.60s**, exit code 0.
- `TEST_PLAN.md` records executable foundation evidence, pending scenarios for all
  four transfer rules, and the user's requested verification/small-commit policy.
  README now links the matrix and the executed test-sensitivity command.
- No runtime implementation repair was required by the observed new tests.
  No transfer/history feature or backend migration was performed. No personal
  judgment, actual total assignment time, or new AI-mistake story was invented.

## Stage 2 authorization and transfer checkpoint

- The user said to proceed, then explicitly confirmed keeping SQLite. No
  PostgreSQL migration, dependency installation, or database server setup occurred.
- Proposed Stage 2 budget: 50 minutes; actual total elapsed/remaining assignment
  time remains unknown. The user owns that timer and relaxed timing emphasis.
- Stage scope: transfers, stable receipts, retry/conflict handling, and history.
  The user's request for rigorous checks also warrants essential competing-transfer
  and rollback evidence before this stage stops for review.
- Before edits, the suite reported **130 passed in 0.53s**, exit code 0.
- Added the canonical successful-transfer table with unique keys, foreign keys,
  integer/range constraints, and distinct-account checks. Each transfer acquires
  `BEGIN IMMEDIATE` before retry lookup, account checks, or conditional updates.
  Debit, credit, and receipt insertion share one commit/rollback boundary.
- Committed receipts are replayed before current funds/existence/self-transfer
  business checks. Changed valid payloads conflict. Failed uncommitted attempts
  leave the key available. Keys are exact plain strings, nonblank, valid UTF-8,
  without NUL characters; they are validated, not trimmed or normalized.
- Added focused checks for exact/ordinary transfers, insufficient funds, recipient
  overflow, missing/self accounts, stable replay after depletion and reopen,
  changed payloads, failed-attempt retry, and parameterized SQL keys.
- `.venv/bin/python -m pytest -q`: **152 passed in 0.69s**, exit code 0.
  These sequential checks alone are not concurrency or injected-failure evidence.
- Assistant inspected the source diff; `git diff --check` passed. This coherent
  milestone is ready to commit as `Apply transfers atomically with retry identity`.
  History and stronger transfer evidence remain to be completed within this stage.

## History checkpoint

- Transfer milestone committed as `9c733a1` —
  `Apply transfers atomically with retry identity`.
- Added `get_history(account_id)`, returning incoming/outgoing entries in persisted
  sequence order. Both account views use the same canonical receipt. A single
  query distinguishes an absent account from a present account with no transfers.
  Opening funding remains separate, and sender/recipient lookup indexes were added.
- Added empty/missing/invalid-history cases, ordered incoming/outgoing assertions,
  reopen and opening-plus-history reconciliation, excluded failed/conflicting/
  replay entries, and 100 exact one-cent transfers.
- `.venv/bin/python -m pytest -q`: **165 passed in 0.88s**, exit code 0.
  Source/test changes were inspected; `git diff --check` passed.
- This milestone is ready to commit as `Expose ordered incoming and outgoing history`.
  Controlled concurrency, injected transfer failures, and wider invalid transfer
  inputs remain to be checked before Stage 2 stops.

## Adversarial transfer and ledger checkpoint

- History milestone committed as `89fd46f` —
  `Expose ordered incoming and outgoing history`.
- Applied the existing 39 adversarial values plus integer zero to all three
  numeric transfer fields. Invalid history IDs and 17 invalid key cases are also
  checked against complete account/transfer snapshots. This explicitly includes
  money strings, booleans, floats/NaN/infinity, numeric wrappers, containers,
  integer subclasses, and conversion objects. Valid text transfer keys are retained.
- Added four seeded 80-operation transfer/retry/conflict sequences, checked against
  a separate Python ledger after each operation. Every account, canonical receipt,
  history direction/order, exact total, bound, and reopen result is compared.
  These are sequential model checks; they do not establish concurrency behavior.
- `.venv/bin/python -m pytest -q`: **345 passed in 1.74s**, exit code 0.
  The changes were inspected and `git diff --check` passed. No production repair
  was required by these checks. Milestone: `Check adversarial transfer inputs against a ledger model`.

## Overlapping transfers and fault-injection checkpoint

- Input/model milestone committed as `a464ce7` —
  `Check adversarial transfer inputs against a ledger model`.
- Added four controlled overlap checks on one real temporary database file with
  independent worker-owned connections. The first caller holds its real writer
  transaction; SQLite tracing confirms the second attempts `BEGIN IMMEDIATE`
  while the first is held. Bounded events release the first, and both outcomes are
  collected. This forces contention at the writer boundary, not simultaneous
  execution inside SQLite's single-writer transaction.
- Required scenario: A=10,000, B=C=0; different keys each request 8,000. Assertions
  require one receipt and one insufficient-funds outcome, A=2,000, destinations
  8,000/0, conserved total=10,000, one canonical row, and matching histories.
  Same-key overlap must return identical receipts once; changed payload overlap
  must conflict without another movement. Opposite-direction transfers both finish.
- Added SQLite triggers that fail before recipient credit (after debit), before
  recording (after credit), or after record insertion. Every case requires unchanged
  accounts/records/history and a successful same-key retry after removing the trigger.
- A held SQLite reader makes transfer `COMMIT` fail with `SQLITE_BUSY`; tracing
  confirms both updates, receipt insertion, commit attempt, and rollback. Complete
  state remains unchanged and the same key later succeeds. The test temporarily
  shortens its timeout to 20 ms; production remains five seconds.
- A discarded receipt followed by reopen/retry returns the committed record once.
  This models caller response loss locally, not a network transport failure.
- Direct database checks cover transfer amount range/type, foreign keys, distinct
  accounts, and unique receipt identity. Public validation remains responsible for
  rejecting losslessly coercible numeric strings and booleans.
- Initial combined suite: **354 passed in 2.02s**, exit code 0. After adding direct
  transfer-constraint checks: **363 passed in 2.03s**, exit code 0.
- New tests were inspected; whitespace checks passed. No production repair was
  required by these tests. They do not prove every schedule or physical power-loss
  recovery. Milestone: `Verify competing transfers and atomic failure paths`.
