"""Send reminder notifications that are due now (for a cron job running every minute).

Use this instead of the built-in 30-second check when PUSH_REMINDERS_ENABLED = False:

    python -m flask_calendar.scripts.send_reminders
"""
from flask_calendar import push
from flask_calendar.app import create_app


def main() -> None:
    app = create_app()
    with app.app_context():
        sent = push.run_once(app)
    print("Sent {} reminder notification(s).".format(sent))


if __name__ == "__main__":
    main()
