from jobagent.prompts import run_options_from_answers

CONTROL_HEADERS = ["Keywords", "Location", "Applicants", "Posted", "Start", "Status"]


def is_start_truthy(value) -> bool:
    if value is True:
        return True
    text = str(value or "").strip().lower()
    return text in {"true", "yes", "y", "1", "checked", "on"}


def control_from_row(values) -> dict:
    cells = list(values or []) + [""] * 6
    return {
        "keywords": str(cells[0] or "").strip(),
        "location": str(cells[1] or "").strip(),
        "applicants": str(cells[2] or "").strip(),
        "posted": str(cells[3] or "").strip(),
        "start": is_start_truthy(cells[4]),
        "status": str(cells[5] or "").strip(),
    }


def options_from_control(control: dict) -> dict:
    return run_options_from_answers(
        {
            "keywords": (control or {}).get("keywords"),
            "location": (control or {}).get("location"),
            "applicants": (control or {}).get("applicants"),
            "posted": (control or {}).get("posted"),
        }
    )
