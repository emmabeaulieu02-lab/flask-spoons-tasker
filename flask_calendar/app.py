#!/usr/bin/python

import locale
import os
from typing import Dict, Optional

from flask import Flask, Response, send_from_directory

import config  # noqa: F401
from flask_calendar.actions import (
    delete_task_action,
    do_login_action,
    edit_task_action,
    hide_repetition_task_instance_action,
    index_action,
    login_action,
    main_calendar_action,
    new_task_action,
    save_task_action,
    update_task_action,
    update_task_day_action,
    weekly_calendar_action,
    settings_action,
    save_settings_action,
    forget_learning_action,
    remove_activity_action,
    apply_suggestion_action,
)
from flask_calendar.app_utils import task_details_for_markup


def create_app(config_overrides: Optional[Dict] = None) -> Flask:
    app = Flask(__name__)
    app.config.from_object("config")

    if config_overrides is not None:
        app.config.from_mapping(config_overrides)

    if app.config["LOCALE"] is not None:
        try:
            locale.setlocale(locale.LC_ALL, app.config["LOCALE"])
        except locale.Error as e:
            app.logger.warning("{} ({})".format(str(e), app.config["LOCALE"]))

    # To avoid main_calendar_action below shallowing favicon requests and generating error logs
    @app.route("/favicon.ico")
    def favicon() -> Response:
        return send_from_directory(
            os.path.join(app.root_path, "static"),
            "favicon.ico",
            mimetype="image/vnd.microsoft.icon",
        )

    app.add_url_rule("/", "index_action", index_action, methods=["GET"])
    app.add_url_rule("/login", "login_action", login_action, methods=["GET"])
    app.add_url_rule("/do_login", "do_login_action", do_login_action, methods=["POST"])
    app.add_url_rule("/<calendar_id>/", "main_calendar_action", main_calendar_action, methods=["GET"])
    app.add_url_rule(
        "/<calendar_id>/<year>/<month>/new_task",
        "new_task_action",
        new_task_action,
        methods=["GET"],
    )
    app.add_url_rule(
        "/<calendar_id>/<year>/<month>/<day>/<task_id>/",
        "edit_task_action",
        edit_task_action,
        methods=["GET"],
    )
    app.add_url_rule(
        "/<calendar_id>/<year>/<month>/<day>/task/<task_id>",
        "update_task_action",
        update_task_action,
        methods=["POST"],
    )
    app.add_url_rule(
        "/<calendar_id>/new_task",
        "save_task_action",
        save_task_action,
        methods=["POST"],
    )
    app.add_url_rule(
        "/<calendar_id>/<year>/<month>/<day>/<task_id>/",
        "delete_task_action",
        delete_task_action,
        methods=["DELETE"],
    )
    app.add_url_rule(
        "/<calendar_id>/<year>/<month>/<day>/<task_id>/",
        "update_task_day_action",
        update_task_day_action,
        methods=["PUT"],
    )
    app.add_url_rule(
        "/<calendar_id>/<year>/<month>/<day>/<task_id>/hide/",
        "hide_repetition_task_instance_action",
        hide_repetition_task_instance_action,
        methods=["POST"],
    )
    app.add_url_rule(
        "/<calendar_id>/week/",
        "weekly_calendar_action",
        weekly_calendar_action,
        methods=["GET"],
    )
    app.add_url_rule(
        "/<calendar_id>/settings/",
        "settings_action",
        settings_action,
        methods=["GET"],
    )

    app.add_url_rule(
        "/<calendar_id>/settings/",
        "save_settings_action",
        save_settings_action,
        methods=["POST"],
    )

    app.add_url_rule(
        "/<calendar_id>/settings/remove-activity/",
        "remove_activity_action",
        remove_activity_action,
        methods=["POST"],
    )
    app.add_url_rule(
        "/<calendar_id>/settings/forget-learning/",
        "forget_learning_action",
        forget_learning_action,
        methods=["POST"],
    )
    app.add_url_rule(
        "/<calendar_id>/week/apply-suggestion/",
        "apply_suggestion_action",
        apply_suggestion_action,
        methods=["POST"],
    )

    app.jinja_env.filters["task_details_for_markup"] = task_details_for_markup

    def energy_level(color: Optional[str]) -> str:
        """'low', 'medium' or 'high' for an energy colour, '' for any other colour."""
        return app.config["ENERGY_LEVELS"].get((color or "").lower(), ("", ""))[0]

    def energy_name(color: Optional[str]) -> str:
        """Words for an energy colour, e.g. 'Low energy'."""
        return app.config["ENERGY_LEVELS"].get((color or "").lower(), ("", ""))[1]

    def text_color_for(background: Optional[str]) -> str:
        """Dark or white text, whichever is easier to read on this background colour."""
        value = (background or "").lstrip("#")
        if len(value) != 6:
            return "#1F1F1F"
        channels = []
        for index in (0, 2, 4):
            channel = int(value[index:index + 2], 16) / 255
            channels.append(channel / 12.92 if channel <= 0.03928 else ((channel + 0.055) / 1.055) ** 2.4)
        luminance = 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]
        # pick whichever text colour gives the higher contrast ratio
        dark_contrast = (luminance + 0.05) / (0.0137 + 0.05)
        white_contrast = 1.05 / (luminance + 0.05)
        return "#1F1F1F" if dark_contrast >= white_contrast else "#FFFFFF"

    app.jinja_env.filters["text_color_for"] = text_color_for
    app.jinja_env.filters["energy_level"] = energy_level
    app.jinja_env.filters["energy_name"] = energy_name

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=app.config["DEBUG"], host=app.config["HOST_IP"])
