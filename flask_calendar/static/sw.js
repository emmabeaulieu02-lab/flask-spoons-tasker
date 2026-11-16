/* Energy Calendar service worker: shows reminder notifications sent by the server,
 * even when the calendar is closed. It does not cache pages, so the calendar is
 * always up to date. */
self.addEventListener("install", function () {
    self.skipWaiting();
});

self.addEventListener("activate", function (event) {
    event.waitUntil(self.clients.claim());
});

self.addEventListener("push", function (event) {
    var data = {};
    try {
        data = event.data ? event.data.json() : {};
    } catch (error) {
        data = { title: "Reminder", body: event.data ? event.data.text() : "" };
    }
    var title = data.title || "Reminder";
    event.waitUntil(
        self.registration.showNotification(title, {
            body: data.body || "",
            tag: data.tag || undefined,
            icon: "/static/icons/icon-192.png",
            badge: "/static/icons/icon-192.png",
            data: { url: data.url || "/?view=week" }
        })
    );
});

self.addEventListener("notificationclick", function (event) {
    event.notification.close();
    var target = new URL((event.notification.data && event.notification.data.url) || "/?view=week", self.location.origin).href;
    event.waitUntil(
        self.clients.matchAll({ type: "window", includeUncontrolled: true }).then(function (windows) {
            for (var i = 0; i < windows.length; i++) {
                if ("focus" in windows[i]) {
                    return windows[i].focus().then(function (client) {
                        return client && "navigate" in client ? client.navigate(target) : client;
                    });
                }
            }
            return self.clients.openWindow ? self.clients.openWindow(target) : null;
        })
    );
});
