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
