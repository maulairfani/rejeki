-- Rejeki Database Schema — Envelope Budget Edition
--
-- Table mapping:
--   envelopes       = envelope definitions (name, icon, type, target)
--   envelope_groups = groups of expense envelopes
--   budget_periods  = per-month budget data (assigned + carryover per envelope)
--   transactions    = all recorded money movements
--   scheduled_transactions = future/recurring transactions
--   accounts        = bank accounts, e-wallets, cash
--   assets          = investment assets tracked by cost basis

CREATE TABLE IF NOT EXISTS accounts (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL,
    type       TEXT NOT NULL CHECK (type IN ('bank', 'ewallet', 'cash')),
    balance    REAL NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS envelope_groups (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS envelopes (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL,
    icon            TEXT,
    type            TEXT NOT NULL CHECK (type IN ('income', 'expense')),
    group_id        INTEGER REFERENCES envelope_groups(id),
    target_type     TEXT CHECK (target_type IN ('monthly', 'goal')),
    target_amount   REAL,
    target_deadline TEXT
);

CREATE TABLE IF NOT EXISTS transactions (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    amount        REAL NOT NULL,
    type          TEXT NOT NULL CHECK (type IN ('income', 'expense', 'transfer')),
    envelope_id   INTEGER REFERENCES envelopes(id),
    account_id    INTEGER NOT NULL REFERENCES accounts(id),
    to_account_id INTEGER REFERENCES accounts(id),
    payee         TEXT,
    memo          TEXT,
    date          TEXT NOT NULL DEFAULT (date('now'))
);

-- Per-period budget data per envelope.
-- Activity (spending) is always computed from transactions — never stored here.
-- Carryover is only positive: overspend reduces RTA next month, not this table.
CREATE TABLE IF NOT EXISTS budget_periods (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    envelope_id INTEGER NOT NULL REFERENCES envelopes(id),
    period      TEXT NOT NULL,  -- YYYY-MM
    assigned    REAL NOT NULL DEFAULT 0,
    carryover   REAL NOT NULL DEFAULT 0,
    UNIQUE(envelope_id, period)
);

CREATE TABLE IF NOT EXISTS scheduled_transactions (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    amount         REAL NOT NULL,
    type           TEXT NOT NULL CHECK (type IN ('income', 'expense', 'transfer')),
    envelope_id    INTEGER REFERENCES envelopes(id),
    account_id     INTEGER NOT NULL REFERENCES accounts(id),
    to_account_id  INTEGER REFERENCES accounts(id),
    payee          TEXT,
    memo           TEXT,
    scheduled_date TEXT NOT NULL,
    recurrence     TEXT NOT NULL DEFAULT 'once' CHECK (recurrence IN ('once', 'weekly', 'monthly', 'yearly')),
    is_active      INTEGER NOT NULL DEFAULT 1,
    created_at     TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS assets (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT NOT NULL,
    type          TEXT NOT NULL,
    cost_basis    REAL NOT NULL,
    quantity      REAL NOT NULL,
    date_acquired TEXT NOT NULL DEFAULT (date('now'))
);

-- Default envelope groups
INSERT OR IGNORE INTO envelope_groups (id, name, sort_order) VALUES
    (1, 'Kebutuhan Tetap',       1),
    (2, 'Kebutuhan Sehari-hari', 2),
    (3, 'Pengeluaran Pribadi',   3),
    (4, 'Tabungan & Goals',      4),
    (5, 'Tidak Terduga',         5);

-- Default envelopes
INSERT OR IGNORE INTO envelopes (id, name, icon, type, group_id) VALUES
    -- Income sources (no group)
    (1,  'Gaji',          '💼', 'income',  NULL),
    (2,  'Freelance',     '💻', 'income',  NULL),
    (3,  'Investasi',     '📈', 'income',  NULL),
    (4,  'Lainnya',       '💰', 'income',  NULL),
    -- Kebutuhan Tetap
    (5,  'Kos/Sewa',     '🏡', 'expense', 1),
    (6,  'Tagihan',      '📄', 'expense', 1),
    (7,  'Langganan',    '🔄', 'expense', 1),
    (8,  'Kirim Ortu',   '🏠', 'expense', 1),
    -- Kebutuhan Sehari-hari
    (9,  'Makan',        '🍽️', 'expense', 2),
    (10, 'Transport',    '🚗', 'expense', 2),
    -- Pengeluaran Pribadi
    (11, 'Belanja',      '🛍️', 'expense', 3),
    (12, 'Hiburan',      '🎮', 'expense', 3),
    (13, 'Kesehatan',    '🏥', 'expense', 3),
    (14, 'Pendidikan',   '📚', 'expense', 3),
    -- Tabungan & Goals
    (15, 'Dana Darurat', '🛡️', 'expense', 4),
    (16, 'Tabungan',     '💎', 'expense', 4),
    -- Tidak Terduga
    (17, 'Lainnya',      '💸', 'expense', 5);
