from jobagent.control import options_from_control

POLL_SECONDS = 10


def watch_loop(sheet, agent, sleep_fn, scrape_fn=None, should_continue=lambda: True) -> None:
    while should_continue():
        handle_control_poll(sheet, agent, scrape_fn=scrape_fn)
        sleep_fn(POLL_SECONDS)


def handle_control_poll(sheet, agent, scrape_fn=None) -> str:
    control = sheet.read_control()
    if not control["start"]:
        return "idle"
    try:
        options = options_from_control(control)
    except ValueError:
        sheet.write_control(start=False, status="error: keywords and location are required")
        return "invalid"
    sheet.write_control(start=False, status="running")
    agent.run_options = options
    try:
        if scrape_fn is not None:
            found, added = scrape_fn()
        else:
            found, added = agent.scrape_to_sheet()
        sheet.write_control(status=f"done: found {found}, added {added}")
        return "done"
    except Exception as exc:
        sheet.write_control(status=f"error: {exc}")
        return "error"
