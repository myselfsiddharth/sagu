import unittest

from sagu.decode import encode_for_tests, message_text
from sagu.imessage import ME, Reader, apple_to_unix, unix_to_apple
from sagu.sim import ANA, BEN, GUID, FakeMessages
from tests.helpers import NOON, World


class DecodeTests(unittest.TestCase):
    def test_plain_text_wins(self):
        self.assertEqual(message_text("hello there", None), "hello there")

    def test_reads_blob_of_every_length_class(self):
        for n in (5, 127, 128, 400, 70000):
            text = ("x" * (n - 1)) + "é"
            self.assertEqual(message_text(None, encode_for_tests(text)), text, n)

    def test_unreadable_or_empty_is_none(self):
        self.assertIsNone(message_text(None, None))
        self.assertIsNone(message_text("", b"nonsense"))
        self.assertIsNone(message_text(None, b"NSString\x01+\x7fshort"))
        self.assertIsNone(message_text("￼", None))  # an attachment placeholder is not words

    def test_time_round_trip(self):
        self.assertAlmostEqual(apple_to_unix(unix_to_apple(NOON)), NOON, places=3)
        self.assertAlmostEqual(apple_to_unix(int(NOON - 978307200)), NOON, places=3)  # older seconds format


class ReaderTests(unittest.TestCase):
    def setUp(self):
        self.fake = FakeMessages()
        self.fake.group(GUID, "Test chat", [ANA, BEN])
        self.fake.group("iMessage;-;+15550199999", "x", [])
        self.fake.db.execute("UPDATE chat SET style=45 WHERE guid='iMessage;-;+15550199999'")
        self.fake.db.commit()

    def test_skips_tapbacks_system_rows_one_on_one_chats_and_empty_blobs(self):
        self.fake.say(GUID, ANA, "a real message here", NOON)
        self.fake.say(GUID, BEN, 'Liked "a real message here"', NOON, kind=2001)
        self.fake.say(GUID, BEN, "renamed the chat", NOON, item=2)
        self.fake.say("iMessage;-;+15550199999", ANA, "private one on one", NOON)
        got = Reader(self.fake.path).new_messages(0)
        self.assertEqual([m.text for m in got], ["a real message here"])

    def test_reads_modern_blob_rows_and_marks_my_own(self):
        self.fake.say(GUID, ANA, "stored only as a blob", NOON, use_blob=True)
        self.fake.say(GUID, ME, "I sent this", NOON + 1)
        a, b = Reader(self.fake.path).new_messages(0)
        self.assertEqual((a.text, a.handle, a.is_from_me), ("stored only as a blob", ANA, False))
        self.assertEqual((b.handle, b.is_from_me), (ME, True))

    def test_history_is_one_person_in_one_chat_within_the_window(self):
        self.fake.say(GUID, ANA, "ana, long ago", NOON - 200 * 86400)
        self.fake.say(GUID, ANA, "ana, recently", NOON - 5 * 86400)
        self.fake.say(GUID, BEN, "ben, recently", NOON - 5 * 86400)
        self.fake.say(GUID, ME, "me, recently", NOON - 5 * 86400)
        r = Reader(self.fake.path)
        self.assertEqual([m.text for m in r.history(GUID, ANA, NOON - 90 * 86400)], ["ana, recently"])
        self.assertEqual([m.text for m in r.history(GUID, ME, NOON - 90 * 86400)], ["me, recently"])

    def test_groups_lists_only_group_chats(self):
        self.assertEqual([g[1] for g in Reader(self.fake.path).groups()], ["Test chat"])

    def test_opens_read_only(self):
        r = Reader(self.fake.path)
        with self.assertRaises(Exception):
            r._db.execute("DELETE FROM message")


if __name__ == "__main__":
    unittest.main()
