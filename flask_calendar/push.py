"""Reminder notifications sent from the server (Web Push), and text messages (see sms.py).

The client adds the calendar to her iPad's Home Screen and turns on notifications in
Settings. Her iPad then gives us a "subscription" (an address for her device). Every
30 seconds the server looks for reminders that are due and sends them there, so they
arrive even when the calendar is closed and the iPad is locked.

Works with iPadOS / iOS 16.4+ (Home Screen web apps) and with Chrome, Edge and Firefox.
"""
import base64
import json
import logging
import os
import threading
import time
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from cryptography.hazmat.primitives import serialization
from flask import Flask

from flask_calendar import sms
from flask_calendar.calendar_data import CalendarData

KEY_SUBSCRIPTIONS = "push_subscriptions"
KEY_SENT = "push_sent"

logger = logging.getLogger(__name__)
_scheduler_started = False
_scheduler_lock = threading.Lock()


# ---------------------------------------------------------------- keys


def _vapid(app: Flask) -> Any:
    """The server's signing key for push messages. Created the first time it is needed."""
    from py_vapid import Vapid01

    path = app.config["VAPID_PRIVATE_KEY_FILE"]
    if not os.path.exists(path):
        folder = os.path.dirname(path)
        if folder:
            os.makedirs(folder, exist_ok=True)
        vapid = Vapid01()
        vapid.generate_keys()
        vapid.save_key(path)
        logger.info("Created a new push key at %s", path)
    return Vapid01.from_file(path)


def public_key(app: Flask) -> str:
    """Public key the browser needs to subscribe (base64url, no padding)."""
    raw = _vapid(app).public_key.public_bytes(
        encoding=serialization.Encoding.X962, format=serialization.PublicFormat.UncompressedPoint
    )
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


# ---------------------------------------------------------------- subscriptions


def _valid_subscription(subscription: Any) -> bool:
    return (
        isinstance(subscription, dict)
        and isinstance(subscription.get("endpoint"), str)
        and subscription["endpoint"].startswith("https://")
        and isinstance(subscription.get("keys"), dict)
        and "p256dh" in subscription["keys"]
        and "auth" in subscription["keys"]
    )


def add_subscription(calendar_data: CalendarData, calendar_id: str, subscription: Dict) -> bool:
    if not _valid_subscription(subscription):
        return False
    data = calendar_data.load_calendar(calendar_id)
    subscriptions = [s for s in data.get(KEY_SUBSCRIPTIONS, []) if s.get("endpoint") != subscription["endpoint"]]
    subscriptions.append(
        {"endpoint": subscription["endpoint"], "keys": {k: subscription["keys"][k] for k in ("p256dh", "auth")}}
    )
    data[KEY_SUBSCRIPTIONS] = subscriptions
    calendar_data._save_calendar(data, filename=calendar_id)
    return True


def remove_subscription(calendar_data: CalendarData, calendar_id: str, endpoint: str) -> None:
    data = calendar_data.load_calendar(calendar_id)
    data[KEY_SUBSCRIPTIONS] = [s for s in data.get(KEY_SUBSCRIPTIONS, []) if s.get("endpoint") != endpoint]
    calendar_data._save_calendar(data, filename=calendar_id)


# ---------------------------------------------------------------- sending


def send(app: Flask, subscriptions: List[Dict], payload: Dict) -> Tuple[int, List[str]]:
    """Send one message to each subscription. Returns (number sent, endpoints that no longer exist)."""
    from pywebpush import WebPushException, webpush

    vapid = _vapid(app)
    sent = 0
    gone = []  # type: List[str]
    for subscription in subscriptions:
        try:
            webpush(
                subscription_info=subscription,
                data=json.dumps(payload),
                vapid_private_key=vapid,
                vapid_claims={"sub": app.config["VAPID_SUBJECT"]},
                ttl=3600,
                timeout=10,
            )
            sent += 1
        except WebPushException as error:
            status = getattr(error.response, "status_code", None)
            if status in (404, 410):
                gone.append(subscription["endpoint"])  # the device turned notifications off or was reset
            else:
                logger.warning("Push failed (%s): %s", status, error)
        except Exception as error:  # network problems: try again next round
            logger.warning("Push failed: %s", error)
    return sent, gone


def _start_of(day: date, task: Dict) -> datetime:
    start = "08:00" if task.get("is_all_day") else (task.get("start_time") or "08:00")
    hours, minutes = [int(part) for part in start[:5].split(":")]
    return datetime(day.year, day.month, day.day, hours, minutes)


def message_for(task: Dict, day: date, now: datetime, calendar_id: str, energy_name: str) -> Dict:
    start = _start_of(day, task)
    minutes_left = int(round((start - now).total_seconds() / 60))
    if task.get("is_all_day"):
        when = "Today (all day)" if day == now.date() else "Tomorrow (all day)"
    elif minutes_left <= 0:
        when = "Starting now ({})".format(start.strftime("%H:%M"))
    elif day != now.date():
        when = "Tomorrow at {}".format(start.strftime("%H:%M"))
    elif minutes_left < 60:
        when = "In {} minute{} ({})".format(minutes_left, "" if minutes_left == 1 else "s", start.strftime("%H:%M"))
    else:
        when = "Today at {}".format(start.strftime("%H:%M"))
    return {
        "title": task.get("title", "Reminder"),
        "body": when + (" · " + energy_name if energy_name else ""),
        "tag": "{}-{}".format(task["id"], day.isoformat()),
        "url": "/{}/week/?date={}".format(calendar_id, day.isoformat()),
    }


def due_reminders(
    calendar_data: CalendarData, data: Dict, now: datetime, catch_up_minutes: int = 10
) -> List[Tuple[str, date, Dict]]:
    """Reminders whose time has come in the last few minutes (so a short outage doesn't lose them)."""
    due = []
    for offset in (0, 1):
        day = now.date() + timedelta(days=offset)
        for task in calendar_data.tasks_for_date(day, data):
            if "reminder" not in task:
                continue
            start = _start_of(day, task)
            remind_at = start - timedelta(minutes=int(task["reminder"]))
            in_window = remind_at <= now < remind_at + timedelta(minutes=catch_up_minutes)
            if in_window and now <= start + timedelta(minutes=30):
                due.append(("{}-{}".format(task["id"], day.isoformat()), day, task))
    return due


def local_now(app: Flask) -> datetime:
    try:
        from zoneinfo import ZoneInfo

        return datetime.now(ZoneInfo(app.config["TIMEZONE"])).replace(tzinfo=None)
    except Exception:
        logger.warning("Unknown TIMEZONE %s, using the server's clock", app.config.get("TIMEZONE"))
        return datetime.now()


def run_once(app: Flask, now: Optional[datetime] = None) -> int:
    """Send every reminder that is due now. Returns how many messages were sent."""
    now = now or local_now(app)
    calendar_data = CalendarData(app.config["DATA_FOLDER"], app.config["WEEK_STARTING_DAY"])
    levels = app.config["ENERGY_LEVELS"]
    total = 0
    for filename in sorted(os.listdir(app.config["DATA_FOLDER"])):
        if not filename.endswith(".json"):
            continue
        calendar_id = filename[: -len(".json")]
        try:
            data = calendar_data.load_calendar(calendar_id)
        except Exception:
            continue
        settings = data.get("settings", {})
        phone = settings.get("sms_phone") if settings.get("sms_enabled") and sms.configured(app) else None
        if not data.get(KEY_SUBSCRIPTIONS) and not phone:
            continue
        sent_log = data.get(KEY_SENT, {})
        changed = False
        for key, day, task in due_reminders(calendar_data, data, now):
            if key in sent_log:
                continue
            energy = levels.get((task.get("color") or "").lower(), ("", ""))[1]
            message = message_for(task, day, now, calendar_id, energy)
            sent, gone = send(app, data.get(KEY_SUBSCRIPTIONS, []), message) if data.get(KEY_SUBSCRIPTIONS) else (0, [])
            total += sent
            if phone and sms.send_text(app, phone, sms.text_for(message))[0]:
                total += 1
            sent_log[key] = now.isoformat(timespec="minutes")
            if gone:
                data[KEY_SUBSCRIPTIONS] = [s for s in data.get(KEY_SUBSCRIPTIONS, []) if s["endpoint"] not in gone]
            changed = True
        if changed:
            # Re-read just before saving so edits made in the meantime are not lost
            fresh = calendar_data.load_calendar(calendar_id)
            cutoff = (now - timedelta(days=3)).isoformat()
            fresh[KEY_SENT] = {k: v for k, v in sent_log.items() if v >= cutoff}
            fresh[KEY_SUBSCRIPTIONS] = data.get(KEY_SUBSCRIPTIONS, [])
            calendar_data._save_calendar(fresh, filename=calendar_id)
    return total


def start_scheduler(app: Flask) -> None:
    """Check for due reminders every 30 seconds in a background thread (started once per process)."""
    global _scheduler_started
    with _scheduler_lock:
        if _scheduler_started or not app.config.get("PUSH_REMINDERS_ENABLED", True):
            return
        _scheduler_started = True

    def loop() -> None:
        while True:
            try:
                with app.app_context():
                    run_once(app)
            except Exception as error:
                logger.warning("Reminder check failed: %s", error)
            time.sleep(30)

    threading.Thread(target=loop, name="reminder-push", daemon=True).start()
