import calendar
from datetime import date, timedelta
from rejeki.database import execute, fetchall, fetchone
from rejeki.tools.transactions import add_transaction


def _next_date(date_str: str, recurrence: str) -> str:
    d = date.fromisoformat(date_str)
    if recurrence == "weekly":
        return (d + timedelta(weeks=1)).isoformat()
    elif recurrence == "monthly":
        month = d.month % 12 + 1
        year = d.year if d.month < 12 else d.year + 1
        day = min(d.day, calendar.monthrange(year, month)[1])
        return date(year, month, day).isoformat()
    elif recurrence == "yearly":
        try:
            return date(d.year + 1, d.month, d.day).isoformat()
        except ValueError:
            return date(d.year + 1, d.month, 28).isoformat()
    return date_str


def add_scheduled_transaction(
    amount: float,
    type: str,
    account_id: int,
    scheduled_date: str,
    envelope_id: int | None = None,
    to_account_id: int | None = None,
    payee: str | None = None,
    memo: str | None = None,
    recurrence: str = "once",
) -> dict:
    id = execute(
        """INSERT INTO scheduled_transactions
           (amount, type, envelope_id, account_id, to_account_id, payee, memo, scheduled_date, recurrence)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (amount, type, envelope_id, account_id, to_account_id, payee, memo, scheduled_date, recurrence),
    )
    return {
        "id": id,
        "amount": amount,
        "type": type,
        "payee": payee,
        "scheduled_date": scheduled_date,
        "recurrence": recurrence,
    }


def get_scheduled_transactions(include_inactive: bool = False) -> list[dict]:
    today = date.today()
    where = "" if include_inactive else "WHERE s.is_active = 1"
    rows = fetchall(
        f"""SELECT s.id, s.amount, s.type, s.payee, s.memo, s.scheduled_date,
                   s.recurrence, s.is_active,
                   e.name AS envelope, e.icon AS envelope_icon,
                   a.name AS account, a2.name AS to_account
            FROM scheduled_transactions s
            LEFT JOIN envelopes e ON s.envelope_id = e.id
            LEFT JOIN accounts a ON s.account_id = a.id
            LEFT JOIN accounts a2 ON s.to_account_id = a2.id
            {where}
            ORDER BY s.scheduled_date ASC""",
    )
    for r in rows:
        r["days_until"] = (date.fromisoformat(r["scheduled_date"]) - today).days
    return rows


def approve_scheduled_transaction(id: int) -> dict:
    """
    Execute as a real transaction.
    If recurring, automatically advance to the next occurrence date.
    """
    sched = fetchone("SELECT * FROM scheduled_transactions WHERE id = ? AND is_active = 1", (id,))
    if not sched:
        raise ValueError(f"Scheduled transaction id={id} tidak ditemukan atau sudah tidak aktif")

    txn = add_transaction(
        amount=sched["amount"],
        type=sched["type"],
        account_id=sched["account_id"],
        envelope_id=sched["envelope_id"],
        to_account_id=sched["to_account_id"],
        payee=sched["payee"],
        memo=sched["memo"],
        transaction_date=sched["scheduled_date"],
    )

    if sched["recurrence"] == "once":
        execute("UPDATE scheduled_transactions SET is_active = 0 WHERE id = ?", (id,))
        next_date = None
    else:
        next_date = _next_date(sched["scheduled_date"], sched["recurrence"])
        execute("UPDATE scheduled_transactions SET scheduled_date = ? WHERE id = ?", (next_date, id))

    return {"transaction": txn, "next_scheduled": next_date}


def skip_scheduled_transaction(id: int) -> dict:
    """
    Skip this occurrence without recording a transaction.
    If recurring, advance to the next occurrence date.
    """
    sched = fetchone("SELECT * FROM scheduled_transactions WHERE id = ? AND is_active = 1", (id,))
    if not sched:
        raise ValueError(f"Scheduled transaction id={id} tidak ditemukan atau sudah tidak aktif")

    if sched["recurrence"] == "once":
        execute("UPDATE scheduled_transactions SET is_active = 0 WHERE id = ?", (id,))
        return {"id": id, "status": "skipped_and_cancelled"}

    next_date = _next_date(sched["scheduled_date"], sched["recurrence"])
    execute("UPDATE scheduled_transactions SET scheduled_date = ? WHERE id = ?", (next_date, id))
    return {"id": id, "status": "skipped", "next_scheduled": next_date}


def delete_scheduled_transaction(id: int) -> dict:
    sched = fetchone("SELECT * FROM scheduled_transactions WHERE id = ?", (id,))
    if not sched:
        raise ValueError(f"Scheduled transaction id={id} tidak ditemukan")
    execute("DELETE FROM scheduled_transactions WHERE id = ?", (id,))
    return {"deleted_id": id, "payee": sched["payee"]}
