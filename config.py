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

WEEK_STARTING_DAY = constants.WEEK_START_DAY_MONDAY

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

# Activity bank shown on the week view: (name, energy colour, length in minutes).
# Edit this list with the client to match her own activities and energy levels.
ACTIVITY_BANK = (
    ("Walk", "#3EB34F", 60),
    ("Reading", "#3EB34F", 30),
    ("Rest", "#3EB34F", 60),
    ("Cooking", "#F2C81A", 60),
    ("Laundry", "#F2C81A", 60),
    ("Phone call", "#F2C81A", 30),
    ("Medical appointment", "#FF4848", 60),
    ("Grocery shopping", "#FF4848", 90),
    ("Physiotherapy", "#FF4848", 60),
)

# percent of chance to do a GC-like sweep on save and clean empty and/or past hidden entries.
# values [0, 100] -> Note that 0 disables it, 100 makes it run every time
GC_ON_SAVE_CHANCE = 30
