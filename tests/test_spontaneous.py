import unittest

from sagu import voice
from sagu.bot import Config
from sagu.imessage import ME
from sagu.safety import clean_roast
from sagu.sim import ANA
from tests.helpers import DAY, NOON, World


def cfg(**kw):
    base = dict(owner_name="Dev", prob=0.0, min_gap=0, spont_every=60.0, spont_check=60.0, max_per_day=4)
    base.update(kw)
    return Config(**base)


def talk(w, who, text):
    """A message without letting the bot speak up on its own during that tick."""
    w.bot.cfg.chatty = False
    w.say(who, text)
    w.bot.cfg.chatty = True


class SpontaneousTests(unittest.TestCase):
    def test_greets_a_quiet_chat_once_a_day_then_waits_for_an_answer(self):
        w = World(cfg()).start()
        talk(w, ANA, "hey everyone")
        w.sender.sent.clear()
        for _ in range(40):
            w.now += 60
            w.bot.tick()
        sent = [t for _, t in w.sender.sent]
        self.assertEqual(len(sent), 1)  # no monologue: nobody answered the greeting
        self.assertTrue(sent[0].startswith("\U0001F335"))
        talk(w, ANA, "morning!")
        for _ in range(40):
            w.now += 60
            w.bot.tick()
        self.assertGreaterEqual(len(w.sender.sent), 2)

    def test_silent_in_chats_that_are_not_on_and_during_quiet_hours(self):
        w = World(cfg())  # never turned on
        for _ in range(60):
            w.now += 60
            w.bot.tick()
        self.assertEqual(w.sender.sent, [])
        w = World(cfg()).start()
        talk(w, ANA, "hey")
        w.bot.cfg.quiet_start, w.bot.cfg.quiet_end = 11, 14  # noon is quiet
        w.sender.sent.clear()
        for _ in range(60):
            w.now += 60
            w.bot.tick()
        self.assertEqual(w.sender.sent, [])

    def test_can_be_turned_off_and_respects_the_daily_cap(self):
        w = World(cfg(chatty=False)).start()
        talk(w, ANA, "hey")
        w.bot.cfg.chatty = False
        w.sender.sent.clear()
        for _ in range(60):
            w.now += 60
            w.bot.tick()
        self.assertEqual(w.sender.sent, [])
        w = World(cfg(max_per_day=2)).start()
        w.sender.sent.clear()
        for _ in range(200):
            w.say(ANA, "hey", dt=120)
        self.assertLessEqual(len(w.sender.sent), 2)

    def test_greeting_matches_the_time_of_day(self):
        w = World(cfg(chatty=False)).start()
        talk(w, ANA, "hey everyone")
        w.bot.cfg.chatty = True
        w.sender.sent.clear()
        for _ in range(40):
            w.now += 60
            w.bot.tick()
        self.assertIn(w.sender.sent[0][1][2:], voice.GREET_AFTERNOON)  # starts just after noon

    def test_every_greeting_and_comment_passes_the_hard_line_filter(self):
        for bank in (voice.GREET_MORNING, voice.GREET_AFTERNOON, voice.GREET_EVENING, voice.CHIME):
            for line in bank:
                self.assertIsNotNone(clean_roast(line), line)
                self.assertLessEqual(len(line), 200)


if __name__ == "__main__":
    unittest.main()
