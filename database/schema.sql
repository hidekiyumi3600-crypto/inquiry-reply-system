CREATE TABLE IF NOT EXISTS inquiries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    inquiry_number TEXT UNIQUE NOT NULL,
    status TEXT NOT NULL DEFAULT 'open',          -- open / replied / completed
    category TEXT,
    subject TEXT,
    customer_name TEXT,
    customer_email TEXT,
    item_name TEXT,
    item_number TEXT,
    order_number TEXT,
    body TEXT,
    inquiry_date TEXT,
    raw_json TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS replies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    inquiry_number TEXT NOT NULL,
    body TEXT NOT NULL,
    is_draft INTEGER NOT NULL DEFAULT 1,          -- 1=下書き, 0=送信済み
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (inquiry_number) REFERENCES inquiries(inquiry_number)
);

CREATE TABLE IF NOT EXISTS sync_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    synced_at TEXT DEFAULT (datetime('now')),
    count INTEGER DEFAULT 0,
    status TEXT DEFAULT 'success',
    message TEXT
);
