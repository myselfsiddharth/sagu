"""The two doors into Messages: reading `chat.db` (read-only) and sending with AppleScript.

Sagu has no Apple ID of its own. It uses whichever account is signed in to Messages on this Mac, so every person
who runs it plugs in their own. Lines go out from that account, which is why each one starts with a cactus.
"""
from __future__ import annotations

import os
import sqlite3
import subprocess
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

from .decode import message_text

APPLE_EPOCH = 978307200  # Messages counts from 2001-01-01
ME = "__me__"  # the handle of the person running Sagu
DEFAULT_DB = os.path.expanduser("~/Library/Messages/chat.db")
GROUP_STYLE = 43


@dataclass(frozen=True)
class Message:
    rowid: int
    chat: str  # chat guid, e.g. "iMessage;+;chat123"
    handle: str  # phone or email of the sender, or ME
    text: str
    ts: float  # unix seconds
    is_from_me: bool


def apple_to_unix(value: int) -> float:
    seconds = value / 1e9 if abs(value) > 1e12 else float(value)
    return seconds + APPLE_EPOCH


def unix_to_apple(ts: float) -> int:
    return int((ts - APPLE_EPOCH) * 1e9)


_SELECT = """
SELECT m.ROWID, c.guid, h.id, m.text, m.attributedBody, m.date, m.is_from_me
FROM message m
JOIN chat_message_join j ON j.message_id = m.ROWID
JOIN chat c ON c.ROWID = j.chat_id
LEFT JOIN handle h ON h.ROWID = m.handle_id
WHERE c.style = ? AND m.item_type = 0 AND m.associated_message_type = 0
"""


class Reader:
    def __init__(self, path: str = DEFAULT_DB):
        self.path = path
        self._db = sqlite3.connect("file:%s?mode=ro" % path, uri=True, timeout=5)

    def close(self) -> None:
        self._db.close()

    def max_rowid(self) -> int:
        row = self._db.execute("SELECT COALESCE(MAX(ROWID), 0) FROM message").fetchone()
        return int(row[0])

    def groups(self) -> List[Tuple[str, str, int]]:
        """(guid, display name, member count) for each group chat."""
        rows = self._db.execute(
            """SELECT c.guid, COALESCE(NULLIF(c.display_name, ''), c.chat_identifier),
                      (SELECT COUNT(*) FROM chat_handle_join x WHERE x.chat_id = c.ROWID)
               FROM chat c WHERE c.style = ? ORDER BY c.ROWID DESC""",
            (GROUP_STYLE,),
        ).fetchall()
        return [(r[0], r[1], int(r[2])) for r in rows]

    def _rows(self, query: str, args: Sequence) -> List[Message]:
        out: List[Message] = []
        for rowid, chat, handle, text, blob, date, mine in self._db.execute(query, args):
            body = message_text(text, blob)
            if body is None:
                continue
            out.append(Message(int(rowid), chat, ME if mine else (handle or "unknown"), body, apple_to_unix(date or 0), bool(mine)))
        return out

    def new_messages(self, after_rowid: int) -> List[Message]:
        return self._rows(_SELECT + " AND m.ROWID > ? ORDER BY m.ROWID", (GROUP_STYLE, after_rowid))

    def history(self, chat: str, handle: str, since_ts: float, limit: int = 4000) -> List[Message]:
        """One person's past messages in one group, for the moment they opt in to being quoted."""
        who = "m.is_from_me = 1" if handle == ME else "m.is_from_me = 0 AND h.id = ?"
        args: List = [GROUP_STYLE, chat, unix_to_apple(since_ts)]
        if handle != ME:
            args.append(handle)
        args.append(limit)
        return self._rows(
            _SELECT + " AND c.guid = ? AND m.date >= ? AND " + who + " ORDER BY m.ROWID DESC LIMIT ?", args
        )


class SendError(RuntimeError):
    pass


_SCRIPT = """on run argv
  tell application "Messages" to send (item 2 of argv) to chat id (item 1 of argv)
end run"""


class OsaSender:
    """Sends into an existing group chat by its guid."""

    def send(self, chat: str, text: str) -> None:
        proc = subprocess.run(
            ["osascript", "-e", _SCRIPT, chat, text], capture_output=True, text=True, timeout=30
        )
        if proc.returncode != 0:
            raise SendError((proc.stderr or proc.stdout).strip() or "osascript failed")


class DrySender:
    """Records lines instead of sending them (`--dry-run`, the demo, and the tests)."""

    def __init__(self) -> None:
        self.sent: List[Tuple[str, str]] = []

    def send(self, chat: str, text: str) -> None:
        self.sent.append((chat, text))


def names_by_chat(groups: Sequence[Tuple[str, str, int]]) -> Dict[str, str]:
    return {g[0]: g[1] for g in groups}


def automation_status() -> Tuple[bool, str]:
    """Can this terminal drive Messages? The first call makes macOS ask for permission."""
    try:
        proc = subprocess.run(
            ["osascript", "-e", 'tell application "Messages" to get name'], capture_output=True, text=True, timeout=30
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, str(exc)
    if proc.returncode == 0:
        return True, "ok"
    return False, (proc.stderr or proc.stdout).strip()
