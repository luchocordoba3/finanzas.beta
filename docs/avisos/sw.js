// Service worker de los avisos del vivero: muestra las notificaciones y al tocarlas abre el sistema.
self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (evento) => evento.waitUntil(self.clients.claim()));

self.addEventListener("push", (evento) => {
  let datos = {};
  try {
    datos = evento.data ? evento.data.json() : {};
  } catch (e) {
    datos = { body: evento.data ? evento.data.text() : "" };
  }
  evento.waitUntil(
    self.registration.showNotification(datos.title || "Vivero", {
      body: datos.body || "",
      icon: "icono-192.png",
      badge: "insignia.png",
      tag: datos.tag || undefined,
      data: { url: datos.url || "" },
    })
  );
});

self.addEventListener("notificationclick", (evento) => {
  evento.notification.close();
  const url = (evento.notification.data && evento.notification.data.url) || "./";
  evento.waitUntil(self.clients.openWindow(url));
});
