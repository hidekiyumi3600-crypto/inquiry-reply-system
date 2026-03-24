import json
import os
import sqlite3

_db_path = None


def init_db(db_path):
    """DB初期化（Flask非依存）"""
    global _db_path
    _db_path = db_path
    _init_db()


def _get_conn():
    conn = sqlite3.connect(_db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def _init_db():
    schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
    with open(schema_path) as f:
        schema = f.read()
    conn = _get_conn()
    conn.executescript(schema)
    conn.close()


# ── Inquiries ──────────────────────────────────────────────


def upsert_inquiry(data):
    """問い合わせをINSERT or UPDATE"""
    conn = _get_conn()
    conn.execute(
        """
        INSERT INTO inquiries
            (inquiry_number, status, category, subject, customer_name,
             customer_email, item_name, item_number, order_number,
             body, inquiry_date, raw_json, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
        ON CONFLICT(inquiry_number) DO UPDATE SET
            status = excluded.status,
            category = excluded.category,
            subject = excluded.subject,
            customer_name = excluded.customer_name,
            customer_email = excluded.customer_email,
            item_name = excluded.item_name,
            item_number = excluded.item_number,
            order_number = excluded.order_number,
            body = excluded.body,
            inquiry_date = excluded.inquiry_date,
            raw_json = excluded.raw_json,
            updated_at = datetime('now')
        """,
        (
            data["inquiry_number"],
            data.get("status", "open"),
            data.get("category"),
            data.get("subject"),
            data.get("customer_name"),
            data.get("customer_email"),
            data.get("item_name"),
            data.get("item_number"),
            data.get("order_number"),
            data.get("body"),
            data.get("inquiry_date"),
            json.dumps(data.get("raw_json"), ensure_ascii=False)
            if data.get("raw_json")
            else None,
        ),
    )
    conn.commit()
    conn.close()


def get_all_inquiries():
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM inquiries ORDER BY inquiry_date DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_inquiry(inquiry_number):
    conn = _get_conn()
    row = conn.execute(
        "SELECT * FROM inquiries WHERE inquiry_number = ?", (inquiry_number,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def update_inquiry_status(inquiry_number, status):
    conn = _get_conn()
    conn.execute(
        "UPDATE inquiries SET status = ?, updated_at = datetime('now') WHERE inquiry_number = ?",
        (status, inquiry_number),
    )
    conn.commit()
    conn.close()


# ── Replies ────────────────────────────────────────────────


def save_draft(inquiry_number, body):
    conn = _get_conn()
    conn.execute(
        "INSERT INTO replies (inquiry_number, body, is_draft) VALUES (?, ?, 1)",
        (inquiry_number, body),
    )
    conn.commit()
    conn.close()


def get_drafts(inquiry_number):
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM replies WHERE inquiry_number = ? AND is_draft = 1 ORDER BY created_at DESC",
        (inquiry_number,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_sent_replies(inquiry_number):
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM replies WHERE inquiry_number = ? AND is_draft = 0 ORDER BY created_at ASC",
        (inquiry_number,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def mark_reply_sent(inquiry_number, body):
    """送信済み返信を記録"""
    conn = _get_conn()
    conn.execute(
        "INSERT INTO replies (inquiry_number, body, is_draft) VALUES (?, ?, 0)",
        (inquiry_number, body),
    )
    conn.commit()
    conn.close()


# ── Sync Log ──────────────────────────────────────────────


def log_sync(count, status="success", message=None):
    conn = _get_conn()
    conn.execute(
        "INSERT INTO sync_log (count, status, message) VALUES (?, ?, ?)",
        (count, status, message),
    )
    conn.commit()
    conn.close()


def get_inquiries_with_replies():
    """問い合わせと送信済み返信を結合して取得（CSVエクスポート用）"""
    conn = _get_conn()
    rows = conn.execute(
        """
        SELECT
            i.inquiry_number,
            i.inquiry_date,
            i.customer_name,
            i.category,
            i.subject,
            i.item_name,
            i.item_number,
            i.order_number,
            i.body AS inquiry_body,
            i.status,
            r.body AS reply_body,
            r.created_at AS reply_date
        FROM inquiries i
        LEFT JOIN replies r
            ON i.inquiry_number = r.inquiry_number AND r.is_draft = 0
        ORDER BY i.inquiry_date DESC, r.created_at ASC
        """
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_last_sync():
    conn = _get_conn()
    row = conn.execute(
        "SELECT * FROM sync_log ORDER BY synced_at DESC LIMIT 1"
    ).fetchone()
    conn.close()
    return dict(row) if row else None
