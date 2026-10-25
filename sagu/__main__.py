"""python3 -m sagu <run|demo|doctor|groups|reset>"""
from __future__ import annotations

import argparse
import os
import random
import shutil
import sys
import time

from . import __version__
from .bot import Config, Sagu
from .imessage import DEFAULT_DB, ME, DrySender, OsaSender, Reader, automation_status
from .store import Store, default_home
from .voice import llm_from_env


def _log(line: str) -> None:
    print(time.strftime("%H:%M:%S"), line, flush=True)


def cmd_doctor(args) -> int:
    ok = True
    print("Sagu %s" % __version__)
    try:
        reader = Reader(args.db)
        n = len(reader.groups())
        print("[ok] can read the Messages database (%d group chats)" % n)
    except Exception as exc:
        ok = False
        print("[!!] cannot read %s: %s" % (args.db, exc))
        print("     Fix: System Settings > Privacy & Security > Full Disk Access > add your terminal app, then reopen it.")
    good, why = automation_status()
    if good:
        print("[ok] can control Messages")
    else:
        ok = False
        print("[!!] cannot control Messages: %s" % why)
        print("     Fix: System Settings > Privacy & Security > Automation > allow your terminal to control Messages.")
    print("[%s] AI lines: %s" % ("ok", "on (ANTHROPIC_API_KEY found)" if os.environ.get("ANTHROPIC_API_KEY") and Config.load(default_home()).llm else "off (curated lines only; nothing leaves this Mac)"))
    print("Next: python3 -m sagu run   then text \"sagu on\" in any group chat." if ok else "Fix the items above, then run doctor again.")
    return 0 if ok else 1


def cmd_groups(args) -> int:
    for guid, name, count in Reader(args.db).groups()[:30]:
        print("%-40s %2d members   %s" % (name[:40], count, guid))
    return 0


def cmd_run(args) -> int:
    home = default_home()
    cfg = Config.load(home)
    store = Store(os.path.join(home, "sagu.db"))
    reader = Reader(args.db)
    if args.dry_run:
        class Printing(DrySender):
            def send(self, chat, text):
                print("DRY RUN ->", chat, "|", text, flush=True)
        sender = Printing()
    else:
        sender = OsaSender()
    llm = llm_from_env(cfg.llm)
    bot = Sagu(store, reader, sender, cfg, llm=llm, log=_log)
    _log("Sagu is listening%s. Text \"sagu on\" in a group chat. Ctrl-C to stop." % (" (dry run)" if args.dry_run else ""))
    try:
        while True:
            try:
                bot.tick()
            except Exception as exc:  # keep running through a bad message or a locked database
                _log("tick failed: %r" % exc)
            if args.once:
                return 0
            time.sleep(args.every)
    except KeyboardInterrupt:
        _log("bye")
        return 0


def cmd_demo(args) -> int:
    from .sim import ANA, BEN, CY, FakeMessages, GUID, build_history, script

    now = time.time()
    fake = FakeMessages()
    build_history(fake, now - 86400)
    store = Store(":memory:")
    sent = DrySender()
    clock = [now]
    cfg = Config(owner_name="Dev", quiet_start=0, quiet_end=0, prob=1.0, min_gap=20 * 60, min_quote_age=86400)
    who_is = {ME: "Dev (host)", ANA: "Ana", BEN: "Ben", CY: "Cy"}
    bot = Sagu(store, Reader(fake.path), sent, cfg, clock=lambda: clock[0], rng=random.Random(args.seed))
    store.set_cursor(Reader(fake.path).max_rowid())
    print("SIMULATION: made-up friends and made-up messages in a throwaway database. Nothing is sent anywhere.\n")
    for who, ts, text, why in script(now):
        clock[0] = ts
        fake.say(GUID, who, text, ts)
        before = len(sent.sent)
        bot.tick()
        print("%-10s %s" % (who_is[who], text))
        for _, line in sent.sent[before:]:
            print("  %s" % line.replace("\n", "\n  "))
        print("  [%s]\n" % why)
    return 0


def cmd_reset(args) -> int:
    home = default_home()
    if os.path.isdir(home) and input("Delete everything Sagu remembers (%s)? [y/N] " % home).strip().lower() == "y":
        shutil.rmtree(home)
        print("Deleted.")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="sagu", description="A cactus that lives in your iMessage group chats.")
    p.add_argument("--db", default=DEFAULT_DB, help="path to chat.db (default: this Mac's Messages)")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("doctor", help="check permissions").set_defaults(fn=cmd_doctor)
    sub.add_parser("groups", help="list your group chats").set_defaults(fn=cmd_groups)
    r = sub.add_parser("run", help="start listening")
    r.add_argument("--dry-run", action="store_true", help="print what Sagu would send instead of sending")
    r.add_argument("--once", action="store_true", help="one pass, then exit")
    r.add_argument("--every", type=float, default=5.0, help="seconds between checks")
    r.set_defaults(fn=cmd_run)
    d = sub.add_parser("demo", help="watch a made-up group chat (simulation)")
    d.add_argument("--seed", type=int, default=7)
    d.set_defaults(fn=cmd_demo)
    sub.add_parser("reset", help="delete everything Sagu remembers").set_defaults(fn=cmd_reset)
    args = p.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
