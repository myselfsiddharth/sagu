# Sagu 🌵

A small cactus that lives in your iMessage group chats. It runs on **your Mac**, using **your own Apple ID**
(whatever Messages is signed in to). It jumps in now and then with a "remember when you said..." receipt (only for
people who asked for it), sometimes with a kind word, shares **food deals**, and rallies people ("in" replies, a
proposed time, a reminder an hour before). Every line it sends starts with 🌵.

Built for the Cubbie Hackathon (DevHacks 2026), Track 3. Python 3.9+, standard library only.

## How it works

```
 Messages.app ──► ~/Library/Messages/chat.db (read-only)
                          │  poll every few seconds
                          ▼
   decode.py (attributedBody) ─► imessage.Reader ─► bot.Sagu.tick()
                                                       │
        commands.py (sagu on / roast me / deal / in)   │
        quotes.py  (pick a receipt, score it)          │
        deals.py   (typed deals, RSS/Atom feeds)       │
        store.py   (sqlite in ~/.config/sagu)          │
                                                       ▼
        voice.py: curated line bank (+ optional model, validated, retried once, else bank)
                                                       ▼
        safety.py: hard-line filter on everything stored and sent
                                                       ▼
                   imessage.OsaSender (AppleScript into the chat guid)
```

## Rules it keeps

- **Silent, and storing nothing, in a chat until the host** (the person whose Mac it is) texts `sagu on` there.
- **Only people who text `sagu roast me` are ever quoted**, and never someone Sagu has no name for.
  `sagu spare me` ends it; `sagu forget me` deletes what it saved about you.
- **Hard lines**: nothing about bodies, weight, appearance, eating, race, religion, gender, sexuality, disability,
  mental health, family or money, and no slurs, threats or sexual content. The filter runs on what is stored and on
  every line before sending. Model text is validated, retried once, then replaced by the curated bank.
- Quiet hours (23:00 to 09:00 by default), a minimum gap between jump-ins, and a daily cap.

## Setup (macOS)

1. `python3 -m sagu doctor` and follow its fixes:
   - **Full Disk Access** for your terminal app (System Settings > Privacy & Security), so it can read `chat.db`.
   - **Automation**: allow your terminal to control Messages.
2. `python3 -m sagu groups` lists your group chats.
3. `python3 -m sagu run --dry-run` prints what Sagu would send and sends nothing.
4. Make a test group, then text `sagu on` there from your own account. Drop `--dry-run` to go live.
5. Friends text `sagu help`. Commands: `sagu roast me`, `sagu spare me`, `sagu i'm Alex`,
   `sagu deal: 2-for-1 tacos till Friday`, `in` / `out`, `sagu deals`, `sagu forget me`. Host only: `sagu off`,
   `sagu forget this chat`.

Other commands: `python3 -m sagu demo` (labeled simulation: made-up friends, throwaway database, nothing sent) and
`python3 -m sagu reset` (delete everything Sagu remembers).

## Privacy: what leaves your Mac

Nothing, by default. Everything is stored in `~/.config/sagu` (override with `SAGU_HOME`). Messages are only
sent to a model provider if you set `"llm": true` in `~/.config/sagu/config.json` **and** export `ANTHROPIC_API_KEY`;
then the quote and the person's first name are sent to write the line. Tunables (`prob`, `quiet_start`, `quiet_end`,
`min_gap`, `max_per_day`, `feeds`, `owner_name`) live in the same file.

## How it was tested

`python3 -m unittest discover -s tests -t .` runs 65 tests (decoder, reader, store, hard-line filter, voice
fallback, deals, commands, and full bot flows) against `FakeMessages` fixtures that write a fake `chat.db` with made-up
people. Tests never send to real chats or read real messages. CI runs them on Python 3.9 and 3.12.

## Known limitations (honest list)

- **The AppleScript send path and the real `chat.db` reader have not been run against real group chats yet.** They
  are tested with fakes only. The `attributedBody` decoder's shape was checked by counts on a real database, not by
  reading message content.
- macOS only; needs Messages signed in on the host Mac, and that Mac awake and running Sagu.
- Polling, not push: replies can lag by a few seconds.
- The "in" count and time proposal are plain chat nudges; Sagu does not book anything anywhere.
- The optional model path has only been tested with a faked network transport, not against the live API.

## License

MIT
