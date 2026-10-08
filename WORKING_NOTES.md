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

## Stage 2 documentation and review checkpoint

- Transfer concurrency/failure milestone committed as `06cfc04` —
  `Verify competing transfers and atomic failure paths`.
- Expanded the disposable mutation script to seven selected faults. Actual run:
  **7/7 detected**, exit code 0; each control passed, each named mutated test failed,
  and real source hashes were unchanged. New faults ignore a failed debit, skip
  committed replay, or commit after a transfer failure. No intentionally faulty
  real source or commit was created, and no AI mistake narrative is implied.
- Final full suite: `.venv/bin/python -m pytest -q` reported
  **363 passed in 1.96s**, exit code 0. The named competing-transfer command passed
  separately: **1 passed in 0.09s**, exit code 0.
- Repeated the four overlap checks in five fresh pytest invocations to check the
  coordination mechanism for observed flakiness; all five invocations passed.
  Repetition is finite schedule evidence, not a general concurrency proof.
- Executed the exact updated README Python example against a fresh temporary file.
  It printed balances 2,000/8,000, sequence-1 receipt, identical replay, and one
  canonical incoming/outgoing history entry. Runtime observed: Python 3.14.7,
  SQLite 3.53.4. `pip check` exited 0 with no broken requirements; installation
  commands/dependencies remain those verified during Stage 1.
- README describes all four operations, input units/bounds, key policies, errors,
  transaction behavior, tested invariants, limits, and exact executed example/test
  commands. TEST_PLAN now maps executed evidence and distinguishes remaining
  process-transfer, recovery, load, and runtime-version checks from passing cases.
- PostgreSQL remains a possible future choice for many simultaneous writers or
  shared server access, not an implemented or benchmarked backend. The user selected
  SQLite and no migration occurred. No client/bank ownership or extra product scope
  was introduced.
- Assistant inspected meaningful changes and whitespace checks passed. Planned
  final milestone message: `Document verified SQLite transfer behavior and evidence`.
  Stage 2 stops after this commit for user inspection; later stages, the concise
  final build log, packaging, and submission remain under user control.
- Actual total assignment elapsed/remaining time and the user's personal review
  judgment remain unknown. No later-stage completion or unsupported test outcome
  is being claimed.

## Stage 3 authorization and process concurrency checkpoint

- The user said `proceed` after the Stage 2 stop. This advances Stage 3 only using
  the confirmed SQLite backend, with one assistant agent and no extra product scope.
- Proposed budget: 25 minutes. Actual total assignment elapsed/remaining time is
  still unknown. Expected new evidence: overlapping separate-process transfers,
  actual process termination during transfer, and selected mutation sensitivity.
- Git was clean at the Stage 2 head `2d83cb6`. Before edits, the full suite reported
  **363 passed in 1.79s**, exit code 0. Existing thread races, precision, validation,
  retries, conflicts, and transfer rollback evidence remain in the suite.
- Added three tests using Python's `spawn` start method. Two independent process IDs
  distinct from the test parent are confirmed. Each child constructs its own service
  and opens its connection locally against the same temporary database file.
- Bounded pipe messages confirm both children are ready, the first holds its real
  writer transaction, and the second traces its actual `BEGIN IMMEDIATE` attempt
  before the first is released. Every outcome and clean exit is required. Unexpected
  exceptions, SQLite lock failures, EOF, missing messages, and timeouts fail checks;
  leftover children are terminated in test cleanup.
- Required competing-funds scenario asserts one receipt and one insufficient-funds
  error, A=2,000, destinations 8,000/0, conserved total=10,000, one row, and exact
  opening/history reconciliation after reopen. Same-key and changed-payload cases
  also run across these processes. SQLite integrity and foreign-key checks pass.
- Focused command `.venv/bin/python -m pytest -q tests/test_transfer_processes.py`:
  **3 passed in 0.30s**, exit code 0. Full suite:
  **366 passed in 2.06s**, exit code 0. The added file was inspected and
  `git diff --check` passed before this milestone commit.
- No production source changes or repairs were necessary. Coordination deliberately
  orders which process wins; this tests actual cross-process contention, not every
  schedule, sustained load, or host/storage failure. Milestone message:
  `Verify transfer contention and retries across separate processes`.

## Stage 3 interrupted-transfer and visibility checkpoint

- Separate-process concurrency milestone committed as `00b6b88` —
  `Verify transfer contention and retries across separate processes`.
- Added child-only connection instrumentation that forwards real SQL, reports the
  reached boundary and actual transaction state, then calls `os._exit(17)` without
  Python cleanup. Three cases exit after debit, after credit, or after completed
  receipt insertion. Each checkpoint confirms the expected uncommitted state;
  clean parent-side reopen then requires the full original state, no receipt/history,
  a still-available key, a successful same-key transfer, and reconciled exact totals.
- A fourth case exits immediately after a successful SQL commit, before the public
  operation returns a receipt. The checkpoint confirms no active transaction and
  the committed row. Reopen/retry returns that same receipt and changes nothing.
- A live child pauses after actual debit. Parent-owned connections still see both
  original balances and empty histories until release/commit. Afterward both balance
  changes and the canonical receipt reconcile. No production fault hook was added.
- Added a public-transfer writer-acquisition timeout check: a real held transaction
  causes `SQLITE_BUSY`, state/key are unchanged, then the same key succeeds after
  release. Only this test shortens its connection timeout to 20 ms.
- Focused process/failure checks: **14 passed in 1.27s**, exit code 0. Full suite:
  **372 passed in 2.99s**, exit code 0. Diff inspection and
  `git diff --check` passed. Milestone: `Check transfer process exits and committed visibility`.
- These are abrupt local process-exit and visibility tests on the observed SQLite
  runtime, not physical power loss, corruption recovery, or a real network response
  loss experiment. No production repair or fabricated AI mistake was necessary.

## Stage 3 final evidence and review checkpoint

- Process-exit/visibility milestone committed as `5e568df` —
  `Check transfer process exits and committed visibility`.
- Extended the disposable-copy sensitivity script to check the actual separate-
  process competing-funds test against ignored failed-debit handling. Run result:
  **8/8 mutation cases detected**, exit code 0, all controls passing and actual source
  hashes unchanged. These cover seven distinct code changes; failed-debit handling
  is checked against both the thread and process race. Collection/setup errors do
  not count as detection. These are planned experiments, not accidental AI defects.
- Final `.venv/bin/python -m pytest -q`: **372 passed in 3.27s**, exit code 0.
  README's separate-process command ran against the final module:
  **8 passed in 1.42s**, exit code 0. The earlier focused process/failure command and
  both milestone full-suite results are retained above as separate actual checkpoints.
- Updated README and TEST_PLAN to reflect completed Stage 3 evidence, exact process
  test commands, coordination boundaries, abrupt-exit/replay/reader checks, mutation
  cases, and remaining limits. Relevant diffs were inspected and whitespace checks
  passed. Final milestone message: `Document process safety evidence and mutation checks`.
- Production source, storage choice, dependencies, and public contract were unchanged
  during Stage 3. Process evidence uses the observed local runtime and controlled
  winner order. Physical power loss, corruption recovery, backup procedures, every
  schedule, sustained load, and supported-version coverage remain unestablished.
- Stage 3 stops for the user's review. Stage 4 critique, final concise build log,
  packaging, and submission are not being performed in this turn. The user's review
  judgment and actual assignment elapsed/remaining time remain unknown.

## Stage 4 review record and Stage 6 authorization

- The previous Stage 4 turn was read-only. It found no actionable money-correctness
  defect against the original brief and changed no project files or commits.
  The fresh suite reported **372 passed in 2.77s**, exit code 0, with bytecode and
  pytest cache writes disabled for that review.
- Four additional checks ran in disposable databases outside the project: 16
  barrier-started callers produced one success and 15 insufficient-funds results
  with 10,000 cents conserved; replay with an empty sender and maximum recipient
  changed nothing; a failed key accepted different valid details; a retained
  single-row RETURNING cursor did not prevent commit. All passed in that turn.
  These review probes were not added to the committed pytest suite.
- The user then said `proceed` after being told Stage 6's deterministic demo was
  next. No Stage 5 repair was identified or manufactured. Stage 6 only is authorized.
- Proposed budget: 15 minutes. Actual assignment elapsed/remaining time is unknown.
  The chosen interface remains a library. Scope: one short executable demonstration
  of existing operations and errors, exact units/receipts, and verified test commands.
- Git was clean at `596d628` before this stage. Baseline suite:
  **372 passed in 2.89s**, exit code 0.

## Stage 6 library demonstration checkpoint

- Added `scripts/demo.py`. It creates a fresh temporary database, opens 10,000-cent
  and zero-cent accounts, transfers 8,000 cents, replays the same receipt, and requests
  a conflicting amount, an overspend, and an intentionally invalid money string.
  Business decisions remain in the public service; the demo verifies expected
  outcomes rather than implementing money rules separately.
- It checks state after replay and each rejection, prints canonical receipt fields,
  balances, and one outgoing/incoming history entry, verifies total=10,000 cents,
  and checks that its disposable directory is removed. Unexpected outcomes raise
  errors rather than printing a successful completion.
- `.venv/bin/python scripts/demo.py`: exit code 0. Actual balances were 2,000/8,000,
  receipt sequence 1 for `demo-payment`, and exactly one successful transfer in both
  histories. Expected domain errors were TransferConflict, InsufficientFunds, and
  InvalidInput. The final removal check passed.
- Two additional fresh executions exited 0, had no stderr, and produced identical
  stdout. These are actual repeated demo runs, not timing or concurrency evidence.
- Full suite after adding the demo: **372 passed in 2.91s**, exit code 0.
  The script was inspected and whitespace checks passed. No redundant formatter
  tests or production behavior changes were added.
- First milestone message: `Add deterministic demo of the public money library`.
  README/demo and focused correctness-check commands remain to be completed within
  this stage before stopping for the user's review.
