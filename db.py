import sqlite3
import os
from datetime import datetime, timezone

DB_PATH = os.getenv("DB_PATH", "stats.db")


def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS user_stats (
                chat_id     INTEGER NOT NULL,
                user_id     INTEGER NOT NULL,
                username    TEXT    DEFAULT '',
                name        TEXT    DEFAULT '',
                messages    INTEGER DEFAULT 0,
                stickers    INTEGER DEFAULT 0,
                gifs        INTEGER DEFAULT 0,
                video_notes INTEGER DEFAULT 0,
                voices      INTEGER DEFAULT 0,
                first_date  REAL,
                last_date   REAL,
                PRIMARY KEY (chat_id, user_id)
            )
        """)
        conn.commit()


def load_all_stats() -> dict:
    result: dict[int, dict[int, dict]] = {}
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM user_stats").fetchall()
    for row in rows:
        chat_id = row["chat_id"]
        user_id = row["user_id"]
        if chat_id not in result:
            result[chat_id] = {}
        result[chat_id][user_id] = {
            "messages":    row["messages"],
            "stickers":    row["stickers"],
            "gifs":        row["gifs"],
            "video_notes": row["video_notes"],
            "voices":      row["voices"],
            "first_date":  datetime.fromtimestamp(row["first_date"], tz=timezone.utc) if row["first_date"] else None,
            "last_date":   datetime.fromtimestamp(row["last_date"],  tz=timezone.utc) if row["last_date"]  else None,
            "username":    row["username"] or "",
            "name":        row["name"]     or "",
        }
    return result


def save_user_stats(chat_id: int, user_id: int, s: dict):
    first_ts = s["first_date"].timestamp() if s["first_date"] else None
    last_ts  = s["last_date"].timestamp()  if s["last_date"]  else None
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            INSERT INTO user_stats
                (chat_id, user_id, username, name,
                 messages, stickers, gifs, video_notes, voices,
                 first_date, last_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(chat_id, user_id) DO UPDATE SET
                username    = excluded.username,
                name        = excluded.name,
                messages    = excluded.messages,
                stickers    = excluded.stickers,
                gifs        = excluded.gifs,
                video_notes = excluded.video_notes,
                voices      = excluded.voices,
                first_date  = excluded.first_date,
                last_date   = excluded.last_date
        """, (
            chat_id, user_id,
            s["username"], s["name"],
            s["messages"], s["stickers"], s["gifs"], s["video_notes"], s["voices"],
            first_ts, last_ts,
        ))
        conn.commit()
