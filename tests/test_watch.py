from jobagent.watch import POLL_SECONDS, handle_control_poll, watch_loop


class FakeSheet:
    def __init__(self, control):
        self.control = dict(control)
        self.writes = []

    def read_control(self):
        return dict(self.control)

    def write_control(self, start=None, status=None):
        if start is not None:
            self.control["start"] = start
        if status is not None:
            self.control["status"] = status
        self.writes.append({"start": start, "status": status})


class FakeAgent:
    run_options = None


def test_poll_idle_when_start_false():
    sheet = FakeSheet({"start": False, "keywords": "python", "location": "Europe", "applicants": "", "posted": ""})
    assert handle_control_poll(sheet, FakeAgent(), scrape_fn=lambda: (0, 0)) == "idle"
    assert sheet.writes == []


def test_poll_invalid_clears_start():
    sheet = FakeSheet({"start": True, "keywords": "", "location": "", "applicants": "", "posted": ""})
    assert handle_control_poll(sheet, FakeAgent(), scrape_fn=lambda: (1, 1)) == "invalid"
    assert sheet.control["start"] is False
    assert "error" in sheet.control["status"]


def test_poll_starts_scrape_and_writes_done():
    sheet = FakeSheet({"start": True, "keywords": "python", "location": "Europe", "applicants": "", "posted": "24h"})
    agent = FakeAgent()
    called = {}

    def scrape():
        called["options"] = dict(agent.run_options)
        return (3, 2)

    assert handle_control_poll(sheet, agent, scrape_fn=scrape) == "done"
    assert called["options"]["work_style"] == "remote"
    assert called["options"]["posted_within"] == "24h"
    assert sheet.control["start"] is False
    assert "done" in sheet.control["status"]
    assert sheet.writes[0]["start"] is False
    assert sheet.writes[0]["status"] == "running"


def test_poll_scrape_error_writes_status():
    sheet = FakeSheet({"start": True, "keywords": "python", "location": "Europe", "applicants": "", "posted": ""})

    def scrape():
        raise RuntimeError("Not logged in to LinkedIn. Run `python run.py login` once")

    assert handle_control_poll(sheet, FakeAgent(), scrape_fn=scrape) == "error"
    assert "login" in sheet.control["status"].lower() or "error" in sheet.control["status"].lower()


def test_watch_loop_polls_then_sleeps():
    sheet = FakeSheet({"start": False, "keywords": "python", "location": "Europe", "applicants": "", "posted": ""})
    sleeps = []
    ticks = {"n": 0}

    def should_continue():
        ticks["n"] += 1
        return ticks["n"] <= 2

    watch_loop(sheet, FakeAgent(), sleep_fn=lambda s: sleeps.append(s), should_continue=should_continue)
    assert sleeps == [POLL_SECONDS, POLL_SECONDS]
    assert POLL_SECONDS == 10
