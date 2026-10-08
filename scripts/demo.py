"""Demonstrate the public library using a fresh, disposable database."""

from pathlib import Path
from tempfile import TemporaryDirectory

from move_money import (
    InsufficientFunds, InvalidInput, MoneyService, TransferConflict, TransferReceipt,
)


def _receipt_text(receipt: TransferReceipt) -> str:
    return (
        f"sequence={receipt.sequence}, transfer_id={receipt.transfer_id}, "
        f"sender_id={receipt.sender_id}, recipient_id={receipt.recipient_id}, "
        f"amount_cents={receipt.amount_cents}"
    )


def _state(service: MoneyService, account_ids: tuple[int, ...]):
    return [(service.get_balance(account_id), service.get_history(account_id))
            for account_id in account_ids]


def main() -> None:
    print("Move the Money demo: all amounts are CAD cents")
    with TemporaryDirectory(prefix="move-money-demo-") as directory:
        service = MoneyService(Path(directory) / "demo.db")
        sender = service.open_account(10_000)
        recipient = service.open_account(0)
        account_ids = (sender.account_id, recipient.account_id)
        for account_id, amount in zip(account_ids, (10_000, 0)):
            if service.get_balance(account_id) != amount or service.get_history(account_id):
                raise RuntimeError("Opening balance or empty history did not match the demo")
            print(f"Opened account {account_id}: {amount} cents; history empty")

        receipt = service.transfer("demo-payment", *account_ids, 8000)
        print(f"Transfer committed: {_receipt_text(receipt)}")
        after_transfer = _state(service, account_ids)
        if [balance for balance, _ in after_transfer] != [2000, 8000]:
            raise RuntimeError("Transfer balances did not match the demo")

        replay = service.transfer("demo-payment", *account_ids, 8000)
        if replay != receipt or _state(service, account_ids) != after_transfer:
            raise RuntimeError("Replay did not return the original receipt without effects")
        print("Replay: original receipt returned; balances and histories unchanged")

        rejected_requests = [
            ("Changed amount", TransferConflict,
             lambda: service.transfer("demo-payment", *account_ids, 8001)),
            ("Overspend", InsufficientFunds,
             lambda: service.transfer("demo-overspend", *account_ids, 2001)),
            # An intentional wrong-type request demonstrates public validation.
            ("Money string", InvalidInput,
             lambda: service.transfer("demo-string", *account_ids, "1")),
        ]
        for label, expected_error, attempt in rejected_requests:
            try:
                attempt()
            except expected_error as error:
                if _state(service, account_ids) != after_transfer:
                    raise RuntimeError(f"{label} rejection changed stored state") from error
                print(f"{label} rejected: {type(error).__name__}: {error}")
            else:
                raise RuntimeError(f"{label} unexpectedly succeeded")

        total = 0
        for account_id in account_ids:
            balance = service.get_balance(account_id)
            total += balance
            print(f"Balance account {account_id}: {balance} cents")
            history = service.get_history(account_id)
            expected_direction = "outgoing" if account_id == sender.account_id else "incoming"
            if len(history) != 1 or history[0].transfer != receipt or history[0].direction != expected_direction:
                raise RuntimeError("History did not match the single successful transfer")
            print(f"History account {account_id}: {history[0].direction}; {_receipt_text(history[0].transfer)}")
        if total != 10_000:
            raise RuntimeError("The demo did not conserve its opening total")
        print(f"Conserved total: {total} cents; one successful transfer")

    if Path(directory).exists():
        raise RuntimeError("Demo database directory was not removed")
    print("Demo checks passed; disposable database removed")


if __name__ == "__main__":
    main()
