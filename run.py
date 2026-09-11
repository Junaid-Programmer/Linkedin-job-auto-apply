#!/usr/bin/env python3
"""CLI for the LinkedIn job agent.

Commands:
  python run.py login
  python run.py run   [--keywords ...] [--location ...] [--pages N] [--posted 24h]
  python run.py scrape [--keywords ...] [--location ...] [--pages N] [--posted 24h]
  python run.py watch
  python run.py score
  python run.py enforce   (re-check scored rows against rules.yaml)
  python run.py tailor
"""

from __future__ import annotations

import argparse
import getpass
import sys
import time

from jobagent.config import Config, ConfigError
from jobagent.linkedin import LinkedInSession, login_credentials, login_interactive
from jobagent.pipeline import JobAgent
from jobagent.prompts import resolve_run_options
from jobagent.sheets import JobSheet
from jobagent.watch import watch_loop


def check_setup(config: Config) -> None:
    """Report what is ready and what still needs the user's action."""
    from pathlib import Path

    print("== setup check ==")

    # 1. LLM
    if config.llm_api_key and config.llm_api_key != "your-api-key-here":
        print(f"[ok]   LLM configured ({config.llm_model})")
    else:
        print("[MISS] LLM: set USER_LLM_API_KEY in .env to your own API key")

    # 2. Google Sheets
    if Path(config.google_service_account_file).exists():
        print(f"[ok]   Google service account at {config.google_service_account_file}")
    else:
        print(
            f"[MISS] Google: put your service-account JSON at "
            f"{config.google_service_account_file} (see README)"
        )

    # 3. Profile / resume
    for name in ("profile.md", "resume.md"):
        if Path(name).exists():
            print(f"[ok]   {name} found")
        else:
            print(f"[MISS] {name} missing - create it from profile.md.example / resume.md.example")

    # 4. LinkedIn session
    session = LinkedInSession(config.state_file, headless=True)
    try:
        session.start()
        if session.logged_in:
            print("[ok]   LinkedIn session logged in")
        else:
            print("[MISS] LinkedIn: run `python run.py login` first")
    except RuntimeError as exc:
        print(f"[MISS] LinkedIn: {exc}")
    finally:
        session.close()

    print("== done ==")


def main() -> None:
    parser = argparse.ArgumentParser(prog="job-agent", description=__doc__)
    sub = parser.add_subparsers(dest="command")

    login = sub.add_parser("login", help="Log in to LinkedIn and save your session")
    login.add_argument(
        "--manual",
        action="store_true",
        help="Open a visible browser for you to log in by hand (use on a machine with a display)",
    )
    sub.add_parser("check", help="Verify the setup is ready to run")

    run = sub.add_parser("run", help="Scrape -> sheet -> score -> tailor/skip")
    scrape = sub.add_parser("scrape", help="Scrape jobs only")
    for p in (run, scrape):
        p.add_argument("--keywords", help="Search keywords")
        p.add_argument("--location", help="Search location")
        p.add_argument("--pages", type=int, help="Number of result pages")
        p.add_argument(
            "--posted",
            dest="time_filter",
            help="Posted window: 2h, 5h, 7h, 24h, 2day, 7day, or all",
        )
        p.add_argument(
            "--applicants",
            help="Applicant max or min-max (e.g. 50 or 10-50). Blank = all",
        )
    sub.add_parser("watch", help="Watch the Control tab and scrape when Start is ticked")
    sub.add_parser("score", help="Score unscored jobs in the sheet")
    sub.add_parser(
        "enforce",
        help="Re-check already-scored jobs against rules.yaml and skip any that now fail",
    )
    sub.add_parser("tailor", help="Prepare application packages for targets")

    args = parser.parse_args()
    if not args.command:
        args.command = "run"
        args.keywords = None
        args.location = None
        args.pages = None
        args.time_filter = None
        args.applicants = None
    config = Config.from_env()

    if args.command == "login":
        if args.manual:
            try:
                login_interactive(config.state_file)
            except RuntimeError as exc:
                print(f"error: {exc}", file=sys.stderr)
                sys.exit(1)
            return
        email = input("LinkedIn email: ").strip()
        password = getpass.getpass("LinkedIn password: ")
        try:
            login_credentials(config.state_file, email, password)
        except RuntimeError as exc:
            print(f"error: {exc}", file=sys.stderr)
            sys.exit(1)
        return

    if args.command == "check":
        check_setup(config)
        return

    agent = JobAgent(config)
    try:
        if args.command in ("run", "scrape"):
            options = resolve_run_options(args)
            agent.run_options = options
            args.keywords = options["keywords"]
            args.location = options["location"]
            args.time_filter = options["posted_within"]
        if args.command == "run":
            agent.run(
                keywords=args.keywords,
                location=args.location,
                pages=args.pages,
                time_filter=args.time_filter,
            )
        elif args.command == "scrape":
            agent.scrape(
                keywords=args.keywords,
                location=args.location,
                pages=args.pages,
                time_filter=args.time_filter,
            )
        elif args.command == "watch":
            config.require_sheets()
            sheet = JobSheet(
                config.google_service_account_file,
                config.google_sheet_name,
                config.google_sheet_id,
            )
            print("Watching Control tab. Fill Keywords + Location, then tick Start.")
            watch_loop(sheet, agent, sleep_fn=time.sleep)
        elif args.command == "score":
            agent.score_pending()
        elif args.command == "enforce":
            agent.enforce_rules()
        elif args.command == "tailor":
            agent.tailor_targets()
    except ConfigError as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
