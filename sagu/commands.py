"""What people can text to Sagu. Everything starts with the word "sagu", except a bare "in" or "out" answering a deal."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from .games import GAME_WORDS

_PREFIX = re.compile(r"^\s*sagu\b[\s,:!.-]*(.*)$", re.I | re.S)
_NAME = re.compile(r"^(?:i'?m|im|i am|call me|my name is|name)\s+([A-Za-z][A-Za-z' -]{0,18})\s*$", re.I)
_IN = re.compile(r"^\s*(?:i'?m in|im in|in|count me in|i'?m down|im down|down)\s*[!.]*\s*$", re.I)
_OUT = re.compile(r"^\s*(?:i'?m out|im out|out|can'?t|cant|pass)\s*[!.]*\s*$", re.I)


@dataclass(frozen=True)
class Command:
    name: str
    arg: str = ""


def parse(text: str) -> Optional[Command]:
    """A command, or None for ordinary chatter."""
    m = _PREFIX.match(text)
    if not m:
        return None
    rest = m.group(1).strip()
    low = rest.lower().rstrip("!. ")
    if low in ("on", "start", "join", "hi", "hello"):
        return Command("on")
    if low in ("off", "stop", "leave", "bye"):
        return Command("off")
    if low in ("help", "?", "commands"):
        return Command("help")
    if low in ("roast me", "quote me", "i'm fair game", "im fair game"):
        return Command("roast_me")
    if low in ("spare me", "stop roasting me", "no roasts", "leave me alone"):
        return Command("spare_me")
    if low in ("forget me", "delete me", "delete my stuff"):
        return Command("forget_me")
    if low in ("forget this chat", "forget everything", "wipe"):
        return Command("forget_chat")
    if low in ("deals", "food", "deal list"):
        return Command("deals")
    if low in ("in", "i'm in", "im in", "count me in"):
        return Command("in")
    if low in ("out", "i'm out", "im out"):
        return Command("out")
    name = _NAME.match(rest)
    if name:
        return Command("name", name.group(1).strip().title())
    deal = re.match(r"^deal\s*[:\-]?\s*(.+)$", rest, re.I | re.S)
    if deal:
        return Command("deal", deal.group(1).strip())
    if low.split(" ")[0].rstrip("?!.,:") in GAME_WORDS or re.fullmatch(r"\d{1,3}", low):
        return Command("game", rest)
    return Command("unknown", rest)


def parse_rsvp(text: str) -> Optional[str]:
    """'in' or 'out' for a bare reply to a deal, else None."""
    if _IN.match(text):
        return "in"
    if _OUT.match(text):
        return "out"
    return None
