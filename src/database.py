import sqlite3
import os
from datetime import datetime
from typing import Optional
from config import DATABASE_PATH


def get_connection() -> sqlite3.Connection:
    """データベース接続を取得"""
    os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """データベースの初期化"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reservations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            user_name TEXT NOT NULL,
            channel_id TEXT NOT NULL,
            event_name TEXT NOT NULL,
            start_time DATETIME NOT NULL,
            end_time DATETIME NOT NULL,
            reminder_minutes INTEGER DEFAULT 15,
            reminder_sent BOOLEAN DEFAULT FALSE,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_start_time ON reservations(start_time)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_user_id ON reservations(user_id)
    """)

    conn.commit()
    conn.close()


def create_reservation(
    user_id: str,
    user_name: str,
    channel_id: str,
    event_name: str,
    start_time: datetime,
    end_time: datetime,
    reminder_minutes: int = 15
) -> int:
    """予約を作成"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO reservations (user_id, user_name, channel_id, event_name, start_time, end_time, reminder_minutes)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (user_id, user_name, channel_id, event_name, start_time.isoformat(), end_time.isoformat(), reminder_minutes))

    reservation_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return reservation_id


def get_reservation(reservation_id: int) -> Optional[dict]:
    """予約を取得"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM reservations WHERE id = ?", (reservation_id,))
    row = cursor.fetchone()
    conn.close()

    return dict(row) if row else None


def get_reservations_by_date(date: str) -> list[dict]:
    """指定日の予約一覧を取得"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM reservations
        WHERE DATE(start_time) = ?
        ORDER BY start_time
    """, (date,))

    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


def get_reservations_by_user(user_id: str) -> list[dict]:
    """指定ユーザーの予約一覧を取得（未来の予約のみ）"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM reservations
        WHERE user_id = ? AND start_time > datetime('now', 'localtime')
        ORDER BY start_time
    """, (user_id,))

    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


def delete_reservation(reservation_id: int, user_id: str) -> Optional[dict]:
    """予約を削除（本人のみ可能）、削除した予約情報を返す"""
    conn = get_connection()
    cursor = conn.cursor()

    # まず予約情報を取得
    cursor.execute("SELECT * FROM reservations WHERE id = ? AND user_id = ?", (reservation_id, user_id))
    row = cursor.fetchone()

    if not row:
        conn.close()
        return None

    reservation = dict(row)

    # 削除実行
    cursor.execute("DELETE FROM reservations WHERE id = ? AND user_id = ?", (reservation_id, user_id))
    conn.commit()
    conn.close()

    return reservation


def check_conflict(start_time: datetime, end_time: datetime, exclude_id: Optional[int] = None) -> Optional[dict]:
    """予約の重複をチェック"""
    conn = get_connection()
    cursor = conn.cursor()

    query = """
        SELECT * FROM reservations
        WHERE (
            (start_time < ? AND end_time > ?) OR
            (start_time < ? AND end_time > ?) OR
            (start_time >= ? AND end_time <= ?)
        )
    """
    params = [
        end_time.isoformat(), start_time.isoformat(),
        end_time.isoformat(), start_time.isoformat(),
        start_time.isoformat(), end_time.isoformat()
    ]

    if exclude_id:
        query += " AND id != ?"
        params.append(exclude_id)

    cursor.execute(query, params)
    row = cursor.fetchone()
    conn.close()

    return dict(row) if row else None


def get_pending_reminders() -> list[dict]:
    """未送信のリマインダーを取得"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM reservations
        WHERE reminder_sent = FALSE
        AND datetime(start_time, '-' || reminder_minutes || ' minutes') <= datetime('now', 'localtime')
        AND start_time > datetime('now', 'localtime')
    """)

    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


def mark_reminder_sent(reservation_id: int):
    """リマインダー送信済みにマーク"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE reservations SET reminder_sent = TRUE WHERE id = ?
    """, (reservation_id,))

    conn.commit()
    conn.close()


if __name__ == "__main__":
    init_db()
    print("Database initialized successfully!")
