import json
import re
from datetime import date, timedelta
from typing import List, Optional, Tuple, cast  # noqa: F401

from flask import abort, current_app, g, jsonify, make_response, redirect, render_template, request
from werkzeug.wrappers import Response

import flask_calendar.constants as constants
from flask_calendar.app_utils import (
    add_session,
    authenticated,
    authorized,
    get_session_username,
    new_session_id,
    next_month_link,
    previous_month_link,
    parse_iso_date,
    day_energy_check,
    learned_summary,
    prepare_week_days,
    record_placement,
    suggest_week,
    time_to_minutes,
    start_of_week,
)
from flask_calendar.authentication import Authentication
from flask_calendar.calendar_data import CalendarData
from flask_calendar.gregorian_calendar import GregorianCalendar


def get_authentication() -> Authentication:
    auth = getattr(g, "_auth", None)
    if auth is None:
        auth = g._auth = Authentication(
            data_folder=current_app.config["USERS_DATA_FOLDER"],
            password_salt=current_app.config["PASSWORD_SALT"],
            failed_login_delay_base=current_app.config["FAILED_LOGIN_DELAY_BASE"],
        )
    return cast(Authentication, auth)


@authenticated
def index_action() -> Response:
    username = get_session_username(session_id=str(request.cookies.get(constants.SESSION_ID)))
    authentication = get_authentication()
    user_data = authentication.user_data(username)
    return redirect("/{}/".format(user_data["default_calendar"]))


def login_action() -> Response:
    return cast(Response, render_template("login.html"))


def do_login_action() -> Response:
    username = request.form.get("username", "")
    password = request.form.get("password", "")
    authentication = get_authentication()

    if authentication.is_valid(username, password):
        session_id = new_session_id()
        add_session(session_id, username)
        response = make_response(redirect("/"))

        cookie_kwargs = {
            "key": constants.SESSION_ID,
            "value": session_id,
            # 1 month
            "max_age": 2678400,
            "secure": current_app.config["COOKIE_HTTPS_ONLY"],
            "httponly": True,
        }

        samesite_policy = current_app.config.get("COOKIE_SAMESITE_POLICY", None)
        # Certain Flask versions don't support 'samesite' param
        if samesite_policy:
            cookie_kwargs.update({"samesite": samesite_policy})

        response.set_cookie(**cookie_kwargs)
        return cast(Response, response)
    else:
        return redirect("/login")


@authenticated
@authorized
def main_calendar_action(calendar_id: str) -> Response:
    GregorianCalendar.setfirstweekday(current_app.config["WEEK_STARTING_DAY"])

    current_day, current_month, current_year = GregorianCalendar.current_date()
    year = int(request.args.get("y", current_year))
    year = max(min(year, current_app.config["MAX_YEAR"]), current_app.config["MIN_YEAR"])
    month = int(request.args.get("m", current_month))
    month = max(min(month, 12), 1)
    month_name = GregorianCalendar.MONTH_NAMES[month - 1]

    if current_app.config["HIDE_PAST_TASKS"]:
        view_past_tasks = False
    else:
        view_past_tasks = request.cookies.get("ViewPastTasks", "1") == "1"

    calendar_data = CalendarData(current_app.config["DATA_FOLDER"], current_app.config["WEEK_STARTING_DAY"])
    try:
        data = calendar_data.load_calendar(calendar_id)
    except FileNotFoundError:
        abort(404)

    tasks = calendar_data.tasks_from_calendar(year, month, data)
    tasks = calendar_data.add_repetitive_tasks_from_calendar(year, month, data, tasks)

    if not view_past_tasks:
        calendar_data.hide_past_tasks(year, month, tasks)

    # Energy balance for each day of the month.
    # A fresh copy of the data is used, because building the month view above adds the
    # repeating tasks into `data` and they would otherwise be counted twice.
    data = calendar_data.load_calendar(calendar_id)
    energy_settings = calendar_data.load_settings(data, current_app.config["DEFAULT_ENERGY_SETTINGS"])
    month_energy = {}
    for month_day in GregorianCalendar.month_days(year, month):
        if month_day.month != month:
            continue
        day_before = month_day - timedelta(days=1)
        month_energy[month_day.day] = day_energy_check(
            calendar_data.tasks_for_date(month_day, data),
            calendar_data.tasks_for_date(day_before, data),
            energy_settings,
            current_app.config["ENERGY_LEVELS"],
            current_app.config["ENERGY_POINTS"],
        )

    if current_app.config["WEEK_STARTING_DAY"] == constants.WEEK_START_DAY_MONDAY:
        weekdays_headers = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]
    else:
        weekdays_headers = ["SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"]

    return cast(
        Response,
        render_template(
            "calendar.html",
            calendar_id=calendar_id,
            year=year,
            month=month,
            month_name=month_name,
            current_year=current_year,
            current_month=current_month,
            current_day=current_day,
            month_days=GregorianCalendar.month_days(year, month),
            previous_month_link=previous_month_link(year, month),
            next_month_link=next_month_link(year, month),
            base_url=current_app.config["BASE_URL"],
            tasks=tasks,
            display_view_past_button=current_app.config["SHOW_VIEW_PAST_BUTTON"],
            weekdays_headers=weekdays_headers,
            month_energy=month_energy,
        ),
    )


@authenticated
@authorized
def new_task_action(calendar_id: str, year: int, month: int) -> Response:
    GregorianCalendar.setfirstweekday(current_app.config["WEEK_STARTING_DAY"])

    current_day, current_month, current_year = GregorianCalendar.current_date()
    year = max(min(int(year), current_app.config["MAX_YEAR"]), current_app.config["MIN_YEAR"])
    month = max(min(int(month), 12), 1)
    month_names = GregorianCalendar.MONTH_NAMES

    if current_month == month and current_year == year:
        day = current_day
    else:
        day = 1
    day = int(request.args.get("day", day))

    task = {
        "date": CalendarData.date_for_frontend(year, month, day),
        "is_all_day": True,
        "repeats": False,
        "details": "",
    }

    emojis_enabled = current_app.config.get("EMOJIS_ENABLED", False)

    return cast(
        Response,
        render_template(
            "task.html",
            calendar_id=calendar_id,
            year=year,
            month=month,
            min_year=current_app.config["MIN_YEAR"],
            max_year=current_app.config["MAX_YEAR"],
            month_names=month_names,
            task=task,
            base_url=current_app.config["BASE_URL"],
            editing=False,
            emojis_enabled=emojis_enabled,
            button_default_color_value=current_app.config["BUTTON_CUSTOM_COLOR_VALUE"],
            buttons_colors=current_app.config["BUTTONS_COLORS_LIST"],
            buttons_emojis=current_app.config["BUTTONS_EMOJIS_LIST"] if emojis_enabled else tuple(),
        ),
    )


@authenticated
@authorized
def edit_task_action(calendar_id: str, year: int, month: int, day: int, task_id: int) -> Response:
    month_names = GregorianCalendar.MONTH_NAMES
    calendar_data = CalendarData(current_app.config["DATA_FOLDER"], current_app.config["WEEK_STARTING_DAY"])

    repeats = request.args.get("repeats") == "1"
    try:
        if repeats:
            task = calendar_data.repetitive_task_from_calendar(
                calendar_id=calendar_id, year=year, month=month, task_id=int(task_id)
            )
            # Show the date of the occurrence that was opened, not the 1st of the month
            task["date"] = calendar_data.date_for_frontend(year, month, day)
        else:
            task = calendar_data.task_from_calendar(
                calendar_id=calendar_id,
                year=year,
                month=month,
                day=day,
                task_id=int(task_id),
            )
    except (FileNotFoundError, IndexError):
        abort(404)

    if task["details"] == "&nbsp;":
        task["details"] = ""

    emojis_enabled = current_app.config.get("EMOJIS_ENABLED", False)

    return cast(
        Response,
        render_template(
            "task.html",
            calendar_id=calendar_id,
            year=year,
            month=month,
            day=day,
            min_year=current_app.config["MIN_YEAR"],
            max_year=current_app.config["MAX_YEAR"],
            month_names=month_names,
            task=task,
            base_url=current_app.config["BASE_URL"],
            editing=True,
            emojis_enabled=emojis_enabled,
            button_default_color_value=current_app.config["BUTTON_CUSTOM_COLOR_VALUE"],
            buttons_colors=current_app.config["BUTTONS_COLORS_LIST"],
            buttons_emojis=current_app.config["BUTTONS_EMOJIS_LIST"] if emojis_enabled else tuple(),
        ),
    )


@authenticated
@authorized
def update_task_action(calendar_id: str, year: str, month: str, day: str, task_id: str) -> Response:
    # Logic is same as save + delete, could refactor but can wait until need to change any save/delete logic

    calendar_data = CalendarData(current_app.config["DATA_FOLDER"], current_app.config["WEEK_STARTING_DAY"])

    # For creation of "updated" task use only form data
    title = request.form["title"].strip()
    start_date = request.form.get("date", "")
    if len(start_date) > 0:
        fragments = re.split("-", start_date)
        updated_year = int(fragments[0])  # type: Optional[int]
        updated_month = int(fragments[1])  # type: Optional[int]
        updated_day = int(fragments[2])  # type: Optional[int]
    else:
        updated_year = updated_month = updated_day = None
    is_all_day = request.form.get("is_all_day", "0") == "1"
    start_time = request.form["start_time"]
    end_time = request.form.get("end_time", None)
    details = ""
    color = request.form["color"]
    has_repetition = request.form.get("repeats", "0") == "1"
    repetition_type = request.form.get("repetition_type", "")
    repetition_subtype = request.form.get("repetition_subtype", "")
    repetition_value = int(request.form["repetition_value"])  # type: int
    locked = request.form.get("locked", "0") == "1"

    calendar_data.create_task(
        calendar_id=calendar_id,
        year=updated_year,
        month=updated_month,
        day=updated_day,
        title=title,
        is_all_day=is_all_day,
        start_time=start_time,
        end_time=end_time,
        details=details,
        color=color,
        has_repetition=has_repetition,
        repetition_type=repetition_type,
        repetition_subtype=repetition_subtype,
        repetition_value=repetition_value,
        locked=locked,
    )
    # For deletion of old task data use only url data (force: the old copy goes even if it was locked)
    calendar_data.delete_task(
        calendar_id=calendar_id,
        year_str=year,
        month_str=month,
        day_str=day,
        task_id=int(task_id),
        force=True,
    )

    learn_from_placement(calendar_id, color, start_date, start_time, is_all_day)

    if updated_year is None:
        return redirect("{}/{}/".format(current_app.config["BASE_URL"], calendar_id), code=302)
    else:
        return redirect(
            "{}/{}/?y={}&m={}".format(current_app.config["BASE_URL"], calendar_id, updated_year, updated_month),
            code=302,
        )


def learn_from_placement(calendar_id: str, color: str, date_text: str, start_time: str, is_all_day: bool) -> None:
    """Remembers when she chose to do this kind of task, so suggestions can follow her habits."""
    level = current_app.config["ENERGY_LEVELS"].get((color or "").lower(), ("", ""))[0]
    if not level or is_all_day or not date_text:
        return
    try:
        chosen_day = date(*[int(part) for part in date_text.split("-")])
        start_minutes = time_to_minutes(start_time)
    except (ValueError, TypeError):
        return
    calendar_data = CalendarData(current_app.config["DATA_FOLDER"], current_app.config["WEEK_STARTING_DAY"])
    data = calendar_data.load_calendar(calendar_id)
    learned = calendar_data.load_learned(data)
    record_placement(learned, level, chosen_day, start_minutes)
    calendar_data.save_learned(calendar_id, learned)


@authenticated
@authorized
def save_task_action(calendar_id: str) -> Response:
    title = request.form["title"].strip()
    startdate = request.form.get("date", "")
    enddate = request.form.get("enddate", "")

    if len(startdate) > 0:
        date_fragments = re.split("-", startdate)
        year = int(date_fragments[0])  # type: Optional[int]
        month = int(date_fragments[1])  # type: Optional[int]
        day = int(date_fragments[2])  # type: Optional[int]
    else:
        year = month = day = None
    is_all_day = request.form.get("is_all_day", "0") == "1"
    start_time = request.form["start_time"]
    end_time = request.form.get("end_time", None)
    details = ""
    color = request.form["color"]
    has_repetition = request.form.get("repeats", "0") == "1"
    repetition_type = request.form.get("repetition_type")
    repetition_subtype = request.form.get("repetition_subtype")
    repetition_value = int(request.form["repetition_value"])
    locked = request.form.get("locked", "0") == "1"

    calendar_data = CalendarData(current_app.config["DATA_FOLDER"], current_app.config["WEEK_STARTING_DAY"])

    dates_to_create = []  # type: List[Tuple[Optional[int], Optional[int], Optional[int]]]

    # repetitive tasks not supported
    if startdate != enddate and not has_repetition:
        startdate_fragments = re.split("-", startdate)
        enddate_fragments = re.split("-", enddate)
        sdate = date(int(startdate_fragments[0]), int(startdate_fragments[1]), int(startdate_fragments[2]))
        edate = date(int(enddate_fragments[0]), int(enddate_fragments[1]), int(enddate_fragments[2]))
        delta = edate - sdate
        for i in range(delta.days + 1):
            currentdate = re.split("-", str(sdate + timedelta(days=i)))

            year = int(currentdate[0])
            month = int(currentdate[1])
            day = int(currentdate[2])

            dates_to_create.append((year, month, day))
    else:
        dates_to_create.append((year, month, day))

    for date_tuple in dates_to_create:
        year, month, day = date_tuple
        calendar_data.create_task(
            calendar_id=calendar_id,
            year=year,
            month=month,
            day=day,
            title=title,
            is_all_day=is_all_day,
            start_time=start_time,
            end_time=end_time,
            details=details,
            color=color,
            has_repetition=has_repetition,
            repetition_type=repetition_type,
            repetition_subtype=repetition_subtype,
            repetition_value=repetition_value,
            locked=locked,
        )

    learn_from_placement(calendar_id, color, startdate, start_time, is_all_day)

    if year is None:
        return redirect("{}/{}/".format(current_app.config["BASE_URL"], calendar_id), code=302)
    else:
        return redirect(
            "{}/{}/?y={}&m={}".format(current_app.config["BASE_URL"], calendar_id, year, month),
            code=302,
        )


@authenticated
@authorized
def delete_task_action(calendar_id: str, year: str, month: str, day: str, task_id: str) -> Response:
    calendar_data = CalendarData(current_app.config["DATA_FOLDER"], current_app.config["WEEK_STARTING_DAY"])
    deleted = calendar_data.delete_task(
        calendar_id=calendar_id,
        year_str=year,
        month_str=month,
        day_str=day,
        task_id=int(task_id),
    )
    if not deleted:
        return cast(Response, make_response(jsonify({"error": "This task is locked. Unlock it first."}), 423))

    return cast(Response, jsonify({}))


@authenticated
@authorized
def update_task_day_action(calendar_id: str, year: str, month: str, day: str, task_id: str) -> Response:
    new_day = request.data.decode("utf-8")

    calendar_data = CalendarData(current_app.config["DATA_FOLDER"], current_app.config["WEEK_STARTING_DAY"])
    moved = calendar_data.update_task_day(
        calendar_id=calendar_id,
        year_str=year,
        month_str=month,
        day_str=day,
        task_id=int(task_id),
        new_day_str=new_day,
    )
    if not moved:
        return cast(Response, make_response(jsonify({"error": "This task is locked. Unlock it first."}), 423))

    return cast(Response, jsonify({}))


@authenticated
@authorized
def hide_repetition_task_instance_action(calendar_id: str, year: str, month: str, day: str, task_id: str) -> Response:
    calendar_data = CalendarData(current_app.config["DATA_FOLDER"], current_app.config["WEEK_STARTING_DAY"])
    calendar_data.hide_repetition_task_instance(
        calendar_id=calendar_id,
        year_str=year,
        month_str=month,
        day_str=day,
        task_id_str=task_id,
    )

    return cast(Response, jsonify({}))

@authenticated
@authorized
def weekly_calendar_action(calendar_id: str):
    """Display seven days on an hourly calendar grid."""
    today = date.today()

    current_day, current_month, current_year = GregorianCalendar.current_date()
    year = int(request.args.get("y", current_year))
    year = max(min(year, current_app.config["MAX_YEAR"]), current_app.config["MIN_YEAR"])
    month = int(request.args.get("m", current_month))
    month = max(min(month, 12), 1)

    selected_date = parse_iso_date(
        request.args.get("date"),
        default=today,
    )

    first_weekday = current_app.config["WEEK_STARTING_DAY"]
    week_start = start_of_week(selected_date, first_weekday)
    week_end = week_start + timedelta(days=6)

    calendar_data = CalendarData(
        data_folder=current_app.config["DATA_FOLDER"],
        first_weekday=first_weekday,
    )
    data = calendar_data.load_calendar(calendar_id)
    tasks = calendar_data.tasks_for_week(week_start, data)
    energy_settings = calendar_data.load_settings(data, current_app.config["DEFAULT_ENERGY_SETTINGS"])

    start_hour = int(energy_settings["day_start"])
    end_hour = int(energy_settings["day_end"])
    hour_height = current_app.config["WEEK_VIEW_HOUR_HEIGHT"]

    week_days = prepare_week_days(
        week_start=week_start,
        tasks=tasks,
        start_hour=start_hour,
        end_hour=end_hour,
        hour_height=hour_height,
        minimum_task_minutes=current_app.config[
            "WEEK_VIEW_MIN_TASK_MINUTES"
        ],
    )

    # Energy balance for each day (uses all of the day's tasks, even ones outside the visible hours)
    previous_day_tasks = calendar_data.tasks_for_date(week_start - timedelta(days=1), data)
    for week_day in week_days:
        day_tasks = tasks.get(week_day["date_key"], [])
        week_day["energy"] = day_energy_check(
            day_tasks,
            previous_day_tasks,
            energy_settings,
            current_app.config["ENERGY_LEVELS"],
            current_app.config["ENERGY_POINTS"],
        )
        previous_day_tasks = day_tasks

    # "Suggest a balanced week": a preview she can accept or ignore
    suggestion = None
    if request.args.get("suggest") == "1":
        suggestion = suggest_week(
            week_dates=[week_day["date"] for week_day in week_days],
            tasks_by_date=tasks,
            previous_day_tasks=calendar_data.tasks_for_date(week_start - timedelta(days=1), data),
            settings=energy_settings,
            energy_levels=current_app.config["ENERGY_LEVELS"],
            energy_points=current_app.config["ENERGY_POINTS"],
            learned=calendar_data.load_learned(data),
            today=today,
        )
        for move in suggestion["moves"]:
            move["top"] = (move["to_start_minutes"] - start_hour * 60) * hour_height / 60
            move["height"] = move["length"] * hour_height / 60

    previous_week = week_start - timedelta(days=7)
    next_week = week_start + timedelta(days=7)

    return render_template(
        "week.html",
        calendar_id=calendar_id,
        year=year,
        month=month,
        week_start=week_start,
        week_end=week_end,
        week_days=week_days,
        today=today,
        previous_week=previous_week.isoformat(),
        next_week=next_week.isoformat(),
        start_hour=start_hour,
        end_hour=end_hour,
        hours=range(start_hour, end_hour),
        hour_height=hour_height,
        grid_height=(end_hour - start_hour) * hour_height,
        activity_bank=current_app.config["ACTIVITY_BANK"],
        energy_levels=current_app.config["BUTTONS_COLORS_LIST"],
        suggestion=suggestion,
        suggestion_json=json.dumps(suggestion["moves"]) if suggestion else "[]",
        applied=request.args.get("applied"),
    )

@authenticated
@authorized
def settings_action(calendar_id: str):
    """Shows the balance settings page."""
    calendar_data = CalendarData(current_app.config["DATA_FOLDER"], current_app.config["WEEK_STARTING_DAY"])
    data = calendar_data.load_calendar(calendar_id)
    settings = calendar_data.load_settings(data, current_app.config["DEFAULT_ENERGY_SETTINGS"])

    return render_template(
        "settings.html",
        calendar_id=calendar_id,
        settings=settings,
        energy_points=current_app.config["ENERGY_POINTS"],
        saved=request.args.get("saved") == "1",
        forgot=request.args.get("forgot") == "1",
        learned=learned_summary(calendar_data.load_learned(data)),
        hours=range(0, 24),
    )


@authenticated
@authorized
def save_settings_action(calendar_id: str) -> Response:
    """Saves the balance settings, keeping every value within a sensible range."""
    defaults = current_app.config["DEFAULT_ENERGY_SETTINGS"]

    def number(name: str, minimum: float, maximum: float) -> float:
        try:
            value = float(request.form.get(name, defaults[name]))
        except ValueError:
            value = float(defaults[name])
        return max(minimum, min(value, maximum))

    day_start = int(number("day_start", 0, 22))
    day_end = int(number("day_end", 1, 24))
    if day_end <= day_start:
        day_end = min(day_start + 1, 24)

    red_time = request.form.get("red_time", "any")
    if red_time not in ("any", "morning", "afternoon", "evening"):
        red_time = "any"

    settings = {
        "daily_limit": number("daily_limit", 0.5, 50),
        "max_red": int(number("max_red", 0, 10)),
        "red_time": red_time,
        "rest_after_red_day": request.form.get("rest_after_red_day") == "1",
        "day_start": day_start,
        "day_end": day_end,
    }

    calendar_data = CalendarData(current_app.config["DATA_FOLDER"], current_app.config["WEEK_STARTING_DAY"])
    calendar_data.save_settings(calendar_id, settings)

    return redirect("{}/{}/settings/?saved=1".format(current_app.config["BASE_URL"], calendar_id), code=302)


@authenticated
@authorized
def forget_learning_action(calendar_id: str) -> Response:
    """Clears what the calendar has learned about her habits."""
    calendar_data = CalendarData(current_app.config["DATA_FOLDER"], current_app.config["WEEK_STARTING_DAY"])
    calendar_data.save_learned(calendar_id, {})
    return redirect("{}/{}/settings/?forgot=1".format(current_app.config["BASE_URL"], calendar_id), code=302)


@authenticated
@authorized
def apply_suggestion_action(calendar_id: str) -> Response:
    """Moves the tasks from a suggestion she accepted."""
    try:
        moves = json.loads(request.form.get("moves", "[]"))
    except ValueError:
        moves = []
    if not isinstance(moves, list):
        moves = []
    calendar_data = CalendarData(current_app.config["DATA_FOLDER"], current_app.config["WEEK_STARTING_DAY"])
    moved = calendar_data.move_tasks(calendar_id, [move for move in moves if isinstance(move, dict)])
    week = request.form.get("week", "")
    return redirect(
        "{}/{}/week/?date={}&applied={}".format(current_app.config["BASE_URL"], calendar_id, week, moved), code=302
    )
