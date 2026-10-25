# CLAUDE.md

You are working on **Prod**, a pushy, funny accountability coach (mascot: **Sagu**, a small cactus), built at the
Cubbie Hackathon (DevHacks 2026). This file is your standing brief. Read it fully at the start of every session,
then read `docs/STATUS.md` to see where things stand.

## The product in one line
A coach that remembers every excuse you've made, quotes it back ("receipts"), and learns which kind of push
actually gets you moving. Persona "coaches" (Drill Sergeant, Mob Boss, Disappointed Dad...) set the voice.

## What we're building (in priority order)

| # | Deliverable | Where | Judged on | Deadline |
|---|---|---|---|---|
| 1 | **Track 1: `prod-coach` Cubbie Skill** (personal coach in iMessage via Cubbie) | `prod-coach/` (its own public repo) | 70% engineering quality, 15% public votes, 15% social views | **First 10 hours of the event. Hard gate.** |
| 2 | **Track 3: Sagu group-chat bot** (Discord) | `prod-squad/` (its own public repo) | Technical + use case, judges privately | General window |
| 3 | **Track 2: Squad Sync** (agents negotiate a joint session) | `prod-squad/` (same codebase, `sync` module) | Technical + use case, judges privately | General window |
| 4 | Landing page | `prod-squad/` Next.js app, `/` route | Supports 2 and 3 | — |

Not this weekend: the iOS app (`docs/later/ios-app-spec.md`). Do not start it.

**Rule:** do not work on Tracks 2/3 until Track 1 is submitted, unless a human explicitly assigns you to it in
parallel.

## Docs (read the one for your task before writing code)
- `docs/00-hackathon.md`: rules, scoring, what's allowed, open questions for organizers.
- `docs/01-branding.md`: Sagu, colors, type, voice, **hard lines**. Read the "Hackathon scope" box first.
- `docs/02-track1-skill.md`: Track 1 spec, including the `scripts/log.py` spec and test checklist.
- `docs/03-track3-group-bot.md`: Discord bot spec.
- `docs/04-track2-squad-sync.md`: negotiation protocol spec.
- `docs/05-architecture.md`: infra, schema, env vars, deploy.
- `docs/06-plan-and-risks.md`: timeline, owners, risks, VERIFY list.
- `docs/STATUS.md`: live checklist. **Update it at the end of every task** (what's done, what's next, blockers).

## Use the official Cubbie Hackathon Kit
The kit is the source of truth for Cubbie rules and tooling:
```bash
git clone https://github.com/imaginix-inc/cubbie-hackathon-kit.git ../cubbie-hackathon-kit
```
- Read `skills/cubbie-hackathon/SKILL.md` and `skills/cubbie-skill-creator/SKILL.md` and their `references/`.
- Or ask the human to install them as plugins:
  `/plugin marketplace add imaginix-inc/cubbie-hackathon-kit`, then
  `/plugin install cubbie-hackathon@cubbie-hackathon-kit`.
- Live windows: `python3 scripts/hackathon.py status` (from `skills/cubbie-hackathon/`). Never guess dates.
- Validate the Skill after **every** change:
  `python3 ../cubbie-hackathon-kit/skills/cubbie-skill-creator/scripts/validate_cubbie_skill.py prod-coach`
- Install links: `python3 ../cubbie-hackathon-kit/skills/cubbie-skill-creator/scripts/github_link.py prod-coach`

If the kit and our docs disagree, **the kit and hackathon.cubbie.ai win**. Update our docs and note it in STATUS.

## Non-negotiable rules
1. **Ask the human before:** creating a GitHub repo, changing repo visibility, pushing, submitting or editing a
   hackathon entry, posting anything public, spending money, or installing anything outside this workspace.
   Hackathon entries are public the moment they're sent.
2. **Secrets:** never commit keys or tokens. Use `.env.local` (gitignored) and Vercel env vars. Never ask the human
   to paste secrets into chat; tell them where to put them.
3. **Cubbie Skill rules:** plain words for Cubbie abilities (never Cubbie tool names, parameters or JSON in
   `SKILL.md`); scripts can't call Cubbie abilities (Cubbie passes data in as arguments); Cubbie texts only its own
   student; the student's yes is required before acting for them; replies are short plain-text iMessages.
4. **Hard lines for every generated line, every persona, every intensity** (`docs/01-branding.md` §5.3): never
   mock body, weight, appearance, eating, race, religion, gender, sexuality, disability, mental health, family or
   money. No slurs, threats or sexual content. Roast the excuse, never the person. Eating/weight/body/mental-health
   goals use the supportive coach only. Enforce this in code (filter before posting), not just in prompts.
5. **No real people as personas.** Archetypes only.
6. **Consent:** public callouts that quote a member need that member's opt-in. Agents never share another
   student's private reasons, only availability.
7. **Honesty:** never fake a working feature in a demo. Seeded demo data is fine if labeled; fabricated results are not.
8. **Fresh code:** everything is written during the event in these repos. Commit early and often.

## Engineering standards
- **Track 1 script:** Python 3.9+, **standard library only**, `--sample` mode, state under `HOME`, short output
  (<8,000 chars), documented exit codes, `unittest` tests.
- **prod-squad:** TypeScript strict, Next.js App Router on Vercel, `zod` for every external input and LLM output,
  `vitest` for core logic (push picker, hard-line filter, negotiation solver). Keep LLM calls behind one
  `lib/llm.ts` interface so the provider can be swapped.
- Every LLM output is validated; on failure retry once, then fall back to the curated line bank. The bot never
  goes silent and never posts unfiltered model text.
- Small, reviewable commits. A README in each repo with: what it is, architecture diagram, how to run, how it was
  tested, and known limitations.

## Definition of done
- **Track 1:** validator OK with no warnings; `log.py` tests pass; Skill installs on a real Cubbie from the branch
  link; the checklist in `docs/02-track1-skill.md` passes on a real account; README has test evidence; entry
  submitted by the human with the repo link (video post optional, can be added later).
- **Track 3:** deployed on Vercel, installed in a real Discord server; goal setup → scheduled check-in → excuse →
  filtered persona reply with receipts → leaderboard all work end to end; tests pass; README + diagram.
- **Track 2:** `/sync` runs a real negotiation between at least 3 members' agents, shows the protocol in a thread,
  handles a no-overlap case, collects every confirmation, posts the plan with `.ics` files; tests pass.

## When unsure
Prefer the smaller, working version. Write the question into `docs/STATUS.md` under "Questions for humans" and
continue with the safest assumption.
