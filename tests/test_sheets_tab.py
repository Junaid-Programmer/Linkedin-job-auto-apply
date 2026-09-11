from jobagent.sheets import resolve_worksheet


class Spread:
    def __init__(self):
        self.sheet1 = "FIRST"

    def worksheet(self, title):
        return f"TAB:{title}"


def test_resolve_worksheet_named_and_default():
    s = Spread()
    assert resolve_worksheet(s, "") == "FIRST"
    assert resolve_worksheet(s, "Jobs") == "TAB:Jobs"
