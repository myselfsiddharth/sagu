"""Sagu's memory: one small SQLite file under SAGU_HOME (default ~/.config/sagu). Nothing is stored for a group
until its owner says "sagu on", and a person's quotes only exist after that person says "sagu roast me"."""
from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass
from typing import List, Optional

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS groups (guid TEXT PRIMARY KEY, active INTEGER NOT NULL DEFAULT 0, last_msg_ts REAL NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS members (guid TEXT, handle TEXT, name TEXT, opted_in INTEGER NOT NULL DEFAULT 0, PRIMARY KEY (guid, handle));
CREATE TABLE IF NOT EXISTS quotes (guid TEXT, handle TEXT, rowid_src INTEGER, text TEXT, ts REAL, score REAL, excuse INTEGER,
  used_ts REAL NOT NULL DEFAULT 0, PRIMARY KEY (guid, rowid_src));
CREATE TABLE IF NOT EXISTS activity (guid TEXT, handle TEXT, ts REAL);
CREATE TABLE IF NOT EXISTS posts (guid TEXT, ts REAL, kind TEXT);
CREATE TABLE IF NOT EXISTS deals (id INTEGER PRIMARY KEY AUTOINCREMENT, guid TEXT, title TEXT, link TEXT, ends_ts REAL,
  source TEXT, key TEXT, created_ts REAL, announced_ts REAL, plan_ts REAL, remind_ts REAL, reminded INTEGER NOT NULL DEFAULT 0,
  UNIQUE (guid, key));
CREATE TABLE IF NOT EXISTS rsvps (deal_id INTEGER, handle TEXT, answer TEXT, PRIMARY KEY (deal_id, handle));
"""


@dataclass
class Quote:
    guid: str
    handle: str
    src: int
    text: str
    ts: float
    score: float
    excuse: bool
    used_ts: float


@dataclass
class Deal:
    id: int
    guid: str
    title: str
    link: Optional[str]
    ends_ts: Optional[float]
    source: str
    created_ts: float
    announced_ts: Optional[float]
    plan_ts: Optional[float]
    remind_ts: Optional[float]
    reminded: bool


def default_home() -> str:
    return os.environ.get("SAGU_HOME") or os.path.expanduser("~/.config/sagu")


class Store:
    def __init__(self, path: str):
        if path != ":memory:":
            os.makedirs(os.path.dirname(path), exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.executescript(SCHEMA)
        if path != ":memory:":
            os.chmod(path, 0o600)

    def close(self) -> None:
        self.db.close()

    # cursor
    def cursor(self) -> Optional[int]:
        row = self.db.execute("SELECT value FROM meta WHERE key='cursor'").fetchone()
        return int(row[0]) if row else None

    def set_cursor(self, rowid: int) -> None:
        self.db.execute("INSERT OR REPLACE INTO meta VALUES ('cursor', ?)", (str(rowid),))
        self.db.commit()

    # groups
    def is_active(self, guid: str) -> bool:
        row = self.db.execute("SELECT active FROM groups WHERE guid=?", (guid,)).fetchone()
        return bool(row and row[0])

    def set_active(self, guid: str, active: bool) -> None:
        self.db.execute(
            "INSERT INTO groups (guid, active) VALUES (?, ?) ON CONFLICT(guid) DO UPDATE SET active=excluded.active",
            (guid, int(active)),
        )
        self.db.commit()

    def active_groups(self) -> List[str]:
        return [r[0] for r in self.db.execute("SELECT guid FROM groups WHERE active=1")]

    def touch(self, guid: str, ts: float) -> None:
        self.db.execute("UPDATE groups SET last_msg_ts=? WHERE guid=?", (ts, guid))
        self.db.commit()

    def last_msg_ts(self, guid: str) -> float:
        row = self.db.execute("SELECT last_msg_ts FROM groups WHERE guid=?", (guid,)).fetchone()
        return float(row[0]) if row else 0.0

    # members
    def member(self, guid: str, handle: str):
        return self.db.execute("SELECT name, opted_in FROM members WHERE guid=? AND handle=?", (guid, handle)).fetchone()

    def name_of(self, guid: str, handle: str) -> Optional[str]:
        row = self.member(guid, handle)
        return row[0] if row and row[0] else None

    def is_opted_in(self, guid: str, handle: str) -> bool:
        row = self.member(guid, handle)
        return bool(row and row[1])

    def set_name(self, guid: str, handle: str, name: str) -> None:
        self.db.execute(
            "INSERT INTO members (guid, handle, name) VALUES (?,?,?) ON CONFLICT(guid, handle) DO UPDATE SET name=excluded.name",
            (guid, handle, name),
        )
        self.db.commit()

    def set_opt_in(self, guid: str, handle: str, opted_in: bool) -> None:
        self.db.execute(
            "INSERT INTO members (guid, handle, opted_in) VALUES (?,?,?) ON CONFLICT(guid, handle) DO UPDATE SET opted_in=excluded.opted_in",
            (guid, handle, int(opted_in)),
        )
        self.db.commit()

    def drop_quotes(self, guid: str, handle: str) -> None:
        self.db.execute("DELETE FROM quotes WHERE guid=? AND handle=?", (guid, handle))
        self.db.commit()

    def forget_member(self, guid: str, handle: str) -> None:
        for table in ("members", "quotes", "activity"):
            self.db.execute("DELETE FROM %s WHERE guid=? AND handle=?" % table, (guid, handle))
        self.db.execute("DELETE FROM rsvps WHERE handle=? AND deal_id IN (SELECT id FROM deals WHERE guid=?)", (handle, guid))
        self.db.commit()

    def forget_group(self, guid: str) -> None:
        for table in ("members", "quotes", "activity", "posts"):
            self.db.execute("DELETE FROM %s WHERE guid=?" % table, (guid,))
        self.db.execute("DELETE FROM rsvps WHERE deal_id IN (SELECT id FROM deals WHERE guid=?)", (guid,))
        self.db.execute("DELETE FROM deals WHERE guid=?", (guid,))
        self.db.commit()

    # quotes
    def add_quote(self, guid: str, handle: str, src: int, text: str, ts: float, score: float, excuse: bool) -> None:
        self.db.execute(
            "INSERT OR IGNORE INTO quotes (guid, handle, rowid_src, text, ts, score, excuse) VALUES (?,?,?,?,?,?,?)",
            (guid, handle, src, text, ts, score, int(excuse)),
        )
        self.db.commit()

    def trim_quotes(self, guid: str, handle: str, keep: int = 40) -> None:
        self.db.execute(
            """DELETE FROM quotes WHERE guid=? AND handle=? AND rowid_src NOT IN
               (SELECT rowid_src FROM quotes WHERE guid=? AND handle=? ORDER BY score DESC, ts DESC LIMIT ?)""",
            (guid, handle, guid, handle, keep),
        )
        self.db.commit()

    def quotes(self, guid: str) -> List[Quote]:
        """Only quotes whose author is currently opted in."""
        rows = self.db.execute(
            """SELECT q.guid, q.handle, q.rowid_src, q.text, q.ts, q.score, q.excuse, q.used_ts FROM quotes q
               JOIN members m ON m.guid=q.guid AND m.handle=q.handle
               WHERE q.guid=? AND m.opted_in=1 AND m.name IS NOT NULL""",
            (guid,),
        ).fetchall()
        return [Quote(r[0], r[1], r[2], r[3], r[4], r[5], bool(r[6]), r[7]) for r in rows]

    def mark_used(self, guid: str, src: int, ts: float) -> None:
        self.db.execute("UPDATE quotes SET used_ts=? WHERE guid=? AND rowid_src=?", (ts, guid, src))
        self.db.commit()

    # activity
    def note_activity(self, guid: str, handle: str, ts: float) -> None:
        self.db.execute("INSERT INTO activity VALUES (?,?,?)", (guid, handle, ts))
        self.db.execute("DELETE FROM activity WHERE ts < ?", (ts - 3 * 86400,))
        self.db.commit()

    def busiest_since(self, guid: str, since: float):
        """(handle, count) of the most active named member since a time, or None."""
        row = self.db.execute(
            """SELECT a.handle, COUNT(*) c FROM activity a JOIN members m ON m.guid=a.guid AND m.handle=a.handle
               WHERE a.guid=? AND a.ts>=? AND m.name IS NOT NULL GROUP BY a.handle ORDER BY c DESC LIMIT 1""",
            (guid, since),
        ).fetchone()
        return (row[0], row[1]) if row else None

    # posts
    def add_post(self, guid: str, ts: float, kind: str) -> None:
        self.db.execute("INSERT INTO posts VALUES (?,?,?)", (guid, ts, kind))
        self.db.commit()

    def last_post_ts(self, guid: str) -> float:
        row = self.db.execute("SELECT MAX(ts) FROM posts WHERE guid=?", (guid,)).fetchone()
        return float(row[0]) if row and row[0] else 0.0

    def posts_since(self, guid: str, since: float) -> int:
        return int(self.db.execute("SELECT COUNT(*) FROM posts WHERE guid=? AND ts>=?", (guid, since)).fetchone()[0])

    # deals
    _DEAL = "id, guid, title, link, ends_ts, source, created_ts, announced_ts, plan_ts, remind_ts, reminded"

    def _deal(self, r) -> Deal:
        return Deal(r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[7], r[8], r[9], bool(r[10]))

    def add_deal(self, guid: str, title: str, link: Optional[str], ends_ts: Optional[float], source: str, key: str, now: float) -> Optional[int]:
        cur = self.db.execute(
            "INSERT OR IGNORE INTO deals (guid, title, link, ends_ts, source, key, created_ts) VALUES (?,?,?,?,?,?,?)",
            (guid, title, link, ends_ts, source, key, now),
        )
        self.db.commit()
        return cur.lastrowid if cur.rowcount else None

    def open_deals(self, guid: str, now: float) -> List[Deal]:
        rows = self.db.execute(
            "SELECT %s FROM deals WHERE guid=? AND (ends_ts IS NULL OR ends_ts>=?) AND created_ts>=? ORDER BY created_ts DESC"
            % self._DEAL,
            (guid, now, now - 3 * 86400),
        ).fetchall()
        return [self._deal(r) for r in rows]

    def mark_announced(self, deal_id: int, ts: float) -> None:
        self.db.execute("UPDATE deals SET announced_ts=? WHERE id=?", (ts, deal_id))
        self.db.commit()

    def set_plan(self, deal_id: int, plan_ts: float, remind_ts: float) -> None:
        self.db.execute("UPDATE deals SET plan_ts=?, remind_ts=?, reminded=0 WHERE id=?", (plan_ts, remind_ts, deal_id))
        self.db.commit()

    def due_reminders(self, now: float) -> List[Deal]:
        rows = self.db.execute(
            "SELECT %s FROM deals WHERE remind_ts IS NOT NULL AND reminded=0 AND remind_ts<=?" % self._DEAL, (now,)
        ).fetchall()
        return [self._deal(r) for r in rows]

    def mark_reminded(self, deal_id: int) -> None:
        self.db.execute("UPDATE deals SET reminded=1 WHERE id=?", (deal_id,))
        self.db.commit()

    def set_rsvp(self, deal_id: int, handle: str, answer: str) -> None:
        self.db.execute("INSERT OR REPLACE INTO rsvps VALUES (?,?,?)", (deal_id, handle, answer))
        self.db.commit()

    def who_is_in(self, deal_id: int) -> List[str]:
        return [r[0] for r in self.db.execute("SELECT handle FROM rsvps WHERE deal_id=? AND answer='in' ORDER BY rowid", (deal_id,))]
