from fastmcp import FastMCP
from rejeki.database import init_db
from rejeki.tools import accounts, envelopes, transactions, scheduled, analytics, assets

init_db()
mcp = FastMCP("rejeki")


# ---------------------------------------------------------------------------
# Accounts
# ---------------------------------------------------------------------------

@mcp.tool()
def finance_add_account(name: str, type: str, initial_balance: float = 0) -> dict:
    """Tambah rekening baru. type: bank | ewallet | cash"""
    return accounts.add_account(name, type, initial_balance)


@mcp.tool()
def finance_get_accounts() -> dict:
    """List semua rekening beserta saldo dan total keseluruhan."""
    return accounts.get_accounts()


@mcp.tool()
def finance_edit_account(id: int, name: str | None = None, type: str | None = None) -> dict:
    """Edit nama atau tipe rekening."""
    return accounts.edit_account(id, name, type)


@mcp.tool()
def finance_update_balance(id: int, balance: float) -> dict:
    """Set saldo rekening langsung (rekonsiliasi manual)."""
    return accounts.update_balance(id, balance)


@mcp.tool()
def finance_delete_account(id: int) -> dict:
    """Hapus rekening."""
    return accounts.delete_account(id)


# ---------------------------------------------------------------------------
# Envelope groups
# ---------------------------------------------------------------------------

@mcp.tool()
def finance_get_groups() -> list:
    """List semua kelompok envelope."""
    return envelopes.get_groups()


@mcp.tool()
def finance_add_group(name: str, sort_order: int = 0) -> dict:
    """Tambah kelompok envelope baru."""
    return envelopes.add_group(name, sort_order)


# ---------------------------------------------------------------------------
# Envelopes — CRUD + budget view
# ---------------------------------------------------------------------------

@mcp.tool()
def finance_get_envelopes(period: str | None = None) -> dict:
    """
    Tampilkan semua envelope.
    Income sources: referensi untuk mencatat pemasukan.
    Expense envelopes per kelompok: carryover, assigned, activity, available, target.
    period format YYYY-MM (default bulan ini).
    """
    return envelopes.get_envelopes(period)


@mcp.tool()
def finance_add_envelope(name: str, type: str, icon: str | None = None, group_id: int | None = None) -> dict:
    """
    Tambah envelope baru. type: income | expense.
    group_id untuk expense (opsional — tanpa group masuk kelompok 'Lainnya').
    """
    return envelopes.add_envelope(name, type, icon, group_id)


@mcp.tool()
def finance_edit_envelope(
    id: int,
    name: str | None = None,
    icon: str | None = None,
    group_id: int | None = None,
) -> dict:
    """Edit envelope. Isi hanya field yang mau diubah."""
    return envelopes.edit_envelope(id, name, icon, group_id)


@mcp.tool()
def finance_delete_envelope(id: int) -> dict:
    """Hapus envelope beserta semua data budgetnya."""
    return envelopes.delete_envelope(id)


@mcp.tool()
def finance_set_target(
    envelope_id: int,
    target_type: str,
    target_amount: float | None = None,
    target_deadline: str | None = None,
) -> dict:
    """
    Set funding target pada envelope expense.
    target_type: 'monthly' — assign X setiap bulan.
                 'goal'    — kumpulkan X sampai deadline.
    target_deadline format YYYY-MM-DD, hanya untuk goal.
    """
    return envelopes.set_target(envelope_id, target_type, target_amount, target_deadline)


@mcp.tool()
def finance_assign_to_envelope(envelope_id: int, amount: float, period: str | None = None) -> dict:
    """
    Assign uang dari Ready to Assign ke envelope.
    Ini operasi inti Rejeki: 'give every rupiah a job'.
    Memanggil ini lagi pada period yang sama akan menimpa assigned sebelumnya.
    period format YYYY-MM (default bulan ini).
    """
    return envelopes.assign_to_envelope(envelope_id, amount, period)


@mcp.tool()
def finance_move_money(
    from_envelope_id: int,
    to_envelope_id: int,
    amount: float,
    period: str | None = None,
) -> dict:
    """
    Pindahkan uang antar envelope dalam satu period.
    Dipakai saat overspend di satu envelope dan perlu ditutup dari envelope lain.
    period format YYYY-MM (default bulan ini).
    """
    return envelopes.move_money(from_envelope_id, to_envelope_id, amount, period)


# ---------------------------------------------------------------------------
# Transactions
# ---------------------------------------------------------------------------

@mcp.tool()
def finance_add_transaction(
    amount: float,
    type: str,
    account_id: int,
    envelope_id: int | None = None,
    to_account_id: int | None = None,
    payee: str | None = None,
    memo: str | None = None,
    transaction_date: str | None = None,
) -> dict:
    """
    Catat transaksi. type: income | expense | transfer.
    envelope_id: wajib untuk expense, gunakan income source id untuk income.
    payee: penerima uang (Alfamart, Grab, dll).
    memo: catatan bebas.
    transaction_date format YYYY-MM-DD (default hari ini).
    """
    return transactions.add_transaction(
        amount, type, account_id, envelope_id, to_account_id, payee, memo, transaction_date
    )


@mcp.tool()
def finance_get_transactions(
    account_id: int | None = None,
    envelope_id: int | None = None,
    type: str | None = None,
    payee: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = 50,
) -> list:
    """
    Query transaksi. Semua filter opsional dan bisa dikombinasikan.
    payee: partial match (misal 'Grab' cocok dengan 'GrabFood').
    """
    return transactions.get_transactions(account_id, envelope_id, type, payee, date_from, date_to, limit)


@mcp.tool()
def finance_edit_transaction(
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
    """Edit transaksi yang sudah ada. Isi hanya field yang mau diubah."""
    return transactions.edit_transaction(
        id, amount, type, account_id, envelope_id, to_account_id, payee, memo, transaction_date
    )


@mcp.tool()
def finance_delete_transaction(id: int) -> dict:
    """Hapus transaksi dan balikkan efeknya ke saldo rekening."""
    return transactions.delete_transaction(id)


# ---------------------------------------------------------------------------
# Scheduled transactions
# ---------------------------------------------------------------------------

@mcp.tool()
def finance_add_scheduled_transaction(
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
    """
    Jadwalkan transaksi di masa depan.
    recurrence: once | weekly | monthly | yearly.
    scheduled_date format YYYY-MM-DD.
    """
    return scheduled.add_scheduled_transaction(
        amount, type, account_id, scheduled_date, envelope_id, to_account_id, payee, memo, recurrence
    )


@mcp.tool()
def finance_get_scheduled_transactions(include_inactive: bool = False) -> list:
    """List transaksi terjadwal, termasuk field days_until (berapa hari lagi)."""
    return scheduled.get_scheduled_transactions(include_inactive)


@mcp.tool()
def finance_approve_scheduled_transaction(id: int) -> dict:
    """
    Eksekusi scheduled transaction sebagai transaksi nyata.
    Jika recurring, otomatis jadwalkan ke occurrence berikutnya.
    """
    return scheduled.approve_scheduled_transaction(id)


@mcp.tool()
def finance_skip_scheduled_transaction(id: int) -> dict:
    """
    Lewati occurrence ini tanpa mencatat transaksi.
    Jika recurring, maju ke occurrence berikutnya.
    """
    return scheduled.skip_scheduled_transaction(id)


@mcp.tool()
def finance_delete_scheduled_transaction(id: int) -> dict:
    """Hapus scheduled transaction sepenuhnya."""
    return scheduled.delete_scheduled_transaction(id)


# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------

@mcp.tool()
def finance_get_onboarding_status() -> dict:
    """
    Cek status onboarding: rekening, targets, envelope assignment, RTA.
    Panggil ini di awal setiap sesi baru.
    """
    return analytics.get_onboarding_status()


@mcp.tool()
def finance_get_ready_to_assign(period: str | None = None) -> dict:
    """
    Hitung Ready to Assign = total saldo rekening − total available semua envelope.
    Target: nol. Setiap rupiah harus punya tugas.
    """
    return analytics.get_ready_to_assign(period)


@mcp.tool()
def finance_get_age_of_money() -> dict:
    """
    Hitung Age of Money: rata-rata berapa hari uang duduk sebelum dipakai.
    Dihitung FIFO. Target: 30+ hari.
    """
    return analytics.get_age_of_money()


@mcp.tool()
def finance_get_summary(period: str | None = None) -> dict:
    """Ringkasan bulanan: income, expense, net, breakdown per envelope. period: YYYY-MM."""
    return analytics.get_summary(period)


@mcp.tool()
def finance_get_spending_trend(envelope_id: int | None = None, months: int = 3) -> list:
    """Tren pengeluaran per envelope, N bulan ke belakang."""
    return analytics.get_spending_trend(envelope_id, months)


# ---------------------------------------------------------------------------
# Assets
# ---------------------------------------------------------------------------

@mcp.tool()
def finance_add_asset(
    name: str,
    type: str,
    cost_basis: float,
    quantity: float,
    date_acquired: str | None = None,
) -> dict:
    """Catat aset investasi (saham, reksa dana, crypto, dll) berdasarkan cost basis."""
    return assets.add_asset(name, type, cost_basis, quantity, date_acquired)


@mcp.tool()
def finance_get_assets() -> dict:
    """List semua aset dan total cost basis."""
    return assets.get_assets()


# ---------------------------------------------------------------------------

def main():
    mcp.run()


if __name__ == "__main__":
    main()
