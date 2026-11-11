import flask_calendar.constants as constants

DEBUG = True
DATA_FOLDER = "data"
USERS_DATA_FOLDER = "users"
BASE_URL = "http://127.0.0.1:5000"
MIN_YEAR = 2017
MAX_YEAR = 2200
PASSWORD_SALT = "something random and full of non-standard characters"
HOST_IP = "127.0.0.1"  # set to None for production
LOCALE = "en_US.UTF-8"
# https://en.wikipedia.org/wiki/List_of_tz_database_time_zones
TIMEZONE = "US/Central"

WEEK_STARTING_DAY = constants.WEEK_START_DAY_SUNDAY  # North American calendar, like the client's iPad

WEEK_VIEW_START_HOUR = 8
WEEK_VIEW_END_HOUR = 21

WEEK_VIEW_HOUR_HEIGHT = 60

WEEK_VIEW_MIN_TASK_MINUTES = 30

MONTHS_TO_EXPORT = 6  # currently only used for ICS export

FEATURE_FLAG_ICAL_EXPORT = False

# (base ^ attempts ) second delays between failed logins
FAILED_LOGIN_DELAY_BASE = 2

# If true, will automatically decorate hyperlinks with <a> tags upon rendering them
AUTO_DECORATE_TASK_DETAILS_HYPERLINK = True

SHOW_VIEW_PAST_BUTTON = True

# Of use if SHOW_VIEW_PAST_BUTTON is False
HIDE_PAST_TASKS = False

# days past to keep hidden tasks (future ones always kept) counting all months as 31 days long
DAYS_PAST_TO_KEEP_HIDDEN_TASKS = 62

# Cookies config
COOKIE_HTTPS_ONLY = False
COOKIE_SAMESITE_POLICY = "Lax"

# If to render emoji buttons at the task create/edit page
EMOJIS_ENABLED = False

# Colors for new task buttons
BUTTON_CUSTOM_COLOR_VALUE = "#3EB34F"
BUTTONS_COLORS_LIST = (
    ("#3EB34F", "Green - low energy"),
    ("#F2C81A", "Yellow - medium energy"),
    ("#FF4848", "Red - high energy"),
)

# Energy level of each task colour: colour code -> (CSS name, words shown on screen).
# Tasks show these words as well as the colour, so colour is never the only clue.
ENERGY_LEVELS = {
    "#3eb34f": ("low", "Low energy"),
    "#f2c81a": ("medium", "Medium energy"),
    "#ff4848": ("high", "High energy"),
}

# Energy points for each level, used to check that a day is balanced
ENERGY_POINTS = {
    "low": 1,
    "medium": 3,  # client meeting 3: two yellow tasks should already feel like a full day
    "high": 4,
}

# Default balance settings. The client can change these on the Settings page.
DEFAULT_ENERGY_SETTINGS = {
    "daily_limit": 6,  # most energy points in one day
    "max_red": 1,  # most red (high energy) tasks in one day
    "red_time": "any",  # best time for red tasks: any, morning, afternoon or evening
    "rest_after_red_day": False,  # warn when two days in a row both have red tasks
    "day_start": WEEK_VIEW_START_HOUR,  # first hour shown in the week view
    "day_end": WEEK_VIEW_END_HOUR,  # last hour shown in the week view
    "theme": "light",  # light, dark or auto (follow the tablet). Client prefers light.
    "font_size": "normal",  # normal, large or extra-large
    "show_energy_words": True,  # show Low / Medium / High on each task
}

# Activity bank shown on the week view:
# (name, energy colour, length in minutes, locked).
# Locked activities can't be moved by accident (for example appointments).
# Edit this list with the client to match her own activities and energy levels.
ACTIVITY_BANK = (
    # From the client's email of 9 November 2026 (after client meeting 3).
    # Green - low energy
    ("Walk and small groceries", "#3EB34F", 90, True),  # daily, non-negotiable, ~10:00 or ~14:00
    ("Clean bathroom", "#3EB34F", 60, False),  # weekly, a day or two before the Tuesday music lesson
    ("Hobby: practise music", "#3EB34F", 30, False),  # weekly, a day or two before the Tuesday music lesson
    ("Meal prep 1/3: meat", "#3EB34F", 60, False),  # three consecutive days
    ("Meal prep 2/3: veggies", "#3EB34F", 60, False),
    ("Meal prep 3/3: pasta or rice", "#3EB34F", 60, False),
    ("Unload dishwasher 1/3: cutlery", "#3EB34F", 15, False),  # three consecutive days
    ("Unload dishwasher 2/3: plates", "#3EB34F", 15, False),
    ("Unload dishwasher 3/3: cups", "#3EB34F", 15, False),
    ("Rest", "#3EB34F", 60, False),  # e.g. after changing the bed
    # Yellow - medium energy
    ("Church and fellowship", "#F2C81A", 90, True),  # Sunday, service 10:30-12:00
    ("Music lesson", "#F2C81A", 30, True),  # Tuesday 18:00, at home
    ("Exercise class", "#F2C81A", 60, True),  # Wednesday 11:30-12:30 (walk moves to 14:00)
    ("Medical appointment", "#F2C81A", 120, True),  # Thursdays 9:30-11:30 and 12:30-14:30, or as needed
    ("Physiotherapy", "#F2C81A", 120, True),  # Friday 10:00-12:00
    ("Laundry and hanging clothes", "#F2C81A", 60, False),
    ("Vacuuming", "#F2C81A", 60, False),  # a day or two before the Tuesday music lesson
    ("Washing floors", "#F2C81A", 60, False),  # occasional
    ("Lunch with a friend", "#F2C81A", 90, False),  # occasional
    ("Special event", "#F2C81A", 120, False),
    # Red - high energy
    ("Change bed and towels", "#FF4848", 60, True),  # Saturday afternoon, weekly; rest afterwards
)

# percent of chance to do a GC-like sweep on save and clean empty and/or past hidden entries.
# values [0, 100] -> Note that 0 disables it, 100 makes it run every time
GC_ON_SAVE_CHANCE = 30
