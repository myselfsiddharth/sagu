"""The brain: reads new group messages, answers commands, and decides when to jump in on its own."""
from __future__ import annotations

import json
import os
import random
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, List, Optional

from . import PREFIX
from .commands import Command, parse, parse_rsvp
from .games import Games
from .deals import from_text, names_deadline, pick_slot, poll_feeds
from .imessage import ME, Message, SendError
from .quotes import funniness
from .store import Deal, Quote, Store
from .voice import Llm, ago, compose, plain

DAY = 86400.0
HELP = (
    "I'm Sagu, a cactus in this chat. I share food deals and sometimes quote or cheer people on.\n"
    "sagu roast me - I may quote your old messages (only in this chat)\n"
    "sagu spare me - no more quotes of you\n"
    "sagu i'm Alex - tell me your name\n"
    "sagu deal: <deal, e.g. 2-for-1 tacos till Friday> - share a deal\n"
    "in / out - answer a deal\n"
    "sagu deals - open deals\n"
    "sagu forget me - delete everything I saved about you\n"
    "sagu games - things to play\n"
    "Whoever runs me can say: sagu off"
)


@dataclass
class Config:
    owner_name: Optional[str] = None
    feeds: List[str] = field(default_factory=list)
    llm: bool = False
    quiet_start: int = 23  # no unprompted lines from 23:00 ...
    quiet_end: int = 9  # ... until 09:00 local time
    prob: float = 0.25  # chance that a live message in an active chat triggers a jump-in
    min_gap: float = 90 * 60
    max_per_day: int = 4
    activity_window: float = 30 * 60  # only jump into a chat that is talking right now
    min_quote_age: float = 2 * DAY
    reuse_gap: float = 14 * DAY
    backfill_days: int = 90
    feed_every: float = 30 * 60

    @staticmethod
    def load(home: str) -> "Config":
        path = os.path.join(home, "config.json")
        cfg = Config()
        try:
            with open(path) as fh:
                raw = json.load(fh)
        except (OSError, ValueError):
            return cfg
        if not isinstance(raw, dict):
            return cfg
        for key, value in raw.items():
            if not hasattr(cfg, key):
                continue
            current = getattr(cfg, key)
            if current is None:
                ok = isinstance(value, str)
            elif isinstance(current, bool):
                ok = isinstance(value, bool)
            elif isinstance(current, (int, float)):
                ok = isinstance(value, (int, float)) and not isinstance(value, bool)
            else:
                ok = isinstance(value, type(current))
            if ok:
                setattr(cfg, key, value)
        return cfg


class Sagu:
    def __init__(self, store: Store, reader, sender, cfg: Config, clock: Callable[[], float] = time.time,
                 rng: Optional[random.Random] = None, llm: Optional[Llm] = None, log: Callable[[str], None] = lambda s: None):
        self.store, self.reader, self.sender, self.cfg = store, reader, sender, cfg
        self.clock, self.rng, self.llm, self.log = clock, rng or random.Random(), llm, log
        self._last_feed = 0.0
        self.games = Games(self.rng)

    # --- loop -------------------------------------------------------------------------------------------------
    def tick(self) -> int:
        """One pass: new messages, feed polling, reminders. Returns how many messages were read."""
        cursor = self.store.cursor()
        if cursor is None:  # first run: start from now, never from history
            self.store.set_cursor(self.reader.max_rowid())
            return 0
        msgs = self.reader.new_messages(cursor)
        for m in msgs:
            self.handle(m)
        if msgs:
            self.store.set_cursor(max(m.rowid for m in msgs))
        self.poll_feeds()
        self.send_reminders()
        return len(msgs)

    # --- sending ----------------------------------------------------------------------------------------------
    def say(self, guid: str, text: Optional[str]) -> bool:
        if not text:
            return False
        try:
            self.sender.send(guid, text)
        except (SendError, OSError) as exc:
            self.log("could not send: %s" % exc)
            return False
        self.log("sent: %s" % text.replace("\n", " / ")[:90])
        return True

    # --- handling a message -----------------------------------------------------------------------------------
    def handle(self, m: Message) -> None:
        if m.text.startswith(PREFIX):
            return  # our own lines (they come back through the database)
        cmd = parse(m.text)
        if not self.store.is_active(m.chat):
            if cmd and cmd.name == "on" and m.is_from_me:
                self.activate(m)
            return
        if cmd:
            self.command(m, cmd)
            return
        answer = parse_rsvp(m.text)
        if answer and self.answer_deal(m, answer):
            return
        self.hear(m)

    def hear(self, m: Message) -> None:
        self.store.touch(m.chat, m.ts)
        self.store.note_activity(m.chat, m.handle, m.ts)
        if self.store.is_opted_in(m.chat, m.handle):
            self.consider_quote(m)
        self.maybe_jump_in(m.chat)

    def consider_quote(self, m: Message) -> None:
        score, excuse = funniness(m.text)
        if score >= 2:
            self.store.add_quote(m.chat, m.handle, m.rowid, m.text, m.ts, score, excuse)
            self.store.trim_quotes(m.chat, m.handle)

    def backfill(self, guid: str, handle: str) -> None:
        """When someone opts in, look back through their own messages in this one chat (on this Mac)."""
        since = self.clock() - self.cfg.backfill_days * DAY
        for old in self.reader.history(guid, handle, since):
            self.consider_quote(old)

    def name(self, guid: str, handle: str) -> str:
        return self.store.name_of(guid, handle) or "a mystery guest"

    # --- commands ---------------------------------------------------------------------------------------------
    def activate(self, m: Message) -> None:
        self.store.set_active(m.chat, True)
        self.store.touch(m.chat, m.ts)
        if self.cfg.owner_name:
            self.store.set_name(m.chat, ME, self.cfg.owner_name)
        self.store.set_opt_in(m.chat, ME, True)  # whoever runs Sagu is fair game by choice
        who = self.cfg.owner_name or "the host"
        privacy = (
            "Lines are written by an AI model, so a quote I use is sent to it."
            if self.llm
            else "Everything I remember stays on this Mac."
        )
        self.say(
            m.chat,
            plain(
                "Sagu here. I'm a small cactus running on %s's Mac. I watch this chat for good moments, share food deals, "
                "and sometimes cheer or tease. I only quote people who say \"sagu roast me\". Tell me your name with "
                "\"sagu i'm Alex\". \"sagu help\" for the rest. %s" % (who, privacy)
            ),
        )

    def command(self, m: Message, cmd: Command) -> None:
        g, h = m.chat, m.handle
        if cmd.name == "help":
            self.say(g, plain(HELP))
        elif cmd.name == "on":
            self.say(g, plain("Already here. \"sagu help\" if you need me."))
        elif cmd.name in ("off", "forget_chat"):
            if not m.is_from_me:
                self.say(g, plain("Only the person whose Mac I live on can do that."))
                return
            if cmd.name == "forget_chat":
                self.store.forget_group(g)
            self.store.set_active(g, False)
            self.say(g, plain("Leaving quietly. %s" % ("Everything I knew about this chat is deleted." if cmd.name == "forget_chat" else "Say \"sagu on\" to bring me back.")))
        elif cmd.name == "roast_me":
            self.store.set_opt_in(g, h, True)
            self.backfill(g, h)
            tail = "" if self.store.name_of(g, h) else " Tell me your name first: \"sagu i'm Alex\"."
            self.say(g, plain("Noted. I may quote what you say in here from time to time. \"sagu spare me\" ends it.%s" % tail))
        elif cmd.name == "spare_me":
            self.store.set_opt_in(g, h, False)
            self.store.drop_quotes(g, h)
            self.say(g, plain("Understood. No quotes of you, and I deleted the ones I had."))
        elif cmd.name == "forget_me":
            self.store.forget_member(g, h)
            self.say(g, plain("Done. I deleted everything I had saved about you."))
        elif cmd.name == "name":
            self.store.set_name(g, h, cmd.arg)
            if self.store.is_opted_in(g, h):
                self.backfill(g, h)
            self.say(g, plain("Nice to meet you, %s." % cmd.arg))
        elif cmd.name == "deals":
            self.list_deals(g)
        elif cmd.name == "deal":
            self.add_deal(m, cmd.arg)
        elif cmd.name in ("in", "out"):
            if not self.answer_deal(m, cmd.name):
                self.say(g, plain("No open deal right now. Share one with \"sagu deal: ...\"."))
        elif cmd.name == "game":
            reply = self.games.play(g, self.store.name_of(g, h) or "A friend", cmd.arg)
            if reply:
                self.say(g, plain(reply))
        elif cmd.name == "unknown" and len(cmd.arg.split()) <= 3:
            self.say(g, plain("Yes? \"sagu help\" lists what I do."))

    # --- deals ------------------------------------------------------------------------------------------------
    @staticmethod
    def _facts(deal_title: str, ends: Optional[float], link: Optional[str]) -> dict:
        when = ", ends %s" % datetime.fromtimestamp(ends).strftime("%A") if ends and not names_deadline(deal_title) else ""
        return {"title": deal_title, "ends": when, "link": (" " + link) if link else ""}

    def add_deal(self, m: Message, text: str) -> None:
        found = from_text(text, self.clock())
        if not found:
            self.say(m.chat, plain("I need a bit more than that. Try: sagu deal: 2-for-1 tacos till Friday"))
            return
        deal_id = self.store.add_deal(m.chat, found.title, found.link, found.ends_ts, "friend", found.key, self.clock())
        if deal_id is None:
            self.say(m.chat, plain("I already have that one."))
            return
        self.store.mark_announced(deal_id, self.clock())
        self.say(m.chat, compose("saved", self.rng, None, **self._facts(found.title, found.ends_ts, found.link)))

    def list_deals(self, guid: str) -> None:
        deals = self.store.open_deals(guid, self.clock())
        if not deals:
            self.say(guid, plain("No open deals. Share one with \"sagu deal: ...\"."))
            return
        lines = ["%d. %s%s" % (i + 1, d.title, " (ends %s)" % datetime.fromtimestamp(d.ends_ts).strftime("%A") if d.ends_ts else "") for i, d in enumerate(deals[:5])]
        self.say(guid, plain("Open deals:\n" + "\n".join(lines)))

    def answer_deal(self, m: Message, answer: str) -> bool:
        """A bare "in"/"out" counts for the latest announced deal. Returns False if there is none, so chatter flows on."""
        now = self.clock()
        deals = [d for d in self.store.open_deals(m.chat, now) if d.announced_ts is not None and now - d.announced_ts < 6 * 3600]
        if not deals:
            return False
        deal = deals[0]
        self.store.set_rsvp(deal.id, m.handle, answer)
        if answer != "in":
            return True
        ins = self.store.who_is_in(deal.id)
        names = [self.name(m.chat, x) for x in ins]
        if deal.plan_ts is not None:
            self.say(m.chat, plain("Added %s to %s. That's %d." % (self.name(m.chat, m.handle), deal.title, len(ins))))
        elif len(ins) >= 2:
            plan = pick_slot(now, deal.ends_ts)
            self.store.set_plan(deal.id, plan, plan - 3600)
            when = datetime.fromtimestamp(plan).strftime("%A %-I:%M%p").replace("AM", "am").replace("PM", "pm")
            self.say(m.chat, compose("going", self.rng, None, names=_join(names), verb="are", count=str(len(ins)), title=deal.title.rstrip(".!?"), when=when))
        else:
            self.say(m.chat, plain("Got you, %s. That's 1. I need one more to make it a plan." % names[0]))
        return True

    def poll_feeds(self) -> None:
        now = self.clock()
        if not self.cfg.feeds or now - self._last_feed < self.cfg.feed_every:
            return
        self._last_feed = now
        found = poll_feeds(self.cfg.feeds, now)
        for guid in self.store.active_groups():
            for f in found:
                self.store.add_deal(guid, f.title, f.link, f.ends_ts, "feed", f.key, now)

    def send_reminders(self) -> None:
        now = self.clock()
        for deal in self.store.due_reminders(now):
            self.store.mark_reminded(deal.id)
            if not self.store.is_active(deal.guid):
                continue
            names = _join([self.name(deal.guid, h) for h in self.store.who_is_in(deal.id)])
            self.say(deal.guid, compose("remind", self.rng, None, title=deal.title.rstrip(".!?"), names=names))

    # --- jumping in -------------------------------------------------------------------------------------------
    def in_quiet_hours(self, now: float) -> bool:
        hour = datetime.fromtimestamp(now).hour
        a, b = self.cfg.quiet_start, self.cfg.quiet_end
        return (hour >= a or hour < b) if a > b else (a <= hour < b)

    def may_post(self, guid: str, now: float) -> bool:
        if self.in_quiet_hours(now):
            return False
        last = self.store.last_post_ts(guid)
        if last and now - last < self.cfg.min_gap:
            return False
        midnight = datetime.fromtimestamp(now).replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
        if self.store.posts_since(guid, midnight) >= self.cfg.max_per_day:
            return False
        return now - self.store.last_msg_ts(guid) <= self.cfg.activity_window

    def eligible_quotes(self, guid: str, now: float) -> List[Quote]:
        return [
            q for q in self.store.quotes(guid)
            if now - q.ts >= self.cfg.min_quote_age and now - q.used_ts >= self.cfg.reuse_gap
        ]

    def pending_deals(self, guid: str, now: float) -> List[Deal]:
        return [d for d in self.store.open_deals(guid, now) if d.announced_ts is None]

    def maybe_jump_in(self, guid: str) -> Optional[str]:
        now = self.clock()
        if not self.may_post(guid, now):
            return None
        deals = self.pending_deals(guid, now)
        if deals:  # a found deal always gets its moment, within the same pacing limits
            return self.post_deal(guid, deals[-1], now)
        if self.rng.random() > self.cfg.prob:
            return None
        quotes = self.eligible_quotes(guid, now)
        kind = self.rng.choices(["callback", "praise"], weights=[3 if quotes else 0, 1])[0]
        if kind == "callback":
            return self.post_callback(guid, quotes, now)
        return self.post_praise(guid, now)

    def post_deal(self, guid: str, deal: Deal, now: float) -> Optional[str]:
        line = compose("deal", self.rng, self.llm, **self._facts(deal.title, deal.ends_ts, deal.link))
        if line and self.say(guid, line):
            self.store.mark_announced(deal.id, now)
            self.store.add_post(guid, now, "deal")
            return "deal"
        return None

    def post_callback(self, guid: str, quotes: List[Quote], now: float) -> Optional[str]:
        top = sorted(quotes, key=lambda q: (-q.score, q.used_ts))[:5]
        q = self.rng.choice(top)
        facts = {"name": self.name(guid, q.handle), "quote": q.text, "ago": ago(q.ts, now)}
        kind = "excuse" if q.excuse else ("praise_quote" if self.rng.random() < 0.3 else "callback")
        line = compose(kind, self.rng, self.llm, **facts)
        if line and self.say(guid, line):
            self.store.mark_used(guid, q.src, now)
            self.store.add_post(guid, now, kind)
            return kind
        return None

    def post_praise(self, guid: str, now: float) -> Optional[str]:
        busiest = self.store.busiest_since(guid, now - DAY)
        if busiest and busiest[1] >= 8 and self.rng.random() < 0.5:
            line, kind = compose("praise_busy", self.rng, self.llm, name=self.name(guid, busiest[0])), "praise_busy"
        else:
            line, kind = compose("praise", self.rng, self.llm), "praise"
        if line and self.say(guid, line):
            self.store.add_post(guid, now, kind)
            return kind
        return None


def _join(names: List[str]) -> str:
    if len(names) <= 1:
        return "".join(names)
    return ", ".join(names[:-1]) + " and " + names[-1]
