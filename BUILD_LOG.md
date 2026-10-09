# Build log — Move the Money

**What I set out to do.** Build a Python + SQLite library for opening accounts,
transferring money, reading balances, and reading history. The priorities were
nonnegative balances, atomic transfers, safe retries, and exact amounts. I chose
Python because I am most comfortable with it and SQLite because the project is
small. I reviewed the work after each stage.

**Where AI genuinely helped.** Codex implemented the service, validation,
transactions, retry policy, histories, and demo. It turned the rules into tests
using independent connections and processes, injected failures, abrupt process
exits, and an independent generated ledger. An AI-assisted technical review found
coverage gaps for invalid inputs on committed keys and immutable return values;
these became regression tests. Deliberate defects in disposable copies checked
selected tests' sensitivity. The latest recorded verification passed 613 tests,
19 selected mutation checks, and the demo. This is evidence for tested cases,
not every possible execution schedule.

**Where AI was wrong and how it was caught.** During the dollar-input change,
AI compared a stored `Decimal` amount with the original float when checking a
retry. `Decimal("0.10")` does not equal the binary float `0.10`, so valid $0.10
and $0.01 retries incorrectly raised conflicts. New tests caught this. The fix
compares normalized integer-cent amounts. Regression tests check equivalent
inputs return the original receipt without moving money again or adding history;
a mutation restoring the faulty comparison is also detected.

The review also found that an AI-generated omit-commit mutation failed during
database initialization with `no such table: accounts`. It detected a defect but
did not establish transfer-commit behavior. The revised check leaves
initialization intact and verifies that omitting the transfer commit leaves
balances unchanged. A failing test must fail for the intended reason.

**What AI suggested that I rejected, and why.** AI initially recommended integer
cents at the public interface: `1213` for $12.13. I requested dollar input such
as `12.13` so amounts could be entered directly. We retained integer cents
internally for exact arithmetic.

I also deferred a suggested combined balance/history snapshot because the brief
asks for separate operations and I wanted the required behavior finished before
extras. PostgreSQL was suggested for familiarity and future scale. I kept SQLite
because the small workload did not justify expanding the exercise's setup.

**What I am not comfortable with.** Decimal-dollar input and SQLite are the
choices I wanted to flag. Accepting `12.13` makes entry easier but adds a
normalization boundary; computed binary floats can contain fractional-cent
artifacts. The service returns `Decimal` money, rejects fractional cents rather
than rounding, and uses integer-cent arithmetic inside SQLite. Explicit
`Decimal` input supports calculations and large amounts. SQLite permits one
writer at a time, so contention can cause lock timeouts. The tests do not
establish sustained-load capacity or physical power-loss recovery. I would
reassess storage if the workload grew.
