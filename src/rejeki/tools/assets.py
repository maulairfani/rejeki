from datetime import date
from rejeki.database import execute, fetchall


def add_asset(name: str, type: str, cost_basis: float, quantity: float, date_acquired: str | None = None) -> dict:
    acquired = date_acquired or date.today().isoformat()
    id = execute(
        "INSERT INTO assets (name, type, cost_basis, quantity, date_acquired) VALUES (?, ?, ?, ?, ?)",
        (name, type, cost_basis, quantity, acquired),
    )
    return {"id": id, "name": name, "type": type, "cost_basis": cost_basis, "quantity": quantity}


def get_assets() -> dict:
    rows = fetchall("SELECT * FROM assets ORDER BY type, name")
    total_cost_basis = sum(r["cost_basis"] for r in rows)
    return {"assets": rows, "total_cost_basis": total_cost_basis}
