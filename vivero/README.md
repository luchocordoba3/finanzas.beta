# 🌱 Sistema de gestión para vivero

Aplicación web (Streamlit + base de datos) para llevar el día a día y la administración de un vivero entre dos socios.

**Día a día**
- **Inicio**: panel de alertas: pedidos atrasados o para hoy, faltantes de stock para pedidos, encargos que llegaron, stock bajo mínimo, compras por recibir, pagos a proveedores, clientes que deben, recordatorios y avisos de temporada.
- **Vender**: carrito con buscador, descuentos, medios de pago, cuenta corriente y comprobante en PDF (no fiscal).
- **Pedidos y encargos**: seña, fecha de entrega, estados (pendiente → listo → entregado) y "encargar" lo que falta al proveedor.
- **Clientes**: ficha con historial, total comprado, cuenta corriente y cobros.
- **Stock**: disponible y comprometido en pedidos, pérdidas con motivo, conteos, ubicación y movimientos.
- **Recordatorios**: tareas para uno, para el otro o para los dos, con repetición semanal o mensual.

**Administración**
- **Compras**: listas de compras por proveedor, texto para mandar el pedido, recepción (suma stock y recalcula el costo promedio) y pagos.
- **Proveedores**, **Catálogo y precios** (fichas de plantas, aumento masivo por %, precio sugerido por margen, importación desde Excel).
- **Estadísticas de ventas** y **de plantas**: más vendidas, márgenes, días y horarios fuertes, clientes, stock parado, pérdidas y temporadas.
- **Producción propia** (opcional, se activa en Configuración): lotes de semillas o esquejes, etapas, pérdidas y pase a stock.
- **Configuración**: datos del vivero, días de aviso, medios de pago, usuarios y copia de seguridad en Excel.

## Probarlo en la computadora

```bash
pip install -r vivero/requirements.txt
python vivero/seed_demo.py          # opcional: carga un año de datos de ejemplo
streamlit run vivero/app.py
```

Sin configurar nada, los datos se guardan en `vivero/vivero.db` (SQLite). Con los datos de ejemplo, los usuarios son `ana` / `vivero123` y `juan` / `vivero123`. Si arrancás sin datos de ejemplo, la primera pantalla te pide crear tu usuario.

## Ponerlo en internet (gratis) para usarlo desde la PC y el celular

1. **Base de datos**: creá una cuenta en [neon.tech](https://neon.tech) y un proyecto en una región de Estados Unidos (por ejemplo AWS US East). En el proyecto tocá **Connect** y copiá la dirección que empieza con `postgresql://`. No la compartas: es la llave de tus datos.
2. **App**: entrá a [share.streamlit.io](https://share.streamlit.io) con GitHub y tocá **Create app** → *Deploy a public app from GitHub*. Elegí **Paste GitHub URL** y pegá:
   `https://github.com/luchocordoba3/finanzas.beta/blob/main/vivero/app.py`
   En **App URL** elegí el nombre de la dirección. En **Advanced settings → Secrets** pegá (la versión de Python dejala como viene):
   ```toml
   DATABASE_URL = "postgresql://usuario:clave@servidor/neondb?sslmode=require"
   ```
   **Save** y después **Deploy**.
3. Abrí la app, creá tu usuario y, en **Configuración → Usuarios**, el de tu socio/a. En **Configuración → Copia de seguridad** tiene que decir "Base de datos en la nube".
4. En el celular: abrí la dirección y usá "Agregar a pantalla de inicio".

- Las tablas se crean solas. Si falta `DATABASE_URL` o está mal copiada, la app no arranca y muestra cómo arreglarlo. En la nube nunca usa el archivo local, porque ahí se borraría.
- Si la página de Streamlit muestra "Oops, something went wrong", desactivá el traductor automático de Chrome para ese sitio y recargá.
- **No** corras `seed_demo.py` contra la base de producción.

## Primeros pasos recomendados

1. **Configuración**: nombre, dirección y teléfono del vivero (salen en el comprobante), medios de pago y días de aviso.
2. **Catálogo y precios → Importar desde Excel**: bajá la plantilla, completala con tus productos (con stock, costo y stock mínimo) y subila.
3. **Clientes → Importar**: lo mismo con la lista de clientes.
4. **Proveedores**: completá teléfono, días de entrega y condiciones de pago.
5. Una vez por semana, **Configuración → Copia de seguridad**.

## Notificaciones

Llegan como las de cualquier app, con el nombre y el ícono del vivero, aunque el sistema esté cerrado: **pedido nuevo, encargo que llegó, producto que se agota, recordatorio que te dejaron** y un **resumen a las 8 de la mañana**. Son gratis (Web Push: las entregan Google, Apple y Mozilla) y no hace falta ninguna app de terceros.

1. **Publicar la página de activación** (una vez): en GitHub, *Settings → Pages → Deploy from a branch → main, carpeta /docs → Save*. La página vive en `docs/avisos/` (`https://luchocordoba3.github.io/finanzas.beta/avisos/`).
2. **En cada celular o PC**: **Configuración → Notificaciones → Activar en este dispositivo → Activar notificaciones → Permitir**. En iPhone (iOS 16.4 o más), primero *Compartir → Agregar a inicio* y activar desde el ícono.
3. **Resumen de las 8** (una vez): secreto `DATABASE_URL` en GitHub (*Settings → Secrets and variables → Actions*). Lo manda `.github/workflows/vivero-resumen-diario.yml`.

Detalles técnicos: el cifrado (RFC 8291) y la firma VAPID (RFC 8292) están en `core/services/push.py`, hechos con `cryptography`. Las claves se generan solas y quedan en la base, fuera de la copia de seguridad. Los dispositivos dados de baja se borran solos.
**Telegram** queda como canal opcional, en la misma pantalla.

## WhatsApp a clientes

Botones que abren WhatsApp con el mensaje ya escrito (vos solo tocás enviar, sin costo): en **Pedidos** (pedido listo, recordar la entrega, llegó el encargo), en **Inicio** (encargos que llegaron, clientes que deben) y en la **ficha del cliente**. Los teléfonos pueden estar cargados como sea (`11 5555-1234`, `011 15…`, `+54 9…`); los que no tienen código de área usan el de **Configuración → Avisos y opciones**.

## A tener en cuenta

- Si recargás la página, hay que volver a ingresar.
- El comprobante no es una factura. La facturación electrónica de ARCA/AFIP no está incluida.
- En el plan gratis de Streamlit, si la app pasa un tiempo sin usarse se "duerme" y tarda unos segundos en volver.

## Para desarrolladores

```
vivero/
  app.py              login y menú (st.navigation)
  core/models.py      tablas (SQLAlchemy)
  core/services/      lógica de negocio sin Streamlit: stock, ventas, pedidos, compras, alertas, estadísticas…
  core/ui.py          sesión de base de datos, formatos y componentes compartidos
  core/graficos.py    gráficos Altair
  vistas/             una pantalla por archivo
  tests/              pytest: servicios + todas las pantallas con AppTest
```

- Tests: `pip install pytest && python -m pytest vivero` (con la configuración de `vivero/pytest.ini`).
- Todo cambio de stock pasa por `services/stock.mover`, que deja el movimiento registrado.
- Las escrituras desde las pantallas van por `ui.ejecutar`, que confirma la transacción antes de recargar la página.
- Fechas en hora de Argentina (`core/tiempo.py`): Streamlit Cloud corre en UTC.
