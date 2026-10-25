"""Food deals: ones a friend types in ("sagu deal: ..."), plus optional RSS/Atom feeds the owner lists in config.

Sagu never invents a deal. With no feeds and nobody adding any, it simply has no deals to announce.
"""
from __future__ import annotations

import hashlib
import re
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Callable, List, Optional

from .safety import has_slur

FOODISH = re.compile(
    r"\b(bogo|free|2.for.1|two.for|half.off|\d+%\s*off|\$\d|deal|combo|meal|pizza|burger|taco|burrito|wings|fries|"
    r"boba|coffee|latte|bagel|sandwich|sub|ramen|sushi|wing|nugget|chicken|dessert|donut|ice cream|happy hour|"
    r"special|discount|coupon|promo)\b",
    re.I,
)
_WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
_ENDS = re.compile(
    r"\b(?:till|til|until|thru|through|ends?|expires?|by|before)\s+"
    r"(today|tonight|tomorrow|mon(?:day)?|tue(?:s(?:day)?)?|wed(?:nesday)?|thu(?:rs(?:day)?)?|fri(?:day)?|sat(?:urday)?|sun(?:day)?)\b",
    re.I,
)
_LINK = re.compile(r"https?://\S+")
MAX_FEED_BYTES = 500_000


@dataclass(frozen=True)
class Found:
    title: str
    link: Optional[str]
    ends_ts: Optional[float]
    key: str


def parse_deadline(text: str, now: float) -> Optional[float]:
    """End of the day named in 'till Friday' / 'ends tomorrow', local time. None when no day is named."""
    m = _ENDS.search(text)
    if not m:
        return None
    word = m.group(1).lower()[:3]
    today = datetime.fromtimestamp(now).replace(hour=23, minute=59, second=0, microsecond=0)
    if word in ("tod", "ton"):
        day = today
    elif word == "tom":
        day = today + timedelta(days=1)
    else:
        ahead = (_WEEKDAYS.index(word) - today.weekday()) % 7
        day = today + timedelta(days=ahead)
    return day.timestamp()


def from_text(text: str, now: float) -> Optional[Found]:
    """A deal typed into the chat. The link, if any, is kept; the rest becomes the title."""
    link = _LINK.search(text)
    title = " ".join(_LINK.sub("", text).split())[:140]
    if len(title) < 6 or has_slur(title) or "@" in title:
        return None
    key = hashlib.sha1(title.lower().encode()).hexdigest()[:16]
    return Found(title, link.group(0) if link else None, parse_deadline(title, now), key)


def parse_feed(xml_bytes: bytes, now: float) -> List[Found]:
    """Titles and links from an RSS or Atom document. Untrusted input: size-capped, no entity tricks, food-only."""
    if len(xml_bytes) > MAX_FEED_BYTES or b"<!ENTITY" in xml_bytes or b"<!DOCTYPE" in xml_bytes[:200].upper():
        return []
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return []
    found: List[Found] = []
    for item in root.iter():
        tag = item.tag.split("}")[-1]
        if tag not in ("item", "entry"):
            continue
        title = link = None
        for child in item:
            ctag = child.tag.split("}")[-1]
            if ctag == "title" and child.text:
                title = " ".join(child.text.split())[:140]
            elif ctag == "link":
                link = (child.text or child.attrib.get("href") or "").strip() or None
        if not title or not FOODISH.search(title) or has_slur(title) or "@" in title:
            continue
        if link and not link.startswith("https://"):
            link = None
        found.append(Found(title, link, parse_deadline(title, now), hashlib.sha1((link or title).lower().encode()).hexdigest()[:16]))
    return found[:20]


def fetch(url: str) -> bytes:
    if not url.startswith("https://"):
        return b""
    req = urllib.request.Request(url, headers={"User-Agent": "sagu/0.1 (+local group chat bot)"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return resp.read(MAX_FEED_BYTES + 1)


def poll_feeds(urls: List[str], now: float, fetcher: Callable[[str], bytes] = fetch) -> List[Found]:
    out: List[Found] = []
    for url in urls:
        try:
            out.extend(parse_feed(fetcher(url), now))
        except Exception:  # one broken feed must never stop the bot
            continue
    return out


def names_deadline(title: str) -> bool:
    return bool(_ENDS.search(title))


def pick_slot(now: float, ends_ts: Optional[float]) -> float:
    """A suggested time to go: 6:30 pm tomorrow, or the last evening before the deal ends if that comes first."""
    start = datetime.fromtimestamp(now)
    day = (start + timedelta(days=1)).replace(hour=18, minute=30, second=0, microsecond=0)
    if start.hour < 15:
        day = start.replace(hour=18, minute=30, second=0, microsecond=0)
    if ends_ts is not None:
        last = datetime.fromtimestamp(ends_ts).replace(hour=18, minute=30, second=0, microsecond=0)
        if last < day:
            return last.timestamp() if last.timestamp() > now else now + 3600  # ends tonight: go in an hour
    return day.timestamp()
