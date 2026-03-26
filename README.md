# Rejeki

AI Personal Finance Agent — bicara natural ke Claude Desktop, Claude yang jadi otaknya.

## Masalah yang Dipecahkan

Aplikasi keuangan biasa (Money Manager, dll.) bisa track pengeluaran, tapi **tidak bisa jawab pertanyaan nyata**:

- "Bisa afford beli ini gak?"
- "Berapa uang yang *beneran* bisa gue pakai sekarang?"
- "Kalau beli ini sekarang, saving goal gue kena gak?"

Rejeki menjawab itu semua.

## Konsep Utama: True Available Money

```
True Available = Total Saldo
              − Alokasi Saving Goals
              − Kewajiban Tetap belum dibayar
              − Upcoming Expenses bulan ini
              − Estimasi sisa budget kategori
```

Bukan sekadar "saldo rekening", tapi uang yang **benar-benar bebas dipakai**.

## Framework: Pay Yourself First

```
Income
  └─ Kewajiban Tetap (cicilan, langganan, dll.)
       └─ Saving Goals (Emergency Fund → Nikah → Rumah → ...)
            └─ True Available (baru ini yang boleh dihabiskan)
```

Saving Goals diprioritaskan: **Emergency Fund selalu #1**.

## Stack

| Komponen | Teknologi |
|----------|-----------|
| MCP Server | Python + FastMCP |
| Database | SQLite (dev) → PostgreSQL (prod) |
| Transport | stdio (dev) → HTTP+OAuth (prod) |
| AI Client | Claude Desktop |

## Arsitektur

```
Claude Desktop  ←→  MCP Server (Rejeki)  ←→  SQLite
     (otak)            (executor)            (data)
```

MCP server hanya eksekutor — menyimpan dan mengambil data. Semua reasoning, analisis, dan keputusan ada di Claude.

## MCP Tools (15)

| Tool | Fungsi |
|------|--------|
| `finance_add_transaction` | Catat transaksi (income/expense/transfer) |
| `finance_get_true_available` | Hitung True Available Money |
| `finance_can_afford` | Cek apakah bisa afford sesuatu |
| `finance_get_summary` | Ringkasan keuangan periode tertentu |
| `finance_get_accounts` | List semua akun dan saldo |
| `finance_set_budget` | Set budget per kategori |
| `finance_get_budget_status` | Status pemakaian budget |
| `finance_add_saving_goal` | Tambah saving goal baru |
| `finance_update_saving_goal` | Update progress saving goal |
| `finance_get_saving_goals` | List semua saving goals |
| `finance_add_fixed_expense` | Tambah kewajiban tetap |
| `finance_add_upcoming_expense` | Tambah pengeluaran mendatang |
| `finance_manage_wishlist` | Kelola wishlist |
| `finance_add_asset` | Catat aset (dicatat di harga beli) |
| `finance_get_spending_trend` | Analisis tren pengeluaran |

## Database Schema

```
accounts          → rekening (BCA, GoPay, Cash, dll.)
transactions      → semua transaksi (income/expense/transfer)
categories        → kategori pengeluaran
budgets           → budget per kategori per bulan
saving_goals      → tujuan tabungan + prioritas
fixed_expenses    → kewajiban tetap bulanan
upcoming_expenses → pengeluaran mendatang yang sudah diketahui
wishlist          → daftar keinginan
assets            → aset (dicatat di cost basis, bukan market value)
```

## Roadmap

- [x] Desain arsitektur & konsep
- [ ] v1 MVP — local, stdio, SQLite, semua core tools
- [ ] Testing & validasi dengan data nyata
- [ ] v2 — HTTP transport + basic auth
- [ ] v3 — PostgreSQL + multi-device

## Contoh Penggunaan

```
User: "Gue mau beli sepatu Rp800rb, bisa gak?"

Claude: Gue cek dulu ya...
        - Saldo total: Rp3.2jt
        - Saving alokasi bulan ini: Rp1jt
        - Tagihan listrik belum bayar: Rp350rb
        - Budget makan sisa: Rp200rb

        True Available lo: Rp1.65jt
        Sepatu Rp800rb? Bisa, masih sisa Rp850rb.
        Tapi kalau beli, emergency fund lo mundur ~2 minggu dari target.
```
