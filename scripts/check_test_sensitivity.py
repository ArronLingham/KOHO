"""Check selected tests against deliberate mutations in disposable copies.

These mutations are test experiments, not defects encountered in the real code.
The actual source files are never modified.
"""

from hashlib import sha256
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]

_MUTATIONS = [
    (
        "accept-booleans",
        "move_money/service.py",
        "type(value) is not int",
        "not isinstance(value, int)",
        "tests/test_input_contract.py::test_invalid_opening_preserves_every_existing_account[true]",
    ),
    (
        "allow-negative-stored-balances",
        "move_money/storage.py",
        "CHECK (balance_cents BETWEEN 0 AND {MAX_CENTS})",
        "CHECK (balance_cents BETWEEN -9223372036854775808 AND {MAX_CENTS})",
        "tests/test_storage_failures.py::test_failed_multirow_statement_leaves_no_partial_balance_changes",
    ),
    (
        "omit-transfer-commit",
        "move_money/storage.py",
        'connection.execute("COMMIT")',
        # Initialization changes zero rows and account opening changes one.
        # Skip only the transaction that debits, credits, and inserts its receipt.
        'if connection.total_changes != 3:\n            connection.execute("COMMIT")',
        "tests/test_transfers.py::test_transfer_moves_exact_cents_once[123]",
    ),
    (
        "omit-rollback",
        "move_money/storage.py",
        'connection.execute("ROLLBACK")',
        "pass  # Deliberate mutation in a disposable copy only.",
        "tests/test_storage_failures.py::test_multiple_writes_roll_back_together_on_error_or_interruption[RuntimeError]",
    ),
    (
        "ignore-failed-debit",
        "move_money/service.py",
        "if debit.rowcount != 1:",
        "if False:  # Deliberate mutation in a disposable copy only.",
        "tests/test_transfer_concurrency.py::test_competing_transfers_cannot_overspend[b-first]",
    ),
    (
        "skip-committed-replay",
        "move_money/service.py",
        "if existing is not None:",
        "if False:  # Deliberate mutation in a disposable copy only.",
        "tests/test_transfer_concurrency.py::test_concurrent_same_key_returns_one_receipt_and_moves_once",
    ),
    (
        "commit-after-transfer-failure",
        "move_money/storage.py",
        'connection.execute("ROLLBACK")',
        'connection.execute("COMMIT")  # Deliberate mutation in a disposable copy only.',
        "tests/test_transfer_failures.py::test_transfer_failure_rolls_back_balances_record_and_key[after-credit]",
    ),
    (
        "ignore-failed-debit-across-processes",
        "move_money/service.py",
        "if debit.rowcount != 1:",
        "if False:  # Deliberate mutation in a disposable copy only.",
        "tests/test_transfer_processes.py::test_separate_processes_competing_for_funds_cannot_overspend[c-first]",
    ),
    (
        "validate-numeric-inputs-after-key-lookup",
        "move_money/service.py",
        '        _validate_integer(sender_id, "sender_id", minimum=1)\n'
        '        _validate_integer(recipient_id, "recipient_id", minimum=1)\n'
        '        _validate_integer(amount_cents, "amount_cents", minimum=1)\n',
        '        with _connection(self._database_path) as lookup:\n'
        '            committed = lookup.execute(\n'
        '                "SELECT 1 FROM transfers WHERE transfer_id = ?", (transfer_id,),\n'
        '            ).fetchone()\n'
        '        if committed is None:\n'
        '            _validate_integer(sender_id, "sender_id", minimum=1)\n'
        '            _validate_integer(recipient_id, "recipient_id", minimum=1)\n'
        '            _validate_integer(amount_cents, "amount_cents", minimum=1)\n',
        "tests/test_input_contract.py::test_invalid_transfer_fields_preserve_all_accounts_and_receipts[true-amount_cents-committed-key]",
    ),
    *[
        (
            f"mutable-{name.lower()}",
            "move_money/service.py",
            f"@dataclass(frozen=True)\nclass {name}:",
            f"@dataclass\nclass {name}:",
            f"tests/test_history.py::test_returned_values_are_immutable[{target}]",
        )
        for name, target in [
            ("Account", "account-balance_cents-999"),
            ("TransferReceipt", "receipt-amount_cents-999"),
            ("HistoryEntry", "entry-direction-incoming"),
        ]
    ],
]


def _run_test(directory, target):
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "--tb=short", target],
        cwd=directory,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )


def main():
    sources = sorted((ROOT / "move_money").glob("*.py"))
    before = {path: sha256(path.read_bytes()).hexdigest() for path in sources}
    scratch_parent = ROOT / "dist"
    scratch_parent.mkdir(exist_ok=True)

    with TemporaryDirectory(prefix="test-sensitivity-", dir=scratch_parent) as scratch:
        for name, relative_path, old, new, target in _MUTATIONS:
            candidate = Path(scratch) / name
            candidate.mkdir()
            for folder in ("move_money", "tests"):
                shutil.copytree(
                    ROOT / folder,
                    candidate / folder,
                    ignore=shutil.ignore_patterns("__pycache__"),
                )

            control = _run_test(candidate, target)
            if control.returncode != 0:
                raise RuntimeError(f"Unmodified control failed for {name}:\n{control.stdout}\n{control.stderr}")

            path = candidate / relative_path
            source = path.read_text()
            if source.count(old) != 1:
                raise RuntimeError(f"Expected one mutation location for {name}")
            path.write_text(source.replace(old, new, 1))
            mutated = _run_test(candidate, target)
            # Exit 1 means test failure; collection/runtime setup errors are not evidence.
            if mutated.returncode != 1 or f"FAILED {target}" not in mutated.stdout:
                raise RuntimeError(f"Mutation was not detected by its test: {name}\n{mutated.stdout}\n{mutated.stderr}")
            print(f"DETECTED {name}: control passed; mutated test failed")

    after = {path: sha256(path.read_bytes()).hexdigest() for path in sources}
    if before != after:
        raise RuntimeError("Actual source changed during the disposable-copy check")
    print(f"{len(_MUTATIONS)}/{len(_MUTATIONS)} selected mutations detected; actual source unchanged")


if __name__ == "__main__":
    main()
