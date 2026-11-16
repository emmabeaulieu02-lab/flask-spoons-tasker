/* Reminders: shows a calm pop-up on this tablet when a task with a reminder is due.
 * Works while the calendar is open in the browser. The server sends the tasks with a
 * reminder for today and tomorrow; the tablet's own clock decides when to show them.
 */
(function () {
    "use strict";

    var script = document.currentScript || document.querySelector("script[data-url][src*='reminders.js']");
    if (!script) {
        return;
    }
    var url = script.getAttribute("data-url");
    var STORE_KEY = "energy-calendar-reminders";
    var SNOOZE_MINUTES = 10;
    var SHOW_UNTIL_MINUTES_AFTER_START = 30;

    var items = [];
    var memoryStore = {};
    var open = null;
    var lastLoaded = 0;

    function readStore() {
        try {
            var saved = JSON.parse(window.localStorage.getItem(STORE_KEY) || "{}");
            return saved && typeof saved === "object" ? saved : {};
        } catch (error) {
            return memoryStore;
        }
    }

    function writeStore(store) {
        memoryStore = store;
        try {
            window.localStorage.setItem(STORE_KEY, JSON.stringify(store));
        } catch (error) {
            /* private browsing: keep it in memory for this visit */
        }
    }

    function pad(n) {
        return (n < 10 ? "0" : "") + n;
    }

    function localDate(d) {
        return d.getFullYear() + "-" + pad(d.getMonth() + 1) + "-" + pad(d.getDate());
    }

    function startOf(item) {
        var d = item.date.split("-");
        var t = item.start.split(":");
        return new Date(+d[0], +d[1] - 1, +d[2], +t[0], +t[1]);
    }

    function load() {
        lastLoaded = Date.now();
        return fetch(url + "?date=" + localDate(new Date()), { credentials: "same-origin" })
            .then(function (response) {
                return response.ok ? response.json() : [];
            })
            .then(function (list) {
                items = Array.isArray(list) ? list : [];
                check();
            })
            .catch(function () {
                /* offline for a moment: try again on the next round */
            });
    }

    function whenText(item, now) {
        var start = startOf(item);
        var minutesLeft = Math.round((start - now) / 60000);
        if (item.all_day) {
            return item.date === localDate(now) ? "Today (all day)" : "Tomorrow (all day)";
        }
        if (minutesLeft <= 0) {
            return "Starting now (" + item.start + ")";
        }
        if (item.date !== localDate(now)) {
            return "Tomorrow at " + item.start;
        }
        if (minutesLeft < 60) {
            return "In " + minutesLeft + " minute" + (minutesLeft === 1 ? "" : "s") + " (" + item.start + ")";
        }
        return "Today at " + item.start;
    }

    function due(now) {
        var store = readStore();
        return items.filter(function (item) {
            var state = store[item.key];
            if (state === "done") {
                return false;
            }
            if (typeof state === "number" && state > now.getTime()) {
                return false; /* snoozed */
            }
            var start = startOf(item);
            var remindAt = new Date(start.getTime() - item.minutes * 60000);
            var showUntil = new Date(start.getTime() + SHOW_UNTIL_MINUTES_AFTER_START * 60000);
            return now >= remindAt && now <= showUntil;
        });
    }

    function close(item, snooze) {
        var store = readStore();
        store[item.key] = snooze ? Date.now() + SNOOZE_MINUTES * 60000 : "done";
        writeStore(store);
        if (open) {
            open.overlay.remove();
            if (open.returnFocus && open.returnFocus.focus) {
                open.returnFocus.focus();
            }
        }
        open = null;
        setTimeout(check, 300);
    }

    function show(item, now) {
        var overlay = document.createElement("div");
        overlay.className = "reminder-overlay";

        var box = document.createElement("div");
        box.className = "reminder-box";
        box.setAttribute("role", "alertdialog");
        box.setAttribute("aria-modal", "true");
        box.setAttribute("aria-labelledby", "reminder-title");
        box.setAttribute("aria-describedby", "reminder-when");

        var label = document.createElement("p");
        label.className = "reminder-label";
        label.textContent = "🔔 Reminder";

        var title = document.createElement("h2");
        title.id = "reminder-title";
        title.className = "reminder-title";
        if (item.energy) {
            title.classList.add("energy-" + item.energy);
        }
        title.textContent = item.title;

        var when = document.createElement("p");
        when.id = "reminder-when";
        when.className = "reminder-when";
        when.textContent = whenText(item, now);

        var actions = document.createElement("div");
        actions.className = "reminder-actions";

        var snooze = document.createElement("button");
        snooze.type = "button";
        snooze.className = "form-button";
        snooze.textContent = "Remind me in " + SNOOZE_MINUTES + " minutes";
        snooze.addEventListener("click", function () { close(item, true); });

        var ok = document.createElement("button");
        ok.type = "button";
        ok.className = "form-button form-button-primary";
        ok.textContent = "OK, got it";
        ok.addEventListener("click", function () { close(item, false); });

        actions.appendChild(snooze);
        actions.appendChild(ok);
        box.appendChild(label);
        box.appendChild(title);
        box.appendChild(when);
        box.appendChild(actions);
        overlay.appendChild(box);

        overlay.addEventListener("keydown", function (event) {
            if (event.key === "Escape") {
                close(item, true);
            } else if (event.key === "Tab") {
                /* keep keyboard focus inside the reminder */
                var first = snooze;
                var last = ok;
                if (event.shiftKey && document.activeElement === first) {
                    event.preventDefault();
                    last.focus();
                } else if (!event.shiftKey && document.activeElement === last) {
                    event.preventDefault();
                    first.focus();
                }
            }
        });

        open = { item: item, overlay: overlay, returnFocus: document.activeElement };
        document.body.appendChild(overlay);
        ok.focus();
    }

    function check() {
        if (open) {
            return;
        }
        var now = new Date();
        var list = due(now);
        if (list.length > 0) {
            list.sort(function (a, b) { return startOf(a) - startOf(b); });
            show(list[0], now);
        }
    }

    load();
    setInterval(function () {
        if (Date.now() - lastLoaded > 10 * 60000) {
            load();
        } else {
            check();
        }
    }, 20000);
    document.addEventListener("visibilitychange", function () {
        if (!document.hidden) {
            load();
        }
    });
})();
