# Build log — Move the Money

Factual draft for author review. Bracketed author fields must be resolved before
submission; they are not claims about time or personal experience.

**Time:** The author reported two hours used at the final-documentation checkpoint,
including prior work. This is a supplied checkpoint, not a measured final duration.
[AUTHOR: update the final total before submission if more assignment time is used.]

**Intent and scope.** Build the four requested operations as a Python + SQLite
library, prioritizing nonnegative balances, atomic transfers, safe retries, and
exact cents. Keep the interface small and business rules in one service. Accounts
store opening/current balances; every successful transfer updates both current
balances and records one canonical receipt in the same transaction. The author
reports reviewing the work after every stage, including the technology choices.
Python was chosen because it is the language the author is most comfortable with.
SQLite was chosen for this project's small workload; PostgreSQL's
additional write capacity was not needed for the exercise. This is a scope judgment,
not a measured throughput comparison.

**Where AI helped.** Codex proposed and implemented the service, exact input checks,
SQL schema/transaction boundary, retry policy, histories, and demo. It constructed
adversarial input cases, independent seeded ledger comparisons, controlled
thread/process contention, injected rollback failures, and abrupt process exits.
One agent was used. Small genuine commits preserve the progression: account
foundation `0f4beed`, atomic transfers/retries `9c733a1`, history `89fd46f`,
competition/failure evidence `06cfc04`, process evidence `00b6b88` / `5e568df`,
and public-library demo `15e31ce`.

**Where the explanation went wrong.** During review, AI described the formula
"opening + incoming − outgoing" without clearly distinguishing reconciliation
from balance lookup. The author challenged why balances were not updated directly.
Checking the service confirmed that they already were: `get_balance` reads the
stored current balance, and each successful transfer updates it atomically.
The explanation and README were clarified; no money-code repair was needed.
This was misleading communication, not an identified incorrect transfer
implementation. No concrete incorrect money implementation was found in the
recorded review, and deliberate mutation experiments are not accidental AI mistakes.

AI also initially packaged Git with `--all`, assuming only the project branch was
relevant. Bundle verification exposed app-generated snapshot refs alongside `main`.
Packaging was corrected to explicitly select `main` and `HEAD`, retaining all real
branch commits without exporting those internal snapshots. No history was rewritten
and the initial package was not sent.

**Scope decision.** The assistant raised a possible combined balance/history
snapshot report. The author directed work back to the brief and deferred extras.
Separate balance and history operations were retained. SQLite was also explicitly
retained after discussion of PostgreSQL.
No UI, authentication, deployment, or client/bank ownership model was added.

**Evidence and concerns.** The recorded suite contains 372 passing cases. Required
competition is two 8,000-cent requests against 10,000: one succeeds, one rejects,
and all balances/history reconcile with total=10,000. Eight selected deliberate
mutation cases were detected with passing controls. Clean-checkout verification
is recorded in WORKING_NOTES; bundle identity/checks are in the local delivery
report. Clean setup, demo, all 372 cases, focused competition/failure/process checks,
and 8/8 sensitivity cases passed with Python 3.12.8 / SQLite 3.45.3, alongside
earlier Python 3.14.7 / SQLite 3.53.4 evidence. Tests cover finite schedules;
physical power-loss recovery, all versions, and sustained load remain unestablished.
Single-writer contention can produce a storage timeout.
[AUTHOR: any shipped choice you personally feel uncomfortable with; explicitly
say if none, rather than assuming that judgment.]

**Next hour.** Vary controlled competing-transfer winner order and generated ledger
seeds, adding a focused regression for any actual finding. Continue prioritizing
the four invariants over additional product features.
