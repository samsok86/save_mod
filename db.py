import sqlite3
import os
from datetime import datetime, timezone

LOCAL_DB = os.environ.get("DB_PATH", "stats.db")


def _connect() -> sqlite3.Connection:
    return sqlite3.connect(LOCAL_DB)


def init_db():
    conn = _connect()
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
    conn.close()


def load_all_stats() -> dict:
    conn = _connect()
    rows = conn.execute(
        "SELECT chat_id, user_id, username, name, "
        "messages, stickers, gifs, video_notes, voices, "
        "first_date, last_date FROM user_stats"
    ).fetchall()
    conn.close()

    result: dict[int, dict[int, dict]] = {}
    for row in rows:
        (chat_id, user_id, username, name,
         messages, stickers, gifs, video_notes, voices,
         first_date_ts, last_date_ts) = row

        if chat_id not in result:
            result[chat_id] = {}

        result[chat_id][user_id] = {
            "messages":    messages,
            "stickers":    stickers,
            "gifs":        gifs,
            "video_notes": video_notes,
            "voices":      voices,
            "first_date":  datetime.fromtimestamp(first_date_ts, tz=timezone.utc) if first_date_ts else None,
            "last_date":   datetime.fromtimestamp(last_date_ts,  tz=timezone.utc) if last_date_ts  else None,
            "username":    username or "",
            "name":        name     or "",
        }
    return result


def save_user_stats(chat_id: int, user_id: int, s: dict):
    first_ts = s["first_date"].timestamp() if s["first_date"] else None
    last_ts  = s["last_date"].timestamp()  if s["last_date"]  else None

    conn = _connect()
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
    conn.close()
