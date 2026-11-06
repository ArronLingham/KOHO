from move_money import MoneyService

service = MoneyService("money.db")  # Opens or creates the SQLite database.

# Open accounts with starting balances in dollars.
sender = service.open_account(100.00)
recipient = service.open_account(25.00)

# Send $12.13 from the sender to the recipient.
receipt = service.transfer(
    "payment-003",
    sender.account_id,
    recipient.account_id,
    12.13,
)

# Look up current balance and transaction history.
print(service.get_balance(sender.account_id))
print(service.get_history(sender.account_id))
print(service.get_balance(recipient.account_id))