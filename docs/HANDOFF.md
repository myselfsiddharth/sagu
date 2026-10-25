# Handoff: Sagu (Track 3), picked up in a new session

## What this is
Sagu is a cactus that lives in iMessage group chats. It runs on the Mac of whoever installs it, using that person's own
Apple ID (Messages signed in on that Mac). It reads group messages from `~/Library/Messages/chat.db` (read-only),
sends with AppleScript into the group's chat guid, and every line starts with the cactus emoji.
It jumps in at random with a "remember when X said..." receipt, sometimes with kindness, and shares **food deals** and
rallies people ("in" replies, proposes a time, reminds 1h before). It replaced the earlier Discord/Freebie ideas on
the human's call: "let people plug their own apple ids", "food discounts so the agent gets people together", "very simple and quick".

## State (Oct 24)
- Python 3.9+, standard library only. Code in `sagu/`, tests in `tests/` (`python3 -m unittest discover -s tests -t .`).
- Modules: decode (attributedBody), imessage (reader/sender), store (sqlite), safety (hard lines), quotes (scoring),
  voice (line bank + optional Anthropic model, validated, falls back to bank), deals (typed deals, RSS/Atom), commands, bot, sim, `__main__` (run/demo/doctor/groups/reset).
- `python3 -m sagu demo` runs a labeled SIMULATION (made-up friends, throwaway DB, nothing sent).
- 62 tests; the last full run had one failing test (a wrong assertion about quote resting, since fixed). **Rerun the suite first.**

## Rules that must not regress (see CLAUDE.md)
- Silent and storing nothing in a chat until the host (is_from_me) texts `sagu on` there.
- Only people who text `sagu roast me` are ever quoted; Sagu never quotes someone with no name.
- Hard-line filter on everything stored and sent; model output validated, retried once, then curated bank.
- Never test by sending to real chats or printing real message content. Use `FakeMessages` fixtures.

## Left to do
1. Rerun tests; fix anything red.
2. `README.md` (what it is, architecture diagram, setup: Full Disk Access + Automation, `doctor`, `run`, `sagu on`, privacy and
   what leaves the Mac (nothing unless `llm` is on in `~/.config/sagu/config.json` and `ANTHROPIC_API_KEY` is set), known
   limitations, how it was tested). Include honestly: the AppleScript send path and the real chat.db reader have NOT been run
   against real group chats by the agent; decoder shape was checked by counts only.
3. `LICENSE` (MIT), `.gitignore`, `.github/workflows/test.yml` (Python 3.9 and 3.12).
4. Update `/docs/STATUS.md` in the parent folder (Track 3 section: replace the Discord plan with this).
5. Human only: create the public repo (`gh repo create sagu --public --source . --push`), run `python3 -m sagu doctor`, grant
   permissions, make a test group, `python3 -m sagu run --dry-run`, then `sagu on` in the test group; later submit Track 3.
6. Optional: tidy `__main__.py` (`cmd_run` builds DrySender twice), add a `--llm` smoke test with a fake transport.
