"""The hard lines, enforced in code.

Sagu roasts the *thing someone said*, never the person. These topics are never quoted, never joked about and never
appear in anything Sagu sends (deal titles excepted, which only need to be free of slurs): body, weight, looks,
eating, race, religion, gender, sexuality, disability, mental health, family, money, sex, violence and slurs.
The lists are deliberately broad. Over-blocking only means fewer quotes; under-blocking would hurt someone.
"""
from __future__ import annotations

import re
from typing import Optional

_TOPICS = {
    "body": r"fat|fatty|skinny|obese|chubby|thicc|ugly|hideous|bald|weigh\w*|weight|pounds|lbs|calori\w*|diet\w*|bmi|"
    r"anorex\w*|bulim\w*|binge\w*|purg\w*|starv\w*|body|bodies|abs|muscle\w*|jacked|hot|sexy|cute|pretty|handsome",
    "identity": r"race|racist|black|white|asian|latino|latina|mexican|indian|chinese|arab|jewish|jew|muslim|christian|"
    r"hindu|atheist|islam\w*|bible|church|god|pray\w*|gay|lesbian|trans|queer|bisexual|straight|gender\w*|"
    r"he/him|she/her|they/them",
    "health": r"depress\w*|anxi\w*|suicid\w*|kill myself|self.?harm|therap\w*|panic|bipolar|adhd|ocd|autis\w*|trauma\w*|"
    r"mental\w*|disabled|disabilit\w*|wheelchair|deaf|blind|handicap\w*|cancer|sick|ill|died|dead|death|funeral",
    "family": r"mom|mum|mother|dad|father|parents?|sister|brother|grandma|grandpa|aunt|uncle|cousin|divorce\w*|"
    r"family|girlfriend|boyfriend|ex|wife|husband",
    "money": r"money|broke|poor|rich|rent|tuition|debt|loans?|paycheck|salary|poverty|cash|dollars?|bucks|afford\w*|"
    r"cheap|expensive|\$\d+",
    "sex_violence": r"sex\w*|nude\w*|porn\w*|horny|hook.?ups?|naked|kill\w*|murder\w*|stab\w*|shoot\w*|beat you|"
    r"hurt you|rape\w*|drunk|wasted|high|weed|drugs?",
}
_SLURS = (
    r"n[i1!]gg\w*|f[a@]gg?[o0]t\w*|retard\w*|tr[a@]nn(?:y|ies)|k[i1]ke\w*|ch[i1]nks?|sp[i1]cs?|d[y]kes?|wetbacks?|"
    r"coons?|gooks?|towelheads?|c[u*]nts?|wh[o0]res?|sluts?"
)

_TOPIC_RE = re.compile(r"(?<![\w$])(?:" + "|".join("(?:%s)" % p for p in _TOPICS.values()) + r")(?![\w])", re.I)
_SLUR_RE = re.compile(r"(?<!\w)(?:%s)(?!\w)" % _SLURS, re.I)
_URL_RE = re.compile(r"https?://|www\.|\b\w+\.(?:com|net|org|io|edu)\b", re.I)
_PHONE_RE = re.compile(r"\d[\d\-\s().]{6,}\d")
_EMAIL_RE = re.compile(r"\S+@\S+")
_TAPBACK_RE = re.compile(r"^(?:liked|loved|laughed at|emphasized|disliked|questioned)\s+[\"“]", re.I)

MAX_LINE = 280


def has_slur(text: str) -> bool:
    return bool(_SLUR_RE.search(text))


def touches_hard_line(text: str) -> bool:
    return bool(_TOPIC_RE.search(text)) or has_slur(text)


def quotable(text: str) -> bool:
    """Whether a message from a friend may be stored and quoted back at them."""
    t = text.strip()
    if not 12 <= len(t) <= 140:
        return False
    if sum(c.isalpha() for c in t) < 8:
        return False
    if _URL_RE.search(t) or _PHONE_RE.search(t) or _EMAIL_RE.search(t) or _TAPBACK_RE.match(t):
        return False
    if t.lower().startswith("sagu") or t.startswith("\U0001F335"):
        return False
    return not touches_hard_line(t)


def clean_line(text: Optional[str]) -> Optional[str]:
    """The last gate before anything is sent. Returns the line, or None if it must not be posted."""
    if not text:
        return None
    t = " ".join(text.split())
    if not t or len(t) > MAX_LINE:
        return None
    if has_slur(t) or "@" in t:
        return None
    return t


def clean_roast(text: Optional[str]) -> Optional[str]:
    """clean_line plus the topic filter, for anything that jokes about what a person said."""
    t = clean_line(text)
    if t is None or touches_hard_line(_strip_quotes(t)):
        return None
    return t


def _strip_quotes(t: str) -> str:
    # quoted words were already checked when stored; here only Sagu's own wording must pass the topic filter
    return re.sub(r"[\"“][^\"”]*[\"”]", " ", t)
