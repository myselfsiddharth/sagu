import unittest
from datetime import datetime

from sagu import deals
from tests.helpers import NOON  # Wednesday 28 Oct 2026, noon

RSS = b"""<?xml version="1.0"?><rss><channel>
<item><title>BOGO burritos at Chipotle-ish through Friday</title><link>https://example.com/a</link></item>
<item><title>City council votes on parking</title><link>https://example.com/b</link></item>
<item><title>Free coffee Monday at the library cafe</title><link>http://insecure.example/c</link></item>
</channel></rss>"""
ATOM = b"""<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>$3 ramen combo</title><link href="https://example.com/r"/></entry></feed>"""


class DealParsingTests(unittest.TestCase):
    def test_deadline_words(self):
        end = lambda t: datetime.fromtimestamp(deals.parse_deadline(t, NOON))
        self.assertEqual(end("tacos till Friday").strftime("%a %d"), "Fri 30")
        self.assertEqual(end("ends tomorrow").strftime("%d"), "29")
        self.assertEqual(end("pizza until tonight").strftime("%d"), "28")
        self.assertEqual(end("wings through wednesday").strftime("%d"), "28")
        self.assertIsNone(deals.parse_deadline("tacos at monday market", NOON))  # "at" is not a deadline word
        self.assertIsNone(deals.parse_deadline("deal ends monthly", NOON))

    def test_from_text(self):
        f = deals.from_text("2-for-1 tacos at Taco Loco till Friday https://example.com/t", NOON)
        self.assertEqual(f.link, "https://example.com/t")
        self.assertNotIn("http", f.title)
        self.assertIsNone(deals.from_text("hi", NOON))
        self.assertIsNone(deals.from_text("free pizza for you @everyone", NOON))
        self.assertEqual(deals.from_text("Tacos 2-for-1 here", NOON).key, deals.from_text("tacos 2-for-1 HERE", NOON).key)

    def test_rss_keeps_only_food_and_https_links(self):
        found = deals.parse_feed(RSS, NOON)
        self.assertEqual([f.title for f in found], ["BOGO burritos at Chipotle-ish through Friday", "Free coffee Monday at the library cafe"])
        self.assertEqual(found[0].link, "https://example.com/a")
        self.assertIsNone(found[1].link)

    def test_atom(self):
        found = deals.parse_feed(ATOM, NOON)
        self.assertEqual((found[0].title, found[0].link), ("$3 ramen combo", "https://example.com/r"))

    def test_hostile_feeds_are_dropped(self):
        bomb = b'<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "aaaa">]><rss><channel><item><title>&a; free pizza</title></item></channel></rss>'
        self.assertEqual(deals.parse_feed(bomb, NOON), [])
        self.assertEqual(deals.parse_feed(b"<rss><oops", NOON), [])
        self.assertEqual(deals.parse_feed(b"x" * 600_000, NOON), [])

    def test_a_broken_feed_does_not_stop_the_others(self):
        def fetcher(url):
            if "bad" in url:
                raise OSError("down")
            return ATOM
        got = deals.poll_feeds(["https://bad.example/f", "https://ok.example/f"], NOON, fetcher)
        self.assertEqual(len(got), 1)

    def test_only_https_feeds_are_fetched(self):
        self.assertEqual(deals.fetch("http://example.com/f"), b"")
        self.assertEqual(deals.fetch("file:///etc/passwd"), b"")

    def test_slot_is_tonight_tomorrow_or_before_the_deadline(self):
        slot = lambda ends: datetime.fromtimestamp(deals.pick_slot(NOON, ends))
        self.assertEqual((slot(None).day, slot(None).hour, slot(None).minute), (28, 18, 30))  # before 3pm: tonight
        late = datetime(2026, 10, 28, 17, 0).timestamp()
        self.assertEqual(datetime.fromtimestamp(deals.pick_slot(late, None)).day, 29)
        ends_today = datetime(2026, 10, 28, 23, 59).timestamp()
        self.assertEqual(datetime.fromtimestamp(deals.pick_slot(late, ends_today)).day, 28)
        after = datetime(2026, 10, 28, 20, 0).timestamp()
        self.assertEqual(deals.pick_slot(after, ends_today), after + 3600)


if __name__ == "__main__":
    unittest.main()
