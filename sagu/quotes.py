"""Which old messages are worth bringing back. A cheap, readable heuristic; no model needed."""
from __future__ import annotations

import re
from typing import Tuple

from .safety import quotable

_PROMISE = re.compile(
    r"\b(i('| a)?ll|im gonna|i'm gonna|going to|gonna|will)\s+(start|do|go|study|finish|clean|call|text|wake|run|cook|"
    r"quit|stop|fix|read|write|work|sleep|save)\b|\b(tomorrow|monday|next week|later|tonight|this weekend|after break)\b|"
    r"\b(never|always|swear|promise|definitely|for sure|trust me|last time|famous last)\b",
    re.I,
)
_LAUGH = re.compile(r"\b(lol|lmao|haha+|bruh|bro|literally|actually|honestly|unhinged|chaos)\b|[\U0001F602\U0001F480\U0001F62D\U0001F923]", re.I)
_SHOUT = re.compile(r"\b[A-Z]{4,}\b")


def funniness(text: str) -> Tuple[float, bool]:
    """(score, is_a_promise_or_excuse). Scores of 2 and up are kept as quotes."""
    if not quotable(text):
        return 0.0, False
    score = 0.0
    promise = bool(_PROMISE.search(text))
    if promise:
        score += 2
    if _LAUGH.search(text):
        score += 1
    if _SHOUT.search(text):
        score += 1
    if "!" in text:
        score += 0.5
    if 25 <= len(text) <= 100:
        score += 1
    return score, promise
