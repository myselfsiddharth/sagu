import random
import unittest

from sagu.commands import parse
from sagu.games import Games
from sagu.safety import clean_line
from sagu.sim import ANA, BEN
from tests.helpers import World


class GameTests(unittest.TestCase):
    def test_parse_routes_game_words_and_numbers(self):
        for text in ("sagu trivia", "sagu 25", "sagu pick a, b", "sagu 8ball will we win?", "sagu scores"):
            self.assertEqual(parse(text).name, "game", text)
        self.assertEqual(parse("sagu hello there friend of mine").name, "unknown")

    def test_guess_the_number_to_a_win_and_a_point(self):
        g = Games(random.Random(1))
        g.play("c", "Ana", "guess")
        n = g.rounds["c"].data["n"]
        low = g.play("c", "Ana", str(max(1, n - 1)) if n > 1 else "50")
        self.assertIn("too", low)
        self.assertIn("got it", g.play("c", "Ben", str(n)))
        self.assertEqual(g.scores["c"], {"Ben": 1})
        self.assertNotIn("c", g.rounds)

    def test_a_number_with_no_game_is_ignored(self):
        self.assertIsNone(Games().play("c", "Ana", "25"))

    def test_trivia_one_try_each_and_scoring(self):
        g = Games(random.Random(2))
        g.play("c", "Ana", "trivia")
        ans = g.rounds["c"].data["answer"]
        wrong = ans % 3 + 1
        self.assertIn("not quite", g.play("c", "Ana", str(wrong)))
        self.assertIsNone(g.play("c", "Ana", str(ans)))  # second try ignored
        self.assertIn("right", g.play("c", "Ben", str(ans)))

    def test_hangman_win_and_loss(self):
        g = Games(random.Random(3))
        g.play("c", "Ana", "hangman")
        word = g.rounds["c"].data["word"]
        for ch in sorted(set(word)):
            out = g.play("c", "Ana", "letter " + ch)
        self.assertIn("finished it", out)
        g.play("c", "Ana", "hangman")
        word = g.rounds["c"].data["word"]
        for ch in [c for c in "zqxjkvw" if c not in word][:6]:
            out = g.play("c", "Ana", "letter " + ch)
        self.assertIn("wilted", out)

    def test_wyr_tallies_votes(self):
        g = Games(random.Random(4))
        g.play("c", "x", "wyr")
        g.play("c", "Ana", "a")
        self.assertIn("A: 1, B: 1", g.play("c", "Ben", "b"))

    def test_toys(self):
        g = Games(random.Random(5))
        self.assertIn("at least two", g.play("c", "Ana", "pick pizza"))
        self.assertIn("I pick", g.play("c", "Ana", "pick pizza, tacos or sushi"))
        self.assertIn("Rolled 2d20", g.play("c", "Ana", "dice 2d20"))
        self.assertIn("first", g.play("c", "Ana", "8ball"))

    def test_every_canned_line_passes_the_hard_line_filter(self):
        from sagu import games
        texts = list(games.BALL) + [q for q, _, _ in games.TRIVIA] + [o for _, os, _ in games.TRIVIA for o in os]
        texts += [x for pair in games.WYR for x in pair] + games.WORDS
        for t in texts:
            self.assertIsNotNone(clean_line("\U0001F335 " + t), t)

    def test_in_a_real_chat_flow(self):
        w = World().start()
        w.say(ANA, "sagu i'm Ana")
        out = w.say(ANA, "sagu trivia")
        self.assertTrue(out[0].startswith("\U0001F335 Trivia"))
        self.assertTrue(w.say(BEN, "sagu games")[0].startswith("\U0001F335 Games"))
        self.assertIn("Ben", w.say(BEN, "sagu 25")[0])  # trivia is running, so numbers answer it
        w.say(ANA, "sagu stop")
        self.assertEqual(w.say(BEN, "sagu 25"), [])  # nothing running: stay quiet
