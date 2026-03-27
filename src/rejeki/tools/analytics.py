from datetime import date, datetime
from rejeki.database import fetchone, fetchall


def _current_period() -> str:
    return date.today().strftime("%Y-%m")


def _prev_period(period: str) -> str:
    year, month = map(int, period.split("-"))
    if month == 1:
        return f"{year - 1}-12"
    return f"{year}-{month - 1:02d}"


def _activity(envelope_id: int, period: str) -> float:
    return fetchone(
        """SELECT COALESCE(SUM(amount), 0) AS total FROM transactions
           WHERE envelope_id = ? AND type = 'expense' AND strftime('%Y-%m', date) = ?""",
        (envelope_id, period),
    )["total"]


def _envelope_available(envelope_id: int, period: str) -> float:
    """Compute available balance for an envelope in a period, including carryover."""
    bp = fetchone(
        "SELECT assigned, carryover FROM budget_periods WHERE envelope_id = ? AND period = ?",
        (envelope_id, period),
    )
    if bp:
        carryover = bp["carryover"]
        assigned = bp["assigned"]
    else:
        prev = _prev_period(period)
        prev_bp = fetchone(
            "SELECT assigned, carryover FROM budget_periods WHERE envelope_id = ? AND period = ?",
            (envelope_id, prev),
        )
        if prev_bp:
            prev_act = _activity(envelope_id, prev)
            carryover = max(0.0, prev_bp["carryover"] + prev_bp["assigned"] - prev_act)
        else:
            carryover = 0.0
        assigned = 0.0

    return carryover + assigned - _activity(envelope_id, period)


# ---------------------------------------------------------------------------
# Public tools
# ---------------------------------------------------------------------------

def get_ready_to_assign(period: str | None = None) -> dict:
    """
    Ready to Assign = total account balance − Σ available across all expense envelopes.
    Goal: bring to zero. Every rupiah must have a job.
    Positive = unassigned money floating. Negative = overspent.
    """
    period = period or _current_period()

    total_balance = fetchone("SELECT COALESCE(SUM(balance), 0) AS total FROM accounts")["total"]
    envelopes = fetchall("SELECT id FROM envelopes WHERE type = 'expense'")
    total_available = sum(_envelope_available(e["id"], period) for e in envelopes)

    rta = total_balance - total_available
    return {
        "period": period,
        "total_balance": total_balance,
        "total_envelope_available": total_available,
        "ready_to_assign": rta,
        "is_zero": abs(rta) < 1,
        "is_overspent": rta < -1,
    }


def get_age_of_money() -> dict:
    """
    Average days money sits in accounts before being spent.
    Calculated FIFO: income dollars are matched to expense dollars chronologically.
    Target: 30+ days means you're not living paycheck-to-paycheck.
    """
    incomes = fetchall(
        "SELECT date, amount FROM transactions WHERE type = 'income' ORDER BY date ASC, id ASC"
    )
    expenses = fetchall(
        "SELECT date, amount FROM transactions WHERE type = 'expense' ORDER BY date ASC, id ASC"
    )

    if not incomes or not expenses:
        return {"age_of_money": None, "message": "Belum cukup data transaksi"}

    pool = [[row["date"], float(row["amount"])] for row in incomes]
    pool_ptr = 0
    expense_ages: list[float] = []

    for exp in expenses:
        exp_date = datetime.fromisoformat(exp["date"])
        remaining = float(exp["amount"])
        weighted_age = 0.0
        ptr = pool_ptr

        while remaining > 0.001 and ptr < len(pool):
            if pool[ptr][1] <= 0.001:
                ptr += 1
                pool_ptr = ptr
                continue
            inc_date = datetime.fromisoformat(pool[ptr][0])
            used = min(remaining, pool[ptr][1])
            weighted_age += used * max(0, (exp_date - inc_date).days)
            remaining -= used
            pool[ptr][1] -= used
            if pool[ptr][1] <= 0.001:
                ptr += 1
                pool_ptr = ptr

        if float(exp["amount"]) > 0:
            expense_ages.append(weighted_age / float(exp["amount"]))

    if not expense_ages:
        return {"age_of_money": None, "message": "Belum ada pengeluaran"}

    recent = expense_ages[-10:]
    aom = round(sum(recent) / len(recent))

    if aom < 10:
        status = "paycheck_to_paycheck"
    elif aom < 30:
        status = "mendekati_buffer"
    elif aom < 60:
        status = "sehat"
    else:
        status = "sangat_sehat"

    return {
        "age_of_money": aom,
        "unit": "hari",
        "based_on": f"{len(recent)} transaksi terakhir",
        "status": status,
        "milestone_30_days": aom >= 30,
    }


def get_summary(period: str | None = None) -> dict:
    """Monthly income/expense summary with breakdown by envelope."""
    period = period or _current_period()

    income = fetchone(
        "SELECT COALESCE(SUM(amount), 0) AS total FROM transactions WHERE type = 'income' AND strftime('%Y-%m', date) = ?",
        (period,),
    )["total"]

    expense = fetchone(
        "SELECT COALESCE(SUM(amount), 0) AS total FROM transactions WHERE type = 'expense' AND strftime('%Y-%m', date) = ?",
        (period,),
    )["total"]

    by_envelope = fetchall(
        """SELECT e.name AS envelope, e.icon, COALESCE(SUM(t.amount), 0) AS total
           FROM transactions t
           JOIN envelopes e ON t.envelope_id = e.id
           WHERE t.type = 'expense' AND strftime('%Y-%m', t.date) = ?
           GROUP BY e.id ORDER BY total DESC""",
        (period,),
    )

    return {
        "period": period,
        "income": income,
        "expense": expense,
        "net": income - expense,
        "expense_by_envelope": by_envelope,
    }


def get_spending_trend(envelope_id: int | None = None, months: int = 3) -> list[dict]:
    """Spending per envelope over the past N months."""
    return fetchall(
        """SELECT strftime('%Y-%m', t.date) AS period,
                  e.name AS envelope, e.icon,
                  COALESCE(SUM(t.amount), 0) AS total
           FROM transactions t
           JOIN envelopes e ON t.envelope_id = e.id
           WHERE t.type = 'expense'
             AND (? IS NULL OR t.envelope_id = ?)
             AND t.date >= date('now', ? || ' months')
           GROUP BY period, t.envelope_id
           ORDER BY period DESC, total DESC""",
        (envelope_id, envelope_id, f"-{months}"),
    )


def get_onboarding_status() -> dict:
    """
    Check how far along the initial setup is.
    Call this at the start of a session to decide whether to guide the user.
    """
    accounts = fetchall("SELECT id, name, balance FROM accounts")
    has_accounts = len(accounts) > 0
    has_balance = any(a["balance"] > 0 for a in accounts)
    total_balance = sum(a["balance"] for a in accounts)

    has_targets = fetchone(
        "SELECT COUNT(*) AS n FROM envelopes WHERE type='expense' AND target_type IS NOT NULL"
    )["n"] > 0

    any_assigned = fetchone("SELECT COUNT(*) AS n FROM budget_periods")["n"] > 0

    period = _current_period()
    envelopes = fetchall("SELECT id FROM envelopes WHERE type = 'expense'")
    total_available = sum(_envelope_available(e["id"], period) for e in envelopes)
    rta = total_balance - total_available
    all_assigned = has_balance and abs(rta) < 1

    steps = [
        {
            "step": 1,
            "title": "Tambah rekening",
            "done": has_accounts,
            "hint": "Tambahkan rekening kamu (BCA, GoPay, Cash, dll) beserta saldo saat ini.",
        },
        {
            "step": 2,
            "title": "Set target per envelope",
            "done": has_targets,
            "hint": "Set target bulanan atau goal untuk tiap envelope pengeluaran.",
        },
        {
            "step": 3,
            "title": "Assign uang ke envelope",
            "done": any_assigned,
            "hint": "Assign uang dari Ready to Assign ke envelope-envelope sampai RTA = 0.",
        },
        {
            "step": 4,
            "title": "RTA = nol",
            "done": all_assigned,
            "hint": "Setiap rupiah harus punya tugas. Pastikan Ready to Assign mencapai nol.",
        },
    ]

    completed = sum(1 for s in steps if s["done"])
    next_step = next((s for s in steps if not s["done"]), None)

    return {
        "is_complete": completed == len(steps),
        "completed_steps": completed,
        "total_steps": len(steps),
        "steps": steps,
        "next": next_step,
        "ready_to_assign": rta if has_accounts else None,
    }
