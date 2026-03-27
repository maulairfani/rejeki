from datetime import date
from rejeki.database import execute, fetchall, fetchone


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _current_period() -> str:
    return date.today().strftime("%Y-%m")


def _prev_period(period: str) -> str:
    year, month = map(int, period.split("-"))
    if month == 1:
        return f"{year - 1}-12"
    return f"{year}-{month - 1:02d}"


def _activity(envelope_id: int, period: str) -> float:
    """Total spending from transactions for this envelope in this period."""
    return fetchone(
        """SELECT COALESCE(SUM(amount), 0) AS total FROM transactions
           WHERE envelope_id = ? AND type = 'expense' AND strftime('%Y-%m', date) = ?""",
        (envelope_id, period),
    )["total"]


def _compute_carryover(envelope_id: int, period: str) -> float:
    """
    Carryover from the previous period — positive only.
    Envelope rule: overspend does NOT carry forward into the envelope.
    It reduces RTA next month instead.
    """
    prev = _prev_period(period)
    row = fetchone(
        "SELECT assigned, carryover FROM budget_periods WHERE envelope_id = ? AND period = ?",
        (envelope_id, prev),
    )
    if not row:
        return 0.0
    prev_available = row["carryover"] + row["assigned"] - _activity(envelope_id, prev)
    return max(0.0, prev_available)


# ---------------------------------------------------------------------------
# Groups
# ---------------------------------------------------------------------------

def get_groups() -> list:
    return fetchall("SELECT id, name, sort_order FROM envelope_groups ORDER BY sort_order")


def add_group(name: str, sort_order: int = 0) -> dict:
    id = execute(
        "INSERT INTO envelope_groups (name, sort_order) VALUES (?, ?)",
        (name, sort_order),
    )
    return {"id": id, "name": name, "sort_order": sort_order}


# ---------------------------------------------------------------------------
# Envelope CRUD
# ---------------------------------------------------------------------------

def add_envelope(name: str, type: str, icon: str | None = None, group_id: int | None = None) -> dict:
    if type not in ("income", "expense"):
        raise ValueError("type harus 'income' atau 'expense'")
    id = execute(
        "INSERT INTO envelopes (name, icon, type, group_id) VALUES (?, ?, ?, ?)",
        (name, icon, type, group_id),
    )
    return {"id": id, "name": name, "icon": icon, "type": type, "group_id": group_id}


def edit_envelope(id: int, name: str | None = None, icon: str | None = None, group_id: int | None = None) -> dict:
    env = fetchone("SELECT * FROM envelopes WHERE id = ?", (id,))
    if not env:
        raise ValueError(f"Envelope id={id} tidak ditemukan")

    new_name = name or env["name"]
    new_icon = icon if icon is not None else env["icon"]
    new_group_id = group_id if group_id is not None else env["group_id"]

    execute(
        "UPDATE envelopes SET name = ?, icon = ?, group_id = ? WHERE id = ?",
        (new_name, new_icon, new_group_id, id),
    )
    return {"id": id, "name": new_name, "icon": new_icon, "type": env["type"], "group_id": new_group_id}


def delete_envelope(id: int) -> dict:
    env = fetchone("SELECT * FROM envelopes WHERE id = ?", (id,))
    if not env:
        raise ValueError(f"Envelope id={id} tidak ditemukan")

    execute("DELETE FROM budget_periods WHERE envelope_id = ?", (id,))
    execute("DELETE FROM envelopes WHERE id = ?", (id,))
    return {"deleted_id": id, "name": env["name"]}


def set_target(
    envelope_id: int,
    target_type: str,
    target_amount: float | None = None,
    target_deadline: str | None = None,
) -> dict:
    """
    Set a funding target on an expense envelope.
    target_type: 'monthly' — assign X per month.
                 'goal'    — accumulate X by deadline.
    """
    env = fetchone("SELECT * FROM envelopes WHERE id = ?", (envelope_id,))
    if not env:
        raise ValueError(f"Envelope id={envelope_id} tidak ditemukan")
    if env["type"] != "expense":
        raise ValueError("Hanya envelope expense yang bisa punya target")

    execute(
        "UPDATE envelopes SET target_type = ?, target_amount = ?, target_deadline = ? WHERE id = ?",
        (target_type, target_amount, target_deadline, envelope_id),
    )
    return {
        "id": envelope_id,
        "name": env["name"],
        "target_type": target_type,
        "target_amount": target_amount,
        "target_deadline": target_deadline,
    }


# ---------------------------------------------------------------------------
# Budget operations
# ---------------------------------------------------------------------------

def assign_to_envelope(envelope_id: int, amount: float, period: str | None = None) -> dict:
    """
    Assign money from Ready to Assign into an envelope.
    Creates or overwrites the assigned amount for this period.
    """
    period = period or _current_period()

    env = fetchone("SELECT * FROM envelopes WHERE id = ?", (envelope_id,))
    if not env:
        raise ValueError(f"Envelope id={envelope_id} tidak ditemukan")
    if env["type"] != "expense":
        raise ValueError("Hanya envelope expense yang bisa di-assign")

    existing = fetchone(
        "SELECT id, carryover FROM budget_periods WHERE envelope_id = ? AND period = ?",
        (envelope_id, period),
    )
    if existing:
        execute("UPDATE budget_periods SET assigned = ? WHERE id = ?", (amount, existing["id"]))
        carryover = existing["carryover"]
    else:
        carryover = _compute_carryover(envelope_id, period)
        execute(
            "INSERT INTO budget_periods (envelope_id, period, assigned, carryover) VALUES (?, ?, ?, ?)",
            (envelope_id, period, amount, carryover),
        )

    act = _activity(envelope_id, period)
    return {
        "envelope": env["name"],
        "icon": env["icon"],
        "period": period,
        "carryover": carryover,
        "assigned": amount,
        "activity": act,
        "available": carryover + amount - act,
    }


def move_money(from_id: int, to_id: int, amount: float, period: str | None = None) -> dict:
    """
    Move money between envelopes within the same period.
    Used to cover overspend or rebalance budgets.
    """
    period = period or _current_period()

    from_env = fetchone("SELECT * FROM envelopes WHERE id = ?", (from_id,))
    to_env = fetchone("SELECT * FROM envelopes WHERE id = ?", (to_id,))
    if not from_env or not to_env:
        raise ValueError("Envelope tidak ditemukan")

    from_bp = fetchone(
        "SELECT id, assigned, carryover FROM budget_periods WHERE envelope_id = ? AND period = ?",
        (from_id, period),
    )
    to_bp = fetchone(
        "SELECT id, assigned, carryover FROM budget_periods WHERE envelope_id = ? AND period = ?",
        (to_id, period),
    )

    from_assigned = from_bp["assigned"] if from_bp else 0.0
    to_assigned = to_bp["assigned"] if to_bp else 0.0
    from_carryover = from_bp["carryover"] if from_bp else _compute_carryover(from_id, period)
    to_carryover = to_bp["carryover"] if to_bp else _compute_carryover(to_id, period)

    new_from = from_assigned - amount
    new_to = to_assigned + amount

    if from_bp:
        execute("UPDATE budget_periods SET assigned = ? WHERE id = ?", (new_from, from_bp["id"]))
    else:
        execute(
            "INSERT INTO budget_periods (envelope_id, period, assigned, carryover) VALUES (?, ?, ?, ?)",
            (from_id, period, new_from, from_carryover),
        )

    if to_bp:
        execute("UPDATE budget_periods SET assigned = ? WHERE id = ?", (new_to, to_bp["id"]))
    else:
        execute(
            "INSERT INTO budget_periods (envelope_id, period, assigned, carryover) VALUES (?, ?, ?, ?)",
            (to_id, period, new_to, to_carryover),
        )

    from_act = _activity(from_id, period)
    to_act = _activity(to_id, period)

    return {
        "moved": amount,
        "period": period,
        "from": {
            "envelope": from_env["name"],
            "icon": from_env["icon"],
            "assigned": new_from,
            "available": from_carryover + new_from - from_act,
        },
        "to": {
            "envelope": to_env["name"],
            "icon": to_env["icon"],
            "assigned": new_to,
            "available": to_carryover + new_to - to_act,
        },
    }


def get_envelopes(period: str | None = None) -> dict:
    """
    Full budget view for the given period.
    Returns income sources + expense envelopes grouped by envelope_group.
    Each expense envelope shows: carryover, assigned, activity, available, target status.
    """
    period = period or _current_period()

    income_sources = fetchall(
        "SELECT id, name, icon FROM envelopes WHERE type = 'income' ORDER BY id"
    )

    expense_envelopes = fetchall(
        """SELECT e.id, e.name, e.icon, e.target_type, e.target_amount, e.target_deadline,
                  g.name AS group_name, g.id AS group_id
           FROM envelopes e
           LEFT JOIN envelope_groups g ON e.group_id = g.id
           WHERE e.type = 'expense'
           ORDER BY COALESCE(g.sort_order, 999), e.id""",
    )

    groups: dict = {}
    total_assigned = 0.0
    total_available = 0.0

    for env in expense_envelopes:
        bp = fetchone(
            "SELECT assigned, carryover FROM budget_periods WHERE envelope_id = ? AND period = ?",
            (env["id"], period),
        )
        carryover = bp["carryover"] if bp else _compute_carryover(env["id"], period)
        assigned = bp["assigned"] if bp else 0.0
        act = _activity(env["id"], period)
        available = carryover + assigned - act

        group_name = env["group_name"] or "Lainnya"
        if group_name not in groups:
            groups[group_name] = {"group_id": env["group_id"], "envelopes": [], "group_available": 0.0}

        target = None
        if env["target_type"]:
            if env["target_type"] == "monthly":
                funded = assigned >= (env["target_amount"] or 0)
            else:
                funded = available >= (env["target_amount"] or 0)
            target = {
                "type": env["target_type"],
                "amount": env["target_amount"],
                "deadline": env["target_deadline"],
                "status": "funded" if funded else "underfunded",
            }

        groups[group_name]["envelopes"].append({
            "id": env["id"],
            "name": env["name"],
            "icon": env["icon"],
            "carryover": carryover,
            "assigned": assigned,
            "activity": act,
            "available": available,
            "target": target,
        })
        groups[group_name]["group_available"] += available
        total_assigned += assigned
        total_available += available

    return {
        "period": period,
        "income_sources": income_sources,
        "groups": groups,
        "total_assigned": total_assigned,
        "total_available": total_available,
    }
