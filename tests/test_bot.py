import json
import os
import tempfile
import unittest
from datetime import datetime

from sagu import PREFIX
from sagu.bot import Config
from sagu.imessage import ME, Reader
from sagu.sim import ANA, BEN, CY, GUID
from tests.helpers import DAY, NOON, World


def lines(world):
    return [t for _, t in world.sender.sent]


class ConsentTests(unittest.TestCase):
    def test_silent_and_storing_nothing_until_the_host_says_sagu_on(self):
        w = World()
        w.past(ANA, "I'll start the 6am gym thing on Monday, for real this time", 20)
        w.store.set_cursor(0)
        for who, text in ((ANA, "sagu roast me"), (BEN, "lol anyone up"), (CY, "sagu on")):  # Cy is not the host
            w.say(who, text)
        self.assertEqual(w.sender.sent, [])
        self.assertEqual(w.store.db.execute("SELECT COUNT(*) FROM members").fetchone()[0], 0)
        self.assertEqual(w.store.db.execute("SELECT COUNT(*) FROM quotes").fetchone()[0], 0)
        self.assertFalse(w.store.is_active(GUID))

    def test_only_the_host_can_send_it_away(self):
        w = World().start()
        self.assertIn("Only the person", w.say(BEN, "sagu off")[0])
        self.assertTrue(w.store.is_active(GUID))
        self.assertIn("Leaving", w.say(ME, "sagu off")[0])
        self.assertFalse(w.store.is_active(GUID))
        self.assertEqual(w.say(ANA, "sagu help"), [])

    def test_a_friend_who_never_opts_in_is_never_quoted(self):
        w = World()
        w.past(BEN, "bro I literally cannot function without iced coffee", 10)
        w.start()
        for i in range(30):
            w.say(BEN, "I swear I'm going to do the laundry tomorrow %d" % i, dt=40 * 60)
        self.assertEqual(w.store.db.execute("SELECT COUNT(*) FROM quotes WHERE handle=?", (BEN,)).fetchone()[0], 0)
        self.assertFalse(any("laundry" in t or "iced coffee" in t for t in lines(w)))

    def test_opt_in_looks_back_through_that_persons_old_messages_only(self):
        w = World()
        w.past(ANA, "I'll start the 6am gym thing on Monday, for real this time", 20)
        w.past(BEN, "I swear I'm going to finish the lab report tomorrow", 20)
        w.start()
        stored = {r[0] for r in w.store.db.execute("SELECT handle FROM quotes")}
        self.assertEqual(stored, {ANA})

    def test_spare_me_deletes_quotes_and_forget_me_deletes_everything(self):
        w = World()
        w.past(ANA, "I'll start the 6am gym thing on Monday, for real this time", 20)
        w.start()
        self.assertEqual(w.store.db.execute("SELECT COUNT(*) FROM quotes").fetchone()[0], 1)
        w.say(ANA, "sagu spare me")
        self.assertEqual(w.store.db.execute("SELECT COUNT(*) FROM quotes").fetchone()[0], 0)
        self.assertFalse(w.store.is_opted_in(GUID, ANA))
        w.say(ANA, "sagu roast me")
        w.say(ANA, "sagu forget me")
        for table in ("members", "quotes", "activity"):
            self.assertEqual(w.store.db.execute("SELECT COUNT(*) FROM %s WHERE handle=?" % table, (ANA,)).fetchone()[0], 0, table)

    def test_forget_chat_wipes_the_group(self):
        w = World().start()
        w.say(CY, "sagu deal: 2-for-1 tacos at Taco Loco till Friday")
        w.say(ME, "sagu forget everything")
        for table in ("members", "quotes", "activity", "posts", "deals"):
            self.assertEqual(w.store.db.execute("SELECT COUNT(*) FROM %s" % table).fetchone()[0], 0, table)
        self.assertFalse(w.store.is_active(GUID))

    def test_unnamed_people_are_never_quoted_by_a_made_up_name(self):
        w = World()
        w.past(CY, "I swear I'm going to finish the lab report tomorrow", 20)
        w.store.set_cursor(0)
        w.start()
        w.say(CY, "sagu roast me")  # opted in but never gave a name
        self.assertEqual(w.store.quotes(GUID), [])


class PacingTests(unittest.TestCase):
    def chatty(self, **cfg):
        base = dict(owner_name="Dev", prob=1.0, min_gap=90 * 60, min_quote_age=DAY, quiet_start=23, quiet_end=9)
        base.update(cfg)
        w = World(Config(**base))
        w.past(ANA, "I'll start the 6am gym thing on Monday, for real this time", 20)
        w.past(ANA, "okay LISTEN I am going to sleep before midnight tonight", 12)
        w.past(ANA, "I swear I'm going to finish the lab report tomorrow", 9)
        return w.start()

    def test_it_jumps_in_sometimes_with_a_receipt_and_sometimes_with_kindness(self):
        seen = set()
        for seed in range(30):
            w = self.chatty()
            w.bot.rng.seed(seed)
            out = w.say(BEN, "anyone want to get dinner")
            self.assertEqual(len(out), 1)
            self.assertTrue(out[0].startswith(PREFIX))
            seen.add("receipt" if "Ana" in out[0] else "kindness")
        self.assertEqual(seen, {"receipt", "kindness"})

    def test_a_receipt_names_the_person_and_quotes_them_exactly(self):
        w = self.chatty()
        kind = w.bot.post_callback(GUID, w.bot.eligible_quotes(GUID, w.now), w.now)
        self.assertIn(kind, ("excuse", "callback", "praise_quote"))
        line = w.sender.sent[-1][1]
        self.assertIn("Ana", line)
        self.assertTrue(any(q in line for q in ("6am gym thing", "before midnight", "lab report")))

    def test_minimum_gap_between_unprompted_lines(self):
        w = self.chatty()
        w.say(BEN, "anyone want to get dinner")
        self.assertEqual(w.say(BEN, "hello?", dt=10 * 60), [])
        self.assertEqual(len(w.say(BEN, "hello??", dt=100 * 60)), 1)

    def test_daily_cap(self):
        w = self.chatty(min_gap=0, max_per_day=2)
        sent = 0
        for i in range(10):
            sent += len(w.say(BEN, "chatter number %d" % i, dt=60))
        self.assertEqual(sent, 2)

    def test_quiet_hours_midnight_wrap(self):
        w = self.chatty()
        w.now = datetime(2026, 10, 28, 23, 30).timestamp()
        self.assertEqual(w.say(BEN, "late night thoughts", dt=60), [])
        w.now = datetime(2026, 10, 29, 8, 0).timestamp()
        self.assertEqual(w.say(BEN, "very early thoughts", dt=60), [])
        w.now = datetime(2026, 10, 29, 12, 0).timestamp()
        self.assertEqual(len(w.say(BEN, "lunch thoughts", dt=60)), 1)

    def test_only_jumps_into_a_chat_that_is_talking_right_now(self):
        w = self.chatty()
        w.bot.store.touch(GUID, w.now - 3 * 3600)
        self.assertIsNone(w.bot.maybe_jump_in(GUID))

    def test_probability_zero_means_never(self):
        w = self.chatty(prob=0.0)
        for i in range(10):
            self.assertEqual(w.say(BEN, "chatter %d" % i, dt=3 * 3600), [])

    def test_a_quote_is_not_reused_inside_two_weeks_and_too_fresh_quotes_wait(self):
        w = World(Config(owner_name="Dev", prob=1.0, min_gap=0, min_quote_age=2 * DAY))
        w.past(ANA, "I'll start the 6am gym thing on Monday, for real this time", 20)
        w.past(ANA, "I swear I'm going to finish the lab report tomorrow", 0.5)  # too fresh
        w.start()
        quotes = w.bot.eligible_quotes(GUID, w.now)
        self.assertEqual(len(quotes), 1)  # the half-day-old promise is too fresh to bring up
        w.bot.post_callback(GUID, quotes, w.now)
        self.assertIn("gym thing", w.sender.sent[-1][1])
        resting = w.bot.eligible_quotes(GUID, w.now + 10 * DAY)  # the one just used is still resting 10 days later
        self.assertTrue(all("gym thing" not in q.text for q in resting))
        self.assertEqual(len(w.bot.eligible_quotes(GUID, w.now + 15 * DAY)), 2)

    def test_its_own_lines_coming_back_through_the_database_are_ignored(self):
        w = World().start()
        n = len(w.sender.sent)
        w.say(ME, PREFIX + " sagu roast me, I am a loop")
        self.assertEqual(len(w.sender.sent), n)


class DealTests(unittest.TestCase):
    def test_deal_flow_headcount_plan_and_reminder(self):
        w = World().start()
        out = w.say(CY, "sagu deal: 2-for-1 tacos at Taco Loco till Friday https://example.com/tacos")
        self.assertIn("2-for-1 tacos", out[0])
        self.assertIn("https://example.com/tacos", out[0])
        self.assertIn("1", w.say(ANA, "in")[0])
        plan = w.say(BEN, "im in")[0]
        self.assertIn("Ana and Ben", plan)
        deal = w.store.open_deals(GUID, w.now)[0]
        self.assertIsNotNone(deal.plan_ts)
        w.now = deal.remind_ts + 1
        before = len(w.sender.sent)
        w.bot.tick()
        self.assertEqual(len(w.sender.sent), before + 1)
        self.assertIn("about an hour", w.sender.sent[-1][1])
        w.bot.tick()
        self.assertEqual(len(w.sender.sent), before + 1)  # only once

    def test_bare_in_with_no_open_deal_is_just_chatter(self):
        w = World(Config(owner_name="Dev", prob=0.0)).start()
        self.assertEqual(w.say(ANA, "in"), [])
        self.assertEqual(w.store.db.execute("SELECT COUNT(*) FROM rsvps").fetchone()[0], 0)

    def test_out_and_late_joiners_and_duplicates(self):
        w = World().start()
        w.say(CY, "sagu deal: $5 burrito bowls at the student union until tomorrow")
        self.assertIn("already", w.say(CY, "sagu deal: $5 burrito bowls at the student union until tomorrow")[0])
        self.assertEqual(w.say(ANA, "out"), [])
        self.assertEqual(w.store.who_is_in(1), [])
        w.say(ANA, "in")
        w.say(BEN, "in")
        self.assertIn("Added", w.say(CY, "in")[0])

    def test_garbage_deal_is_refused_and_deals_lists_open_ones(self):
        w = World().start()
        self.assertIn("more than that", w.say(CY, "sagu deal: hi")[0])
        self.assertIn("No open deals", w.say(CY, "sagu deals")[0])
        w.say(CY, "sagu deal: half off wings at the sports bar till Friday")
        self.assertIn("half off wings", w.say(CY, "sagu deals")[0])

    def test_feed_deals_are_announced_once_when_the_chat_is_live(self):
        w = World(Config(owner_name="Dev", prob=0.0, min_gap=0, feeds=["https://feeds.example/food.xml"], feed_every=0)).start()
        import sagu.bot as botmod
        from sagu.deals import Found
        original = botmod.poll_feeds
        botmod.poll_feeds = lambda urls, now: [Found("BOGO pizza at Slice Shop", "https://example.com/p", None, "k1")]
        try:
            w.bot.tick()
        finally:
            botmod.poll_feeds = original
        out = w.say(BEN, "what is for dinner")
        self.assertEqual(len(out), 1)
        self.assertIn("BOGO pizza", out[0])
        self.assertEqual(w.say(BEN, "anyone?"), [])  # announced once, then it is a normal deal


class RobustnessTests(unittest.TestCase):
    def test_first_run_starts_from_now_not_from_history(self):
        w = World()
        w.past(ANA, "sagu on", 3)  # an old message that would have switched Sagu on
        w.store.db.execute("DELETE FROM meta")
        w.store.db.commit()
        w.bot.tick()
        self.assertFalse(w.store.is_active(GUID))
        self.assertEqual(w.store.cursor(), Reader(w.fake.path).max_rowid())

    def test_send_failures_do_not_crash_or_record_a_post(self):
        w = World().start()
        class Broken:
            def send(self, chat, text):
                from sagu.imessage import SendError
                raise SendError("Messages is not running")
        w.bot.sender = Broken()
        w.say(CY, "sagu deal: 2-for-1 tacos at Taco Loco till Friday")
        self.assertEqual(w.store.db.execute("SELECT COUNT(*) FROM posts").fetchone()[0], 0)

    def test_unknown_commands_only_get_a_nudge_when_short(self):
        w = World().start()
        self.assertEqual(len(w.say(ANA, "sagu?")), 1)
        self.assertEqual(w.say(ANA, "sagu is honestly the funniest cactus I have ever met in my life"), [])

    def test_config_loading_ignores_bad_types_and_missing_files(self):
        with tempfile.TemporaryDirectory() as home:
            self.assertEqual(Config.load(home).prob, 0.25)
            with open(os.path.join(home, "config.json"), "w") as fh:
                json.dump({"prob": "lots", "max_per_day": 2, "owner_name": "Sid", "llm": "yes", "feeds": ["https://a.example/f"], "bogus": 1}, fh)
            cfg = Config.load(home)
            self.assertEqual((cfg.prob, cfg.max_per_day, cfg.owner_name, cfg.llm, cfg.feeds), (0.25, 2, "Sid", False, ["https://a.example/f"]))
            with open(os.path.join(home, "config.json"), "w") as fh:
                fh.write("[1,2")
            self.assertEqual(Config.load(home).max_per_day, 4)


if __name__ == "__main__":
    unittest.main()
