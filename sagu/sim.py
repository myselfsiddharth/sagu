"""A made-up Messages database and a scripted group chat, for the demo and the tests.

Everything here is fiction: invented friends, invented messages, an in-memory database shaped like the part of
Apple's chat.db that Sagu reads. The demo prints "SIMULATION" because that is what it is.
"""
from __future__ import annotations

import os
import sqlite3
import tempfile
from datetime import datetime, timedelta
from typing import List, Optional, Tuple

from .decode import encode_for_tests
from .imessage import ME, unix_to_apple

SCHEMA = """
CREATE TABLE handle (ROWID INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT UNIQUE);
CREATE TABLE chat (ROWID INTEGER PRIMARY KEY AUTOINCREMENT, guid TEXT UNIQUE, style INTEGER, chat_identifier TEXT, display_name TEXT);
CREATE TABLE chat_handle_join (chat_id INTEGER, handle_id INTEGER);
CREATE TABLE message (ROWID INTEGER PRIMARY KEY AUTOINCREMENT, guid TEXT UNIQUE, text TEXT, attributedBody BLOB, handle_id INTEGER DEFAULT 0,
  date INTEGER, is_from_me INTEGER DEFAULT 0, item_type INTEGER DEFAULT 0, associated_message_type INTEGER DEFAULT 0);
CREATE TABLE chat_message_join (chat_id INTEGER, message_id INTEGER);
"""


class FakeMessages:
    """A throwaway chat.db. `say` appends a message; `use_blob=True` stores it the way recent macOS does."""

    def __init__(self, path: Optional[str] = None):
        self.path = path or os.path.join(tempfile.mkdtemp(prefix="sagu-sim-"), "chat.db")
        self.db = sqlite3.connect(self.path)
        self.db.executescript(SCHEMA)
        self._n = 0

    def group(self, guid: str, name: str, members: List[str]) -> None:
        cur = self.db.execute("INSERT INTO chat (guid, style, chat_identifier, display_name) VALUES (?,43,?,?)", (guid, guid, name))
        for h in members:
            hid = self._handle(h)
            self.db.execute("INSERT INTO chat_handle_join VALUES (?,?)", (cur.lastrowid, hid))
        self.db.commit()

    def _handle(self, h: str) -> int:
        self.db.execute("INSERT OR IGNORE INTO handle (id) VALUES (?)", (h,))
        return self.db.execute("SELECT ROWID FROM handle WHERE id=?", (h,)).fetchone()[0]

    def say(self, guid: str, handle: str, text: str, ts: float, use_blob: bool = False, kind: int = 0, item: int = 0) -> int:
        self._n += 1
        chat_id = self.db.execute("SELECT ROWID FROM chat WHERE guid=?", (guid,)).fetchone()[0]
        mine = handle == ME
        cur = self.db.execute(
            "INSERT INTO message (guid, text, attributedBody, handle_id, date, is_from_me, item_type, associated_message_type) VALUES (?,?,?,?,?,?,?,?)",
            ("m%d" % self._n, None if use_blob else text, encode_for_tests(text) if use_blob else None,
             0 if mine else self._handle(handle), unix_to_apple(ts), int(mine), item, kind),
        )
        self.db.execute("INSERT INTO chat_message_join VALUES (?,?)", (chat_id, cur.lastrowid))
        self.db.commit()
        return int(cur.lastrowid)


GUID = "iMessage;+;chat-sim-4b"
ANA, BEN, CY = "+15550100001", "+15550100002", "ben-and-cy@example.com"
HANDLES = {"ana": ANA, "ben": BEN, "cy": CY}


def build_history(fake: FakeMessages, now: float) -> None:
    """Three weeks of a fictional dorm chat, so there is something to remember."""
    fake.group(GUID, "Dorm 4B (simulation)", [ANA, BEN, CY])
    day = 86400.0
    past = [
        (21, ANA, "I'll start the 6am gym thing on Monday, for real this time"),
        (19, BEN, "bro I literally cannot function without iced coffee"),
        (17, CY, "I swear I'm going to finish the lab report tomorrow"),
        (15, ME, "does anyone else's roommate microwave fish at midnight"),
        (12, ANA, "never again will I schedule an 8am, trust me"),
        (9, BEN, "I am convinced the dining hall chicken is a social experiment"),
        (6, CY, "okay LISTEN I am going to sleep before midnight tonight"),
        (4, ANA, "ok"),
        (3, BEN, "http://example.com/some-link"),
    ]
    for days_ago, who, text in past:
        fake.say(GUID, who, text, now - days_ago * day + 3600, use_blob=(len(text) % 2 == 0))


def at(hour: int, minute: int = 0, days_ahead: int = 0) -> float:
    base = datetime.now().replace(hour=hour, minute=minute, second=0, microsecond=0)
    return (base + timedelta(days=days_ahead)).timestamp()


def script(now: float) -> List[Tuple[str, float, str, str]]:
    """(who, time, text, what it shows)"""
    t = now
    return [
        (ME, t, "sagu on", "the host adds Sagu"),
        (ANA, t + 60, "sagu i'm Ana", "people tell Sagu their name"),
        (ANA, t + 90, "sagu roast me", "Ana opts in; Sagu looks back through her old messages"),
        (BEN, t + 120, "sagu i'm Ben", "Ben gives a name but does NOT opt in, so Sagu will never quote him"),
        (CY, t + 150, "sagu deal: 2-for-1 tacos at Taco Loco till Friday", "a friend shares a deal"),
        (ANA, t + 200, "in", "Ana is in"),
        (BEN, t + 240, "im in", "Ben is in, so Sagu proposes a time"),
        (ANA, t + 2000, "lol did anyone do the reading", "ordinary chatter, Sagu may jump in"),
        (BEN, t + 2100, "nope", "ordinary chatter"),
        (ANA, t + 9000, "this chat is unhinged today", "ordinary chatter"),
    ]
