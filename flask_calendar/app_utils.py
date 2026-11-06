import re
import uuid
from functools import wraps
from datetime import date, datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Tuple

from cachelib.simple import SimpleCache
from flask import abort, current_app, redirect, request
from flask_calendar.authorization import Authorization
from flask_calendar.calendar_data import CalendarData
from flask_calendar.constants import SESSION_ID
from flask_calendar.gregorian_calendar import GregorianCalendar

cache = SimpleCache()

# see `app_utils` tests for details, but TL;DR is that urls must start with `http://` or `https://` to match
URLS_REGEX_PATTERN = r"(https?\:\/\/[\w/\-?=%.]+\.[\w/\+\-?=%.~&\[\]\#]+)"
DECORATED_URL_FORMAT = '<a href="{}" target="_blank">{}</a>'


def authenticated(decorated_function: Callable) -> Any:
    @wraps(decorated_function)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        session_id = request.cookies.get(SESSION_ID)
        if session_id is None or not is_session_valid(str(session_id)):
            if request.headers.get("Content-Type", "") == "application/json":
                abort(401)
            return redirect("/login")
        return decorated_function(*args, **kwargs)

    return wrapper


def authorized(decorated_function: Callable) -> Any:
    @wraps(decorated_function)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        username = get_session_username(str(request.cookies.get(SESSION_ID)))
        authorization = Authorization(calendar_data=CalendarData(data_folder=current_app.config["DATA_FOLDER"]))
        if "calendar_id" not in kwargs:
            raise ValueError("calendar_id")
        calendar_id = str(kwargs["calendar_id"])
        if not authorization.can_access(username=username, calendar_id=calendar_id):
            abort(403)
        return decorated_function(*args, **kwargs)

    return wrapper


def previous_month_link(year: int, month: int) -> str:
    month, year = GregorianCalendar.previous_month_and_year(year=year, month=month)
    return (
        ""
        if year < current_app.config["MIN_YEAR"] or year > current_app.config["MAX_YEAR"]
        else "?y={}&m={}".format(year, month)
    )


def next_month_link(year: int, month: int) -> str:
    month, year = GregorianCalendar.next_month_and_year(year=year, month=month)
    return (
        ""
        if year < current_app.config["MIN_YEAR"] or year > current_app.config["MAX_YEAR"]
        else "?y={}&m={}".format(year, month)
    )


def new_session_id() -> str:
    return str(uuid.uuid4())


def is_session_valid(session_id: str) -> bool:
    return cache.get(session_id) is not None


def add_session(session_id: str, username: str) -> None:
    cache.set(session_id, username, timeout=2678400)  # 1 month


def get_session_username(session_id: str) -> str:
    return str(cache.get(session_id))


def task_details_for_markup(details: str) -> str:
    if not current_app.config["AUTO_DECORATE_TASK_DETAILS_HYPERLINK"]:
        return details

    decorated_fragments = []

    fragments = re.split(URLS_REGEX_PATTERN, details)
    for index, fragment in enumerate(fragments):
        if index % 2 == 1:
            decorated_fragments.append(DECORATED_URL_FORMAT.format(fragment, fragment))
        else:
            decorated_fragments.append(fragment)

    return "".join(decorated_fragments)

def parse_iso_date(value: Optional[str], default: date) -> date:
    """Parse YYYY-MM-DD, returning the supplied default when invalid."""
    if value is None:
        return default

    try:
        return date.fromisoformat(value)
    except ValueError:
        return default


def start_of_week(value: date, first_weekday: int) -> date:
    """Return the first date of the week containing value."""
    days_since_week_start = (value.weekday() - first_weekday) % 7
    return value - timedelta(days=days_since_week_start)


def time_to_minutes(value: str) -> int:
    """Convert an HH:MM value to minutes after midnight."""
    try:
        parsed_time = datetime.strptime(value, "%H:%M").time()
    except (TypeError, ValueError):
        return 0

    return parsed_time.hour * 60 + parsed_time.minute


def prepare_week_task(
    task: Dict,
    start_hour: int,
    end_hour: int,
    hour_height: int,
    minimum_task_minutes: int,
) -> Optional[Dict]:
    """
    Add pixel positioning information to a timed task.

    Tasks completely outside the visible range are omitted.
    """
    if task.get("is_all_day", False):
        return dict(task)

    visible_start = start_hour * 60
    visible_end = end_hour * 60

    task_start = time_to_minutes(task.get("start_time", "00:00"))
    task_end = time_to_minutes(
        task.get("end_time") or task.get("start_time", "00:00")
    )

    # Treat an end time before the start as passing midnight.
    if task_end < task_start:
        task_end = 24 * 60

    if task_end == task_start:
        task_end += minimum_task_minutes

    clipped_start = max(task_start, visible_start)
    clipped_end = min(task_end, visible_end)

    if clipped_end <= clipped_start:
        return None

    pixels_per_minute = hour_height / 60
    prepared_task = dict(task)
    prepared_task["top"] = (
        clipped_start - visible_start
    ) * pixels_per_minute
    prepared_task["height"] = max(
        (clipped_end - clipped_start) * pixels_per_minute,
        20,
    )

    return prepared_task


def prepare_week_days(
    week_start: date,
    tasks: Dict[str, List[Dict]],
    start_hour: int,
    end_hour: int,
    hour_height: int,
    minimum_task_minutes: int,
) -> List[Dict]:
    """Build the seven day-column objects used by the weekly template."""
    days: List[Dict] = []

    for offset in range(7):
        day_date = week_start + timedelta(days=offset)
        day_tasks = tasks.get(day_date.isoformat(), [])

        all_day_tasks = [
            dict(task)
            for task in day_tasks
            if task.get("is_all_day", False)
        ]

        timed_tasks = []
        for task in day_tasks:
            if task.get("is_all_day", False):
                continue

            prepared_task = prepare_week_task(
                task=task,
                start_hour=start_hour,
                end_hour=end_hour,
                hour_height=hour_height,
                minimum_task_minutes=minimum_task_minutes,
            )

            if prepared_task is not None:
                timed_tasks.append(prepared_task)

        timed_tasks.sort(
            key=lambda task: time_to_minutes(
                task.get("start_time", "00:00")
            )
        )

        days.append(
            {
                "date": day_date,
                "date_key": day_date.isoformat(),
                "all_day_tasks": all_day_tasks,
                "timed_tasks": timed_tasks,
            }
        )

    return days


# ---------- Energy balance ----------

RED_TIME_WINDOWS = {
    "morning": (0, 12 * 60, "morning"),
    "afternoon": (12 * 60, 17 * 60, "afternoon"),
    "evening": (17 * 60, 24 * 60, "evening"),
}


def format_points(value: float) -> str:
    """4.5 -> '4.5', 6.0 -> '6'"""
    return "{:g}".format(round(value, 1))


def day_energy_check(
    day_tasks: List[Dict],
    previous_day_tasks: List[Dict],
    settings: Dict,
    energy_levels: Dict,
    energy_points: Dict,
) -> Dict:
    """
    Adds up a day's energy points and lists plain-language warnings:
    too many red tasks, a high energy day (over the point limit),
    and red tasks on two days in a row (if that setting is on).
    The preferred time of day is not a warning: the suggestions use it instead.
    """

    def level_of(task: Dict) -> str:
        return energy_levels.get((task.get("color") or "").lower(), ("", ""))[0]

    points = sum(energy_points.get(level_of(task), 0) for task in day_tasks)
    red_tasks = [task for task in day_tasks if level_of(task) == "high"]
    limit = float(settings["daily_limit"])
    max_red = int(settings["max_red"])

    warnings = []
    if len(red_tasks) > max_red:
        warnings.append("{} red tasks today (limit {})".format(len(red_tasks), max_red))
    if points > limit:
        warnings.append("High energy day")

    if settings.get("rest_after_red_day") and red_tasks:
        if any(level_of(task) == "high" for task in previous_day_tasks):
            warnings.append("Red tasks 2 days in a row")

    return {
        "points": points,
        "points_text": format_points(points),
        "limit_text": format_points(limit),
        "over": points > limit,
        "warnings": warnings,
    }


# ---------- Learning her preferences ----------

LEVEL_WORDS = {"low": "green", "medium": "yellow", "high": "red"}
WEEKDAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def part_of_day(minutes: int) -> str:
    if minutes < 12 * 60:
        return "morning"
    if minutes < 17 * 60:
        return "afternoon"
    return "evening"


def record_placement(learned: Dict, level: str, day: date, start_minutes: int) -> None:
    """Remembers the hour and weekday she chose for a task of this energy level."""
    if level not in LEVEL_WORDS:
        return
    entry = learned.setdefault(level, {"hours": {}, "weekdays": {}})
    hour = str(start_minutes // 60)
    weekday = str(day.weekday())
    entry["hours"][hour] = entry["hours"].get(hour, 0) + 1
    entry["weekdays"][weekday] = entry["weekdays"].get(weekday, 0) + 1


def learned_summary(learned: Dict) -> List[str]:
    """Plain sentences about what has been learned, for the Settings page."""
    sentences = []
    for level, word in LEVEL_WORDS.items():
        hours = learned.get(level, {}).get("hours", {})
        total = sum(hours.values())
        if total == 0:
            continue
        parts = {"morning": 0, "afternoon": 0, "evening": 0}
        for hour, count in hours.items():
            parts[part_of_day(int(hour) * 60)] += count
        favourite = max(parts, key=lambda name: parts[name])
        if total < 3 or parts[favourite] / total < 0.6:
            sentences.append("No clear pattern yet for {} tasks ({} so far).".format(word, total))
        else:
            sentences.append(
                "You usually put {} tasks in the {} ({} of {} times).".format(word, favourite, parts[favourite], total)
            )
    return sentences


def hour_preference(learned: Dict, level: str, hour: int, settings: Dict) -> float:
    """How well an hour suits this kind of task for her: higher is better."""
    score = 0.0
    hours = learned.get(level, {}).get("hours", {})
    total = sum(hours.values())
    if total:
        exact = hours.get(str(hour), 0)
        near = sum(count for other, count in hours.items() if abs(int(other) - hour) <= 1)
        score += 2.0 * exact / total + 1.0 * near / total
    if level == "high":
        window = RED_TIME_WINDOWS.get(settings.get("red_time", "any"))
        if window is not None and window[0] <= hour * 60 < window[1]:
            score += 1.5
    return score


def weekday_preference(learned: Dict, level: str, weekday: int) -> float:
    days = learned.get(level, {}).get("weekdays", {})
    total = sum(days.values())
    return days.get(str(weekday), 0) / total if total else 0.0


# ---------- Suggesting a balanced week ----------

def suggest_week(
    week_dates: List[date],
    tasks_by_date: Dict[str, List[Dict]],
    previous_day_tasks: List[Dict],
    settings: Dict,
    energy_levels: Dict,
    energy_points: Dict,
    learned: Dict,
    today: date,
) -> Dict:
    """
    Suggests where to put this week's movable tasks so that each day stays balanced.

    Locked tasks, weekly repeating tasks, all-day tasks and tasks on past days stay where they are.
    Red tasks are placed first (they are the hardest to fit), then yellow, then green.
    Each task goes to the day and time with the lowest "cost": going over the point limit or the
    red-task limit costs a lot, red tasks on days next to each other cost some (if that setting is on),
    busy days cost a little, and hours/days she usually chooses for that kind of task lower the cost.
    A task is only moved if the new spot is clearly better than where it already is.
    """

    def level_of(task: Dict) -> str:
        return energy_levels.get((task.get("color") or "").lower(), ("", ""))[0]

    def span(task: Dict) -> Tuple[int, int]:
        start = time_to_minutes(task.get("start_time", "00:00"))
        end = time_to_minutes(task.get("end_time") or task.get("start_time", "00:00"))
        if end <= start:
            end = start + 15
        return start, end

    day_start = int(settings["day_start"]) * 60
    day_end = int(settings["day_end"]) * 60
    limit = float(settings["daily_limit"])
    max_red = int(settings["max_red"])
    rest_after_red = bool(settings.get("rest_after_red_day"))
    keys = [day.isoformat() for day in week_dates]

    placed = {key: [] for key in keys}  # type: Dict[str, List[Dict]]
    movable = []
    for day in week_dates:
        key = day.isoformat()
        for task in tasks_by_date.get(key, []):
            level = level_of(task)
            can_move = (
                level != ""
                and not task.get("locked", False)
                and "repetition_type" not in task
                and not task.get("is_all_day", False)
                and day >= today
            )
            if can_move:
                movable.append((day, task, level))
            else:
                placed[key].append(task)

    def day_points(key: str) -> float:
        return sum(energy_points.get(level_of(task), 0) for task in placed[key])

    def day_reds(key: str) -> int:
        return sum(1 for task in placed[key] if level_of(task) == "high")

    def has_red(index: int) -> bool:
        if index < 0:
            return any(level_of(task) == "high" for task in previous_day_tasks)
        if index >= len(keys):
            return False
        return day_reds(keys[index]) > 0

    def is_free(key: str, start: int, end: int) -> bool:
        for task in placed[key]:
            if task.get("is_all_day", False):
                continue
            other_start, other_end = span(task)
            if start < other_end and other_start < end:
                return False
        return True

    def cost(index: int, start: int, level: str, original: Tuple[date, int]) -> float:
        key = keys[index]
        new_points = day_points(key) + energy_points.get(level, 0)
        new_reds = day_reds(key) + (1 if level == "high" else 0)
        value = 0.0
        if new_points > limit:
            value += 5 + 10 * (new_points - limit)
        if new_reds > max_red:
            value += 12
        if rest_after_red and level == "high" and (has_red(index - 1) or has_red(index + 1)):
            value += 6
        value += 0.4 * new_points
        value -= weekday_preference(learned, level, week_dates[index].weekday())
        value -= 1.5 * hour_preference(learned, level, start // 60, settings)
        if week_dates[index] != original[0]:
            value += 1.5
        value += 0.002 * abs(start - original[1])
        if start % 60:
            value += 0.1  # gently prefer starting on the hour
        return value

    order = {"high": 0, "medium": 1, "low": 2}
    movable.sort(key=lambda item: (order[item[2]], item[0], span(item[1])[0]))

    moves = []
    for day, task, level in movable:
        start, end = span(task)
        length = end - start
        original = (day, start)
        original_index = keys.index(day.isoformat())

        best = None  # type: Optional[Tuple[float, int, int]]
        baseline = None  # type: Optional[float]
        if is_free(keys[original_index], start, end):
            baseline = cost(original_index, start, level, original)

        for index, candidate_day in enumerate(week_dates):
            if candidate_day < today:
                continue
            for candidate_start in range(day_start, day_end - length + 1, 30):
                if not is_free(keys[index], candidate_start, candidate_start + length):
                    continue
                value = cost(index, candidate_start, level, original)
                if best is None or value < best[0]:
                    best = (value, index, candidate_start)

        target_index, target_start = original_index, start
        if best is not None and (baseline is None or baseline - best[0] >= 1.0):
            target_index, target_start = best[1], best[2]

        moved = dict(task)
        moved["start_time"] = "{:02d}:{:02d}".format(target_start // 60, target_start % 60)
        moved["end_time"] = "{:02d}:{:02d}".format((target_start + length) // 60, (target_start + length) % 60)
        placed[keys[target_index]].append(moved)

        if (target_index, target_start) != (original_index, start):
            moves.append(
                {
                    "task_id": task["id"],
                    "title": task.get("title", ""),
                    "level": level,
                    "from_date": day.isoformat(),
                    "from_day": WEEKDAY_NAMES[day.weekday()],
                    "from_start": task.get("start_time", ""),
                    "to_date": keys[target_index],
                    "to_day": WEEKDAY_NAMES[week_dates[target_index].weekday()],
                    "to_start": moved["start_time"],
                    "to_end": moved["end_time"],
                    "to_start_minutes": target_start,
                    "length": length,
                    "changed_day": target_index != original_index,
                    "part_of_day": part_of_day(target_start),
                }
            )

    def warning_count(tasks_for_days: Dict[str, List[Dict]]) -> int:
        count = 0
        previous = previous_day_tasks
        for key in keys:
            count += len(day_energy_check(tasks_for_days[key], previous, settings, energy_levels, energy_points)["warnings"])
            previous = tasks_for_days[key]
        return count

    before = warning_count({key: tasks_by_date.get(key, []) for key in keys})
    after = warning_count(placed)

    # A short reason for each suggested move
    original_warnings = {}
    previous = previous_day_tasks
    for key in keys:
        original_warnings[key] = day_energy_check(
            tasks_by_date.get(key, []), previous, settings, energy_levels, energy_points
        )["warnings"]
        previous = tasks_by_date.get(key, [])
    for move in moves:
        reasons = []
        if move["changed_day"]:
            if original_warnings[move["from_date"]]:
                reasons.append("to balance {}".format(move["from_day"]))
            else:
                reasons.append("to spread your energy across the week")
        if hour_preference(learned, move["level"], move["to_start_minutes"] // 60, settings) > 0:
            if sum(learned.get(move["level"], {}).get("hours", {}).values()) > 0:
                reasons.append(
                    "in the {}, when you usually do {} tasks".format(move["part_of_day"], LEVEL_WORDS[move["level"]])
                )
            else:
                reasons.append("in the {}, your best time for red tasks".format(move["part_of_day"]))
        move["reason"] = " and ".join(reasons) if reasons else "to fit the week better"

    return {"moves": moves, "warnings_before": before, "warnings_after": after}
