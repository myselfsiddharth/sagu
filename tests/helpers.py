import random
from datetime import datetime

from sagu.bot import Config, Sagu
from sagu.imessage import ME, DrySender, Reader
from sagu.sim import ANA, BEN, CY, GUID, FakeMessages
from sagu.store import Store

NOON = datetime(2026, 10, 28, 12, 0).timestamp()  # a Wednesday, midday local time
DAY = 86400.0


class World:
    """A fake Mac: a throwaway chat.db, an in-memory store, a recording sender and a clock the test controls."""

    def __init__(self, cfg=None, seed=1, llm=None, history=True):
        self.fake = FakeMessages()
        self.fake.group(GUID, "Test chat", [ANA, BEN, CY])
        self.store = Store(":memory:")
        self.sender = DrySender()
        self.now = NOON
        self.cfg = cfg or Config(owner_name="Dev", prob=1.0, min_gap=0, min_quote_age=DAY, chatty=False)
        self.history = []
        self.bot = Sagu(self.store, Reader(self.fake.path), self.sender, self.cfg, clock=lambda: self.now, rng=random.Random(seed), llm=llm)
        self.store.set_cursor(0)

    def past(self, handle, text, days_ago):
        self.fake.say(GUID, handle, text, NOON - days_ago * DAY)

    def say(self, handle, text, dt=60.0):
        self.now += dt
        self.fake.say(GUID, handle, text, self.now)
        before = len(self.sender.sent)
        self.bot.tick()
        return [t for _, t in self.sender.sent[before:]]

    def start(self):
        """Skip history and turn Sagu on, with Ana named and opted in, Ben named only."""
        self.store.set_cursor(Reader(self.fake.path).max_rowid())
        self.say(ME, "sagu on")
        self.say(ANA, "sagu i'm Ana")
        self.say(ANA, "sagu roast me")
        self.say(BEN, "sagu i'm Ben")
        return self
