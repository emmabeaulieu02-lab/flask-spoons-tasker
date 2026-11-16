/* Settings > Notifications on this tablet: turns reminder notifications on or off. */
(function () {
    "use strict";

    var panel = document.getElementById("push-panel");
    if (!panel) {
        return;
    }
    var status = document.getElementById("push-status");
    var iosHelp = document.getElementById("push-ios-help");
    var enableButton = document.getElementById("push-enable");
    var testButton = document.getElementById("push-test");
    var disableButton = document.getElementById("push-disable");

    var isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent) ||
        (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
    var isHomeScreenApp = window.matchMedia("(display-mode: standalone)").matches || window.navigator.standalone === true;
    var supported = "serviceWorker" in navigator && "PushManager" in window && "Notification" in window;

    function say(text) {
        status.textContent = text;
    }

    function showButtons(on) {
        enableButton.hidden = on;
        testButton.hidden = !on;
        disableButton.hidden = !on;
    }

    function keyBytes(base64) {
        var padding = "=".repeat((4 - base64.length % 4) % 4);
        var raw = window.atob((base64 + padding).replace(/-/g, "+").replace(/_/g, "/"));
        var bytes = new Uint8Array(raw.length);
        for (var i = 0; i < raw.length; i++) {
            bytes[i] = raw.charCodeAt(i);
        }
        return bytes;
    }

    function post(url, body) {
        return fetch(url, {
            method: "POST",
            credentials: "same-origin",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body || {})
        });
    }

    function registration() {
        return navigator.serviceWorker.register("/sw.js", { scope: "/" }).then(function () {
            return navigator.serviceWorker.ready;
        });
    }

    function refresh() {
        if (isIOS && !isHomeScreenApp) {
            say("To get notifications on an iPad, first add the calendar to the Home Screen:");
            iosHelp.hidden = false;
            enableButton.hidden = true;
            return;
        }
        if (!supported) {
            say("This browser can't show notifications. Reminders will still pop up while the calendar is open.");
            return;
        }
        if (Notification.permission === "denied") {
            say("Notifications are blocked for this app. To allow them, open the tablet's Settings, then Notifications, then Energy Calendar.");
            return;
        }
        registration().then(function (reg) {
            return reg.pushManager.getSubscription();
        }).then(function (subscription) {
            if (subscription && Notification.permission === "granted") {
                // Make sure the server still knows this tablet
                post(panel.dataset.subscribeUrl, subscription.toJSON());
                say("Notifications are on for this tablet.");
                showButtons(true);
            } else {
                say("Notifications are off.");
                showButtons(false);
            }
        }).catch(function () {
            say("Notifications are off.");
            showButtons(false);
        });
    }

    enableButton.addEventListener("click", function () {
        say("Turning on…");
        // The permission question must be asked straight from the tap
        Notification.requestPermission().then(function (permission) {
            if (permission !== "granted") {
                throw new Error("permission");
            }
            return Promise.all([registration(), fetch(panel.dataset.keyUrl, { credentials: "same-origin" }).then(function (r) { return r.json(); })]);
        }).then(function (results) {
            var reg = results[0];
            return reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: keyBytes(results[1].key) });
        }).then(function (subscription) {
            return post(panel.dataset.subscribeUrl, subscription.toJSON());
        }).then(function (response) {
            if (!response.ok) {
                throw new Error("save");
            }
            say("Notifications are on for this tablet. Tap “Send a test notification” to check.");
            showButtons(true);
        }).catch(function (error) {
            if (error && error.message === "permission") {
                say("Notifications were not allowed. To allow them, open the tablet's Settings, then Notifications, then Energy Calendar.");
            } else {
                say("Notifications could not be turned on. Please check the internet connection and try again.");
            }
            showButtons(false);
        });
    });

    testButton.addEventListener("click", function () {
        say("Sending a test…");
        post(panel.dataset.testUrl).then(function (r) { return r.json(); }).then(function (result) {
            say(result.sent > 0 ?
                "Test sent. It should appear in a few seconds (lock the tablet to see it on the Lock Screen)." :
                "The test could not be sent. Try turning notifications off and on again.");
        }).catch(function () {
            say("The test could not be sent. Please check the internet connection.");
        });
    });

    disableButton.addEventListener("click", function () {
        registration().then(function (reg) {
            return reg.pushManager.getSubscription();
        }).then(function (subscription) {
            if (!subscription) {
                return null;
            }
            var endpoint = subscription.endpoint;
            return subscription.unsubscribe().then(function () {
                return post(panel.dataset.unsubscribeUrl, { endpoint: endpoint });
            });
        }).then(function () {
            say("Notifications are off.");
            showButtons(false);
        });
    });

    refresh();
})();
