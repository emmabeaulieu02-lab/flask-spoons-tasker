"""Load the client's fixed weekly routine into a calendar as locked, weekly tasks.

From the client's email of 9 November 2026. Run from the project folder:

    python -m flask_calendar.scripts.load_client_routine sample

Running it again does not add duplicates: a weekly task with the same title,
day and start time is skipped.
"""
import sys
from typing import List, Tuple

from flask_calendar.app import create_app
from flask_calendar.calendar_data import CalendarData

GREEN, YELLOW, RED = "#3EB34F", "#F2C81A", "#FF4848"
MON, TUE, WED, THU, FRI, SAT, SUN = range(7)  # same numbering as the app's weekly repeats

# (title, colour, weekday, start, end, locked)
ROUTINE: List[Tuple[str, str, int, str, str, bool]] = [
    ("Church and fellowship", YELLOW, SUN, "10:30", "12:00", True),
    ("Walk and small groceries", GREEN, SUN, "14:00", "15:30", True),
    ("Walk and small groceries", GREEN, MON, "10:00", "11:30", True),
    ("Walk and small groceries", GREEN, TUE, "10:00", "11:30", True),
    ("Music lesson", YELLOW, TUE, "18:00", "18:30", True),
    ("Exercise class", YELLOW, WED, "11:30", "12:30", True),
    ("Walk and small groceries", GREEN, WED, "14:00", "15:30", True),
    ("Medical appointment", YELLOW, THU, "09:30", "11:30", True),
    ("Medical appointment", YELLOW, THU, "12:30", "14:30", True),
    ("Walk and small groceries", GREEN, THU, "14:30", "16:00", True),
    ("Physiotherapy", YELLOW, FRI, "10:00", "12:00", True),
    ("Walk and small groceries", GREEN, FRI, "14:00", "15:30", True),
    ("Walk and small groceries", GREEN, SAT, "10:00", "11:30", True),
    ("Change bed and towels", RED, SAT, "14:00", "15:00", True),
    ("Rest", GREEN, SAT, "15:00", "16:00", False),
]


def main(calendar_id: str) -> None:
    app = create_app()
    with app.app_context():
        calendar_data = CalendarData(app.config["DATA_FOLDER"], app.config["WEEK_STARTING_DAY"])
        existing = {
            (task.get("title"), str(task.get("repetition_value")), task.get("start_time"))
            for task in calendar_data.load_calendar(calendar_id)["tasks"]["repetition"]
        }
        added = 0
        for title, color, weekday, start, end, locked in ROUTINE:
            if (title, str(weekday), start) in existing:
                continue
            calendar_data.create_task(
                calendar_id, None, None, None, title, False, start, "", color,
                True, "w", "w", weekday, end, locked,
            )
            added += 1
        print("Added {} weekly tasks to '{}' ({} already there).".format(added, calendar_id, len(ROUTINE) - added))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "sample")
