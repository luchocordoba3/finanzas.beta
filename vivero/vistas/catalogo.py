import pandas as pd
import streamlit as st

from core import ui
from core.constantes import AMBIENTES, TIPOS_CATEGORIA, UNIDADES
from core.models import Planta
from core.services import catalogo, importar, proveedores, stock

st.title("🏷️ Catálogo y precios")

with ui.sesion() as s:
    df = stock.tabla_productos(s, solo_activos=False)
    cats = pd.DataFrame([(c.id, c.nombre, c.tipo, c.margen_objetivo, c.activo) for c in catalogo.categorias(s, solo_activas=False)],
                        columns=["id", "nombre", "tipo", "margen_objetivo", "activo"])
    plantas = pd.DataFrame([(p.id, p.nombre_comun, p.nombre_cientifico, p.categoria_id, p.ambiente, p.cuidados, p.activo)
                            for p in catalogo.plantas(s, solo_activas=False)],
                           columns=["id", "nombre_comun", "nombre_cientifico", "categoria_id", "ambiente", "cuidados", "activo"])
    provs = {p.id: p.nombre for p in proveedores.listar(s)}

cats["activo"] = cats["activo"].astype(bool)
plantas["activo"] = plantas["activo"].astype(bool)
cat_nombre = dict(zip(cats["id"], cats["nombre"]))
cat_tipo = dict(zip(cats["id"], cats["tipo"]))
cat_activas = cats.loc[cats["activo"], "id"].tolist()
ubicaciones = sorted(u for u in df["ubicacion"].unique() if u)
planta_nombre = dict(zip(plantas["id"], plantas["nombre_comun"]))


def _prov(p):
    return "—" if p is None else provs.get(p, "—")


def _crear_producto(s, planta, datos, stock_inicial, costo, usuario_id):
    """`planta`: id de una ficha existente, texto con el nombre de una nueva, o None para insumos."""
    if planta is not None:
        p = catalogo.buscar_o_crear_planta(s, planta, datos.get("categoria_id")) if isinstance(planta, str) \
            else s.get(Planta, planta)
        datos |= {"planta_id": p.id, "nombre": p.nombre_comun, "categoria_id": datos.get("categoria_id") or p.categoria_id}
    elif datos.get("es_planta"):
        raise ValueError("Elegí la planta o escribí el nombre de una nueva.")
    datos.pop("es_planta", None)
    return catalogo.crear_producto(s, datos, stock_inicial, costo, usuario_id)


t_prod, t_nuevo, t_plantas, t_precios, t_cats, t_imp = st.tabs(
    ["Productos", "Nuevo producto", "Fichas de plantas", "Actualizar precios", "Categorías", "Importar desde Excel"])

with t_prod:
    c = st.columns([3, 2, 1.3], vertical_alignment="bottom")
    buscar = c[0].text_input("Buscar", placeholder="Nombre, presentación o código…", key="cat_buscar")
    filtro_cat = c[1].multiselect("Categorías", sorted(df["categoria"].unique()), placeholder="Todas", key="cat_filtro")
    inactivos = c[2].toggle("Ver inactivos", key="cat_inactivos")
    vista = df if inactivos else df[df["activo"]]
    if buscar:
        vista = vista[(vista["producto"] + " " + vista["codigo"]).str.contains(buscar, case=False, regex=False)]
    if filtro_cat:
        vista = vista[vista["categoria"].isin(filtro_cat)]
    vista = vista.assign(margen=((vista["precio"] - vista["costo_promedio"]) / vista["costo_promedio"] * 100)
                         .where(vista["costo_promedio"] > 0))
    ev = st.dataframe(vista[["producto", "categoria", "proveedor", "precio", "costo_promedio", "margen", "stock", "codigo"]],
                      hide_index=True, on_select="rerun", selection_mode="single-row", key="tabla_catalogo",
                      column_config={"producto": "Producto", "categoria": "Categoría", "proveedor": "Proveedor",
                                     "precio": ui.col_pesos("Precio ($)"), "costo_promedio": ui.col_pesos("Costo ($)"),
                                     "margen": st.column_config.NumberColumn("Margen s/costo", format="%.0f%%"),
                                     "stock": ui.col_cant("Stock"), "codigo": "Código"})
    if not ev.selection.rows:
        st.caption("Tocá un producto para editarlo.")
    else:
        p = vista.iloc[ev.selection.rows[0]]
        pid = int(p["id"])
        st.subheader(f"Editar: {p['producto']}")
        with st.form(f"editar_prod_{pid}"):
            c = st.columns(2)
            ids_cat = [i for i in cat_activas if cat_tipo[i] == (p["tipo"] or "planta")] or cat_activas
            datos = {
                "nombre": c[0].text_input("Nombre", p["nombre"]),
                "presentacion": c[1].text_input("Presentación", p["presentacion"]),
                "categoria_id": c[0].selectbox("Categoría", ids_cat, format_func=cat_nombre.get,
                                               index=ids_cat.index(p["categoria_id"]) if p["categoria_id"] in ids_cat else None),
                "proveedor_id": c[1].selectbox("Proveedor habitual", [None, *provs], format_func=_prov,
                                               index=([None, *provs].index(p["proveedor_id"]) if p["proveedor_id"] in provs else 0)),
            }
            c = st.columns(4)
            datos["precio"] = c[0].number_input("Precio de venta ($)", min_value=0.0, value=float(p["precio"]), step=100.0)
            datos["costo_promedio"] = c[1].number_input("Costo promedio ($)", min_value=0.0, value=float(p["costo_promedio"]),
                                                        step=100.0)
            datos["stock_minimo"] = c[2].number_input("Stock mínimo", min_value=0.0, value=float(p["stock_minimo"]),
                                                      step=1.0, format="%g")
            datos["unidad"] = c[3].selectbox("Unidad", UNIDADES, index=UNIDADES.index(p["unidad"]) if p["unidad"] in UNIDADES else 0)
            c = st.columns(3)
            datos["ubicacion"] = c[0].selectbox("Ubicación", ubicaciones, accept_new_options=True,
                                                index=ubicaciones.index(p["ubicacion"]) if p["ubicacion"] in ubicaciones else None) or ""
            datos["codigo"] = c[1].text_input("Código", p["codigo"])
            datos["activo"] = c[2].checkbox("Activo (se puede vender)", bool(p["activo"]))
            margen = p["margen_objetivo"] if pd.notna(p["margen_objetivo"]) else 0
            if p["costo_promedio"] > 0:
                st.caption(f"Precio sugerido con el margen de la categoría ({margen:g}%): "
                           f"{ui.pesos_md(catalogo.precio_sugerido(p['costo_promedio'], margen))}")
            if st.form_submit_button("Guardar cambios", type="primary", icon="💾"):
                ui.ejecutar(catalogo.actualizar_producto, pid, datos, ok="Producto actualizado")

with t_nuevo:
    tipo = st.segmented_control("¿Qué vas a cargar?", list(TIPOS_CATEGORIA), default="planta", key="np_tipo",
                                format_func={"planta": "🌿 Una planta", "insumo": "🧰 Un insumo o accesorio"}.get) or "planta"
    with st.form("nuevo_producto", clear_on_submit=True):
        c = st.columns(2)
        planta, nombre = None, ""
        if tipo == "planta":
            activas = plantas.loc[plantas["activo"], "id"].tolist()
            planta = c[0].selectbox("Planta", activas, format_func=lambda x: planta_nombre.get(x, str(x)), index=None,
                                    accept_new_options=True, placeholder="Elegí una o escribí una nueva")
        else:
            nombre = c[0].text_input("Nombre *", placeholder="Tierra fértil, maceta plástica…")
        presentacion = c[1].text_input("Presentación", placeholder="Maceta 14, plantín, bolsa 25 L…")
        ids_cat = [i for i in cat_activas if cat_tipo[i] == tipo]
        categoria = c[0].selectbox("Categoría", ids_cat, format_func=cat_nombre.get, index=None,
                                   placeholder="Si es una planta ya cargada, se toma la de su ficha")
        proveedor = c[1].selectbox("Proveedor habitual", [None, *provs], format_func=_prov)
        c = st.columns(4)
        precio = c[0].number_input("Precio de venta ($)", min_value=0.0, step=100.0)
        costo = c[1].number_input("Costo ($)", min_value=0.0, step=100.0)
        stock_inicial = c[2].number_input("Stock inicial", min_value=0.0, step=1.0, format="%g")
        minimo = c[3].number_input("Stock mínimo", min_value=0.0, step=1.0, format="%g",
                                   help="Cuando quede esto o menos, avisa para reponer. 0 = no avisar.")
        c = st.columns(3)
        ubicacion = c[0].selectbox("Ubicación", ubicaciones, index=None, accept_new_options=True,
                                   placeholder="Invernadero, sector, mesa…")
        unidad = c[1].selectbox("Unidad", UNIDADES)
        codigo = c[2].text_input("Código (opcional)")
        if st.form_submit_button("Crear producto", type="primary", icon="➕"):
            datos = {"nombre": nombre, "presentacion": presentacion, "categoria_id": categoria, "proveedor_id": proveedor,
                     "precio": precio, "stock_minimo": minimo, "ubicacion": ubicacion or "", "unidad": unidad,
                     "codigo": codigo, "es_planta": tipo == "planta"}
            ui.ejecutar(_crear_producto, planta, datos, stock_inicial, costo, ui.uid(), ok="Producto creado")

with t_plantas:
    st.caption("La ficha de cada planta: nombre científico, cuidados y ambiente. Sirve para las estadísticas por planta "
               "(sumando todas sus presentaciones) y para responder consultas.")
    ids_cat_planta = [i for i in cat_activas if cat_tipo[i] == "planta"]
    conteo = df[df["activo"]].groupby("planta_id").size()
    vista = plantas.assign(categoria=plantas["categoria_id"].map(cat_nombre).fillna(""),
                           productos=plantas["id"].map(conteo).fillna(0).astype(int))
    ev = st.dataframe(vista[["nombre_comun", "nombre_cientifico", "categoria", "ambiente", "productos"]], hide_index=True,
                      on_select="rerun", selection_mode="single-row", key="tabla_plantas",
                      column_config={"nombre_comun": "Nombre", "nombre_cientifico": "Nombre científico",
                                     "categoria": "Categoría", "ambiente": "Ambiente", "productos": "Presentaciones"})
    fila = vista.iloc[ev.selection.rows[0]] if ev.selection.rows else None
    st.markdown(f"**{'Editar ' + fila['nombre_comun'] if fila is not None else 'Nueva ficha'}**")
    with st.form(f"ficha_{fila['id'] if fila is not None else 'nueva'}", clear_on_submit=fila is None):
        c = st.columns(2)
        datos = {
            "nombre_comun": c[0].text_input("Nombre común *", fila["nombre_comun"] if fila is not None else ""),
            "nombre_cientifico": c[1].text_input("Nombre científico", fila["nombre_cientifico"] if fila is not None else ""),
            "categoria_id": c[0].selectbox("Categoría", ids_cat_planta, format_func=cat_nombre.get,
                                           index=ids_cat_planta.index(fila["categoria_id"])
                                           if fila is not None and fila["categoria_id"] in ids_cat_planta else None),
            "ambiente": c[1].selectbox("Ambiente", AMBIENTES, format_func=lambda a: a or "—",
                                       index=AMBIENTES.index(fila["ambiente"]) if fila is not None and fila["ambiente"] in AMBIENTES else 0),
            "cuidados": st.text_area("Cuidados (luz, riego, época de poda…)", fila["cuidados"] if fila is not None else "",
                                     height=80),
        }
        if fila is not None:
            datos["activo"] = st.checkbox("Activa", bool(fila["activo"]))
        if st.form_submit_button("Guardar ficha", type="primary", icon="💾"):
            ui.ejecutar(catalogo.guardar_planta, datos, int(fila["id"]) if fila is not None else None, ok="Ficha guardada")

with t_precios:
    st.caption("Para actualizar precios de a muchos (por ejemplo, por inflación o por una lista nueva del proveedor).")
    modo = st.radio("Cómo", ["Aumentar un porcentaje", "Llevar al precio sugerido por el margen de la categoría"],
                    horizontal=True, key="modo_precios")
    c = st.columns(3)
    filtro_cat = c[0].multiselect("Categorías", cat_activas, format_func=cat_nombre.get, placeholder="Todas", key="pr_cat")
    filtro_prov = c[1].multiselect("Proveedores", list(provs), format_func=provs.get, placeholder="Todos", key="pr_prov")
    paso = c[2].selectbox("Redondear hacia arriba a", [1, 10, 50, 100, 500, 1000], index=3, key="pr_paso",
                          format_func=lambda p: "Sin redondeo" if p == 1 else ui.pesos(p))
    base = df[df["activo"]]
    if filtro_cat:
        base = base[base["categoria_id"].isin(filtro_cat)]
    if filtro_prov:
        base = base[base["proveedor_id"].isin(filtro_prov)]
    if modo.startswith("Aumentar"):
        pct = st.number_input("Aumento (%) — negativo para bajar", min_value=-90.0, value=10.0, step=1.0, key="pr_pct")
        prev = catalogo.vista_previa_aumento(base, pct, paso)
    else:
        base = base[base["costo_promedio"] > 0]
        prev = base[["id", "producto", "categoria", "proveedor", "precio"]].assign(
            nuevo=[catalogo.redondear(catalogo.precio_sugerido(cst, m if pd.notna(m) else 0), paso)
                   for cst, m in zip(base["costo_promedio"], base["margen_objetivo"])])
    prev = prev.assign(diferencia=prev["nuevo"] - prev["precio"], aplicar=True)
    editado = st.data_editor(prev[["id", "producto", "categoria", "precio", "nuevo", "diferencia", "aplicar"]], hide_index=True,
                             disabled=["id", "producto", "categoria", "precio", "diferencia"], key="ed_precios",
                             column_config={"id": None, "producto": "Producto", "categoria": "Categoría",
                                            "precio": ui.col_pesos("Actual ($)"),
                                            "nuevo": st.column_config.NumberColumn("Nuevo ($)", min_value=0, format="localized"),
                                            "diferencia": ui.col_pesos("Diferencia ($)"),
                                            "aplicar": st.column_config.CheckboxColumn("Aplicar")})
    elegidos = editado[editado["aplicar"]]
    if st.button(f"Aplicar precios nuevos a {len(elegidos)} productos", type="primary", disabled=elegidos.empty):
        ui.ejecutar(catalogo.aplicar_precios, dict(zip(elegidos["id"], elegidos["nuevo"])),
                    ok=f"Precios actualizados en {len(elegidos)} productos")

with t_cats:
    st.caption("El margen objetivo se usa para sugerir precios a partir del costo.")
    editado = st.data_editor(cats, hide_index=True, disabled=["id"], key="ed_cats",
                             column_config={"id": None, "nombre": "Nombre",
                                            "tipo": st.column_config.SelectboxColumn("Tipo", options=list(TIPOS_CATEGORIA)),
                                            "margen_objetivo": st.column_config.NumberColumn("Margen objetivo (%)", min_value=0),
                                            "activo": st.column_config.CheckboxColumn("Activa")})

    def _guardar_cats(s, filas):
        for f in filas:
            margen = 0.0 if pd.isna(f["margen_objetivo"]) else float(f["margen_objetivo"])
            catalogo.guardar_categoria(s, str(f["nombre"] or ""), f["tipo"] or "planta", margen, int(f["id"]), bool(f["activo"]))

    if st.button("Guardar cambios de categorías", icon="💾"):
        ui.ejecutar(_guardar_cats, editado.to_dict("records"), ok="Categorías guardadas")
    with st.form("nueva_categoria", clear_on_submit=True):
        c = st.columns([3, 2, 2])
        nombre = c[0].text_input("Nueva categoría")
        tipo_cat = c[1].selectbox("Tipo", list(TIPOS_CATEGORIA), format_func=TIPOS_CATEGORIA.get)
        margen = c[2].number_input("Margen objetivo (%)", min_value=0.0, value=100.0, step=5.0)
        if st.form_submit_button("Agregar categoría"):
            ui.ejecutar(catalogo.guardar_categoria, nombre, tipo_cat, margen, ok="Categoría creada")

with t_imp:
    st.markdown("Cargá todo el catálogo de una vez, con su stock inicial. Columnas de la plantilla: "
                "**nombre** (obligatoria), presentacion, categoria, tipo (*planta* o *insumo*), precio, costo, stock, "
                "stock_minimo, ubicacion, proveedor, codigo, unidad, nombre_cientifico. "
                "Las categorías, proveedores y fichas de plantas que no existan se crean solas.")
    ui.importador("productos", importar.COLUMNAS_PRODUCTOS, importar.EJEMPLO_PRODUCTOS, importar.importar_productos,
                  usuario_id=ui.uid())
