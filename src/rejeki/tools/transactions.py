from datetime import date
from rejeki.database import execute, fetchall, fetchone


def add_transaction(
    amount: float,
    type: str,
    account_id: int,
    envelope_id: int | None = None,
    to_account_id: int | None = None,
    payee: str | None = None,
    memo: str | None = None,
    transaction_date: str | None = None,
) -> dict:
    txn_date = transaction_date or date.today().isoformat()

    txn_id = execute(
        """INSERT INTO transactions
           (amount, type, envelope_id, account_id, to_account_id, payee, memo, date)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (amount, type, envelope_id, account_id, to_account_id, payee, memo, txn_date),
    )

    if type == "expense":
        execute("UPDATE accounts SET balance = balance - ? WHERE id = ?", (amount, account_id))
    elif type == "income":
        execute("UPDATE accounts SET balance = balance + ? WHERE id = ?", (amount, account_id))
    elif type == "transfer":
        execute("UPDATE accounts SET balance = balance - ? WHERE id = ?", (amount, account_id))
        execute("UPDATE accounts SET balance = balance + ? WHERE id = ?", (amount, to_account_id))

    account = fetchone("SELECT name, balance FROM accounts WHERE id = ?", (account_id,))
    return {
        "id": txn_id,
        "amount": amount,
        "type": type,
        "payee": payee,
        "memo": memo,
        "date": txn_date,
        "account": account["name"],
        "account_balance_after": account["balance"],
    }


def _reverse_balance(txn: dict) -> None:
    t = txn["type"]
    if t == "expense":
        execute("UPDATE accounts SET balance = balance + ? WHERE id = ?", (txn["amount"], txn["account_id"]))
    elif t == "income":
        execute("UPDATE accounts SET balance = balance - ? WHERE id = ?", (txn["amount"], txn["account_id"]))
    elif t == "transfer":
        execute("UPDATE accounts SET balance = balance + ? WHERE id = ?", (txn["amount"], txn["account_id"]))
        execute("UPDATE accounts SET balance = balance - ? WHERE id = ?", (txn["amount"], txn["to_account_id"]))


def _apply_balance(amount: float, type: str, account_id: int, to_account_id: int | None) -> None:
    if type == "expense":
        execute("UPDATE accounts SET balance = balance - ? WHERE id = ?", (amount, account_id))
    elif type == "income":
        execute("UPDATE accounts SET balance = balance + ? WHERE id = ?", (amount, account_id))
    elif type == "transfer":
        execute("UPDATE accounts SET balance = balance - ? WHERE id = ?", (amount, account_id))
        execute("UPDATE accounts SET balance = balance + ? WHERE id = ?", (amount, to_account_id))


def edit_transaction(
    id: int,
    amount: float | None = None,
    type: str | None = None,
    account_id: int | None = None,
    envelope_id: int | None = None,
    to_account_id: int | None = None,
    payee: str | None = None,
    memo: str | None = None,
    transaction_date: str | None = None,
) -> dict:
    old = fetchone("SELECT * FROM transactions WHERE id = ?", (id,))
    if not old:
        raise ValueError(f"Transaksi id={id} tidak ditemukan")

    _reverse_balance(old)

    new_amount = amount if amount is not None else old["amount"]
    new_type = type or old["type"]
    new_account_id = account_id if account_id is not None else old["account_id"]
    new_to_account_id = to_account_id if to_account_id is not None else old["to_account_id"]
    new_envelope_id = envelope_id if envelope_id is not None else old["envelope_id"]
    new_payee = payee if payee is not None else old["payee"]
    new_memo = memo if memo is not None else old["memo"]
    new_date = transaction_date or old["date"]

    execute(
        """UPDATE transactions SET amount=?, type=?, account_id=?, to_account_id=?,
           envelope_id=?, payee=?, memo=?, date=? WHERE id=?""",
        (new_amount, new_type, new_account_id, new_to_account_id, new_envelope_id,
         new_payee, new_memo, new_date, id),
    )
    _apply_balance(new_amount, new_type, new_account_id, new_to_account_id)

    account = fetchone("SELECT name, balance FROM accounts WHERE id = ?", (new_account_id,))
    return {
        "id": id,
        "amount": new_amount,
        "type": new_type,
        "payee": new_payee,
        "memo": new_memo,
        "date": new_date,
        "account": account["name"],
        "account_balance_after": account["balance"],
    }


def delete_transaction(id: int) -> dict:
    txn = fetchone("SELECT * FROM transactions WHERE id = ?", (id,))
    if not txn:
        raise ValueError(f"Transaksi id={id} tidak ditemukan")

    _reverse_balance(txn)
    execute("DELETE FROM transactions WHERE id = ?", (id,))

    account = fetchone("SELECT name, balance FROM accounts WHERE id = ?", (txn["account_id"],))
    return {
        "deleted_id": id,
        "account": account["name"],
        "account_balance_after": account["balance"],
    }


def get_transactions(
    account_id: int | None = None,
    envelope_id: int | None = None,
    type: str | None = None,
    payee: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = 50,
) -> list[dict]:
    conditions = []
    params = []

    if account_id:
        conditions.append("t.account_id = ?")
        params.append(account_id)
    if envelope_id:
        conditions.append("t.envelope_id = ?")
        params.append(envelope_id)
    if type:
        conditions.append("t.type = ?")
        params.append(type)
    if payee:
        conditions.append("t.payee LIKE ?")
        params.append(f"%{payee}%")
    if date_from:
        conditions.append("t.date >= ?")
        params.append(date_from)
    if date_to:
        conditions.append("t.date <= ?")
        params.append(date_to)

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    params.append(limit)

    return fetchall(
        f"""SELECT t.id, t.amount, t.type, t.payee, t.memo, t.date,
                   a.name AS account, e.name AS envelope, e.icon AS envelope_icon
            FROM transactions t
            LEFT JOIN accounts a ON t.account_id = a.id
            LEFT JOIN envelopes e ON t.envelope_id = e.id
            {where}
            ORDER BY t.date DESC, t.id DESC
            LIMIT ?""",
        tuple(params),
    )
