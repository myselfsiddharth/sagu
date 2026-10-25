"""Little games to play with Sagu in a group chat. One game per chat at a time, kept in memory (a restart ends them).

Everything here is a fixed, curated bank: no model text, nothing about anyone's body, money, family or health.
"""
from __future__ import annotations

import random
import re
from typing import Callable, Dict, List, Optional

GAME_WORDS = ("flip", "dice", "roll", "8ball", "ask", "pick", "guess", "trivia", "hangman", "letter", "wyr", "a", "b", "scores", "games", "stop")

BALL = [
    "Yes. Obviously.", "Ask again after some water.", "Signs point to yes.", "Absolutely not.", "My spines say no.",
    "Outlook sunny.", "Doubtful. Cacti are realists.", "Do it. Worry later.", "Not today.", "Without a doubt.",
    "Too early to tell. Photosynthesis is slow.", "The desert says maybe.",
]

TRIVIA = [
    ("How often does a desert cactus need watering?", ["Every day", "Every few weeks", "Never, ever"], 2),
    ("Which of these is a real plant that stores water in its stem?", ["Saguaro", "Poplar", "Dandelion"], 1),
    ("A saguaro can grow arms after roughly how many years?", ["5", "30 to 75", "300"], 2),
    ("What are cactus spines, really?", ["Modified leaves", "Roots", "Dried flowers"], 1),
    ("Which planet is closest to the sun?", ["Venus", "Mercury", "Mars"], 2),
    ("How many sides does a hexagon have?", ["5", "6", "8"], 2),
    ("What is the largest ocean on Earth?", ["Atlantic", "Pacific", "Indian"], 2),
    ("Which animal is known for building dams?", ["Otter", "Beaver", "Heron"], 2),
    ("What is the capital of Japan?", ["Kyoto", "Osaka", "Tokyo"], 3),
    ("How many continents are there?", ["5", "7", "9"], 2),
    ("Which gas do plants take in?", ["Carbon dioxide", "Helium", "Neon"], 1),
    ("What is the hardest natural substance?", ["Gold", "Diamond", "Quartz"], 2),
]

WYR = [
    ("always be 10 minutes early", "always be 10 minutes late"),
    ("have a pet dragon the size of a cat", "have a pet cat the size of a dragon"),
    ("only be able to whisper", "only be able to shout"),
    ("live in a treehouse", "live in a lighthouse"),
    ("never lose your keys but always lose your charger", "never lose your charger but always lose your keys"),
    ("have a rewind button for your day", "have a pause button for your day"),
    ("be able to talk to plants", "be able to talk to birds"),
    ("take a road trip with no map", "take a train trip with no schedule"),
    ("have summer all year", "have autumn all year"),
    ("every song you hear be a remix", "every movie you watch be a sequel"),
]

WORDS = ["cactus", "desert", "sunrise", "balloon", "picnic", "compass", "lantern", "puzzle", "marble", "thunder", "backpack", "festival", "journey", "mystery", "pancake"]
MAX_WRONG = 6


class Round:
    def __init__(self, kind: str, **data) -> None:
        self.kind = kind
        self.data = data


class Games:
    def __init__(self, rng: Optional[random.Random] = None) -> None:
        self.rng = rng or random.Random()
        self.rounds: Dict[str, Round] = {}
        self.scores: Dict[str, Dict[str, int]] = {}

    # --- helpers --------------------------------------------------------------------------------------------
    def _win(self, chat: str, who: str, points: int = 1) -> None:
        board = self.scores.setdefault(chat, {})
        board[who] = board.get(who, 0) + points

    def _board(self, chat: str) -> str:
        board = self.scores.get(chat)
        if not board:
            return "No points yet. Try \"sagu trivia\" or \"sagu guess\"."
        top = sorted(board.items(), key=lambda kv: (-kv[1], kv[0]))[:5]
        return "Scoreboard:\n" + "\n".join("%d. %s - %d" % (i + 1, n, p) for i, (n, p) in enumerate(top))

    # --- entry point ----------------------------------------------------------------------------------------
    def play(self, chat: str, who: str, text: str) -> Optional[str]:
        """text is what followed "sagu". Returns a reply, or None if it isn't a game move."""
        words = text.strip().split(None, 1)
        if not words:
            return None
        head, rest = words[0].lower().rstrip("?!.,:"), (words[1].strip() if len(words) > 1 else "")
        if re.fullmatch(r"\d{1,3}", head):
            return self._number(chat, who, int(head))
        if head not in GAME_WORDS:
            return None
        handler: Dict[str, Callable[[], Optional[str]]] = {
            "flip": lambda: self.rng.choice(["Heads.", "Tails.", "Heads. Final answer.", "Tails. Sorry."]),
            "dice": lambda: self._dice(rest), "roll": lambda: self._dice(rest),
            "8ball": lambda: self._ball(rest), "ask": lambda: self._ball(rest),
            "pick": lambda: self._pick(rest),
            "guess": lambda: self._guess(chat, who, rest),
            "trivia": lambda: self._trivia(chat),
            "hangman": lambda: self._hangman(chat),
            "letter": lambda: self._letter(chat, who, rest),
            "wyr": lambda: self._wyr(chat),
            "a": lambda: self._vote(chat, who, "a"), "b": lambda: self._vote(chat, who, "b"),
            "scores": lambda: self._board(chat),
            "games": lambda: GAMES_HELP,
            "stop": lambda: self._stop(chat),
        }
        return handler[head]()

    # --- one-shot toys --------------------------------------------------------------------------------------
    def _dice(self, rest: str) -> str:
        m = re.fullmatch(r"(?:(\d{1,2})d)?(\d{1,3})?", rest.strip().lower())
        count, sides = (int(m.group(1) or 1), int(m.group(2) or 6)) if m else (1, 6)
        count, sides = max(1, min(count, 10)), max(2, min(sides, 100))
        rolls = [self.rng.randint(1, sides) for _ in range(count)]
        return "Rolled %dd%d: %s%s" % (count, sides, ", ".join(map(str, rolls)), " (total %d)" % sum(rolls) if count > 1 else "")

    def _ball(self, rest: str) -> str:
        if not rest:
            return "Ask me something first: sagu 8ball will we win?"
        return self.rng.choice(BALL)

    def _pick(self, rest: str) -> str:
        options = [o.strip() for o in re.split(r",|\bor\b|\|", rest) if o.strip()]
        if len(options) < 2:
            return "Give me at least two options: sagu pick pizza, tacos, sushi"
        return "I pick: %s." % self.rng.choice(options[:12])

    # --- guess the number -----------------------------------------------------------------------------------
    def _guess(self, chat: str, who: str, rest: str) -> str:
        if rest.isdigit():
            return self._number(chat, who, int(rest))
        self.rounds[chat] = Round("guess", n=self.rng.randint(1, 50), tries=0)
        return "I'm thinking of a number from 1 to 50. Guess with \"sagu 25\". Anyone can play."

    def _number(self, chat: str, who: str, n: int) -> Optional[str]:
        r = self.rounds.get(chat)
        if not r:
            return None
        if r.kind == "guess":
            r.data["tries"] += 1
            if n == r.data["n"]:
                del self.rounds[chat]
                self._win(chat, who)
                return "%s got it: %d, in %d tries. +1 point." % (who, n, r.data["tries"])
            if r.data["tries"] >= 12:
                del self.rounds[chat]
                return "Out of tries. It was %d." % r.data["n"]
            return "%d is too %s." % (n, "low" if n < r.data["n"] else "high")
        if r.kind == "trivia":
            if who in r.data["answered"]:
                return None
            r.data["answered"].add(who)
            if n == r.data["answer"]:
                del self.rounds[chat]
                self._win(chat, who)
                return "%s is right: %s. +1 point." % (who, r.data["options"][n - 1])
            if len(r.data["answered"]) >= 6:
                del self.rounds[chat]
                return "Nobody got it. The answer was %d, %s." % (r.data["answer"], r.data["options"][r.data["answer"] - 1])
            return "%s: not quite." % who
        return None

    # --- trivia ---------------------------------------------------------------------------------------------
    def _trivia(self, chat: str) -> str:
        q, options, answer = self.rng.choice(TRIVIA)
        self.rounds[chat] = Round("trivia", options=options, answer=answer, answered=set())
        return "Trivia: %s\n%s\nAnswer with \"sagu 1\", \"sagu 2\" or \"sagu 3\". One try each." % (q, "\n".join("%d. %s" % (i + 1, o) for i, o in enumerate(options)))

    # --- would you rather -----------------------------------------------------------------------------------
    def _wyr(self, chat: str) -> str:
        a, b = self.rng.choice(WYR)
        self.rounds[chat] = Round("wyr", a=a, b=b, votes={})
        return "Would you rather...\nA. %s\nB. %s\nVote with \"sagu a\" or \"sagu b\"." % (a, b)

    def _vote(self, chat: str, who: str, side: str) -> Optional[str]:
        r = self.rounds.get(chat)
        if not r or r.kind != "wyr":
            return None
        r.data["votes"][who] = side
        votes = r.data["votes"]
        na, nb = sum(1 for v in votes.values() if v == "a"), sum(1 for v in votes.values() if v == "b")
        return "%s picked %s. A: %d, B: %d." % (who, side.upper(), na, nb)

    # --- hangman --------------------------------------------------------------------------------------------
    def _hangman(self, chat: str) -> str:
        self.rounds[chat] = Round("hangman", word=self.rng.choice(WORDS), seen=set(), wrong=0)
        r = self.rounds[chat]
        return "Hangman! %s\nGuess with \"sagu letter e\". %d misses and the cactus wilts." % (self._mask(r), MAX_WRONG)

    @staticmethod
    def _mask(r: Round) -> str:
        return " ".join(c if c in r.data["seen"] else "_" for c in r.data["word"])

    def _letter(self, chat: str, who: str, rest: str) -> Optional[str]:
        r = self.rounds.get(chat)
        if not r or r.kind != "hangman":
            return "No hangman going. Start one with \"sagu hangman\"."
        letter = rest.strip().lower()
        if len(letter) != 1 or not letter.isalpha():
            return "One letter at a time: sagu letter e"
        if letter in r.data["seen"]:
            return "Already tried %s. %s" % (letter, self._mask(r))
        if letter in r.data["word"]:
            r.data["seen"].add(letter)
            if all(c in r.data["seen"] for c in r.data["word"]):
                word = r.data["word"]
                del self.rounds[chat]
                self._win(chat, who, 2)
                return "%s finished it: %s. +2 points." % (who, word)
            return "Yes. %s" % self._mask(r)
        r.data["seen"].add(letter)
        r.data["wrong"] += 1
        left = MAX_WRONG - r.data["wrong"]
        if left <= 0:
            word = r.data["word"]
            del self.rounds[chat]
            return "The cactus wilted. The word was %s." % word
        return "Nope. %d misses left. %s" % (left, self._mask(r))

    def _stop(self, chat: str) -> str:
        return "Game over." if self.rounds.pop(chat, None) else "No game running."


GAMES_HELP = (
    "Games:\n"
    "sagu trivia - quick question, answer with sagu 1/2/3\n"
    "sagu guess - number from 1 to 50, answer with sagu 25\n"
    "sagu hangman - then sagu letter e\n"
    "sagu wyr - would you rather, vote sagu a / sagu b\n"
    "sagu 8ball <question>, sagu pick x, y, z, sagu flip, sagu dice (or 2d20)\n"
    "sagu scores - points so far, sagu stop - end the game"
)
