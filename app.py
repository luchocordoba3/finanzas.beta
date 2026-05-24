import streamlit as st
import pandas as pd
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
import os
import calendar

# --- CONFIGURACIÓN DE ARCHIVOS Y LOGIN ---
CREDENTIALS_FILE = "usuarios_credenciales.csv"

def cargar_credenciales():
    if os.path.exists(CREDENTIALS_FILE):
        return pd.read_csv(CREDENTIALS_FILE, dtype={'Usuario': str, 'PIN': str})
    return pd.DataFrame(columns=['Usuario', 'PIN'])

def guardar_credencial(usuario, pin):
    df_cred = cargar_credenciales()
    nueva_cred = pd.DataFrame([{'Usuario': usuario, 'PIN': str(pin)}])
    df_cred = pd.concat([df_cred, nueva_cred], ignore_index=True)
    df_cred.to_csv(CREDENTIALS_FILE, index=False)

# Inicializar estados de sesión
if 'autenticado' not in st.session_state:
    st.session_state.autenticado = False
if 'usuario_actual' not in st.session_state:
    st.session_state.usuario_actual = None

st.set_page_config(page_title="Finanzas Pro IA", layout="wide")

# --- PANTALLA DE LOGIN / REGISTRO ---
if not st.session_state.autenticado:
    st.title("🔐 Finanzas Pro IA - Control de Acceso")
    st.markdown("Bienvenido. Ingresá tu nombre para acceder a tu panel privado.")
    
    col_login, _ = st.columns([1, 2])
    with col_login:
        nombre_input = st.text_input("Nombre de Usuario").strip()
        
        if nombre_input:
            df_cred = cargar_credenciales()
            usuario_existe = nombre_input in df_cred['Usuario'].values
            
            if usuario_existe:
                st.info(f"Hola {nombre_input}, ingresá tu clave para iniciar sesión.")
                pin_input = st.text_input("PIN Numérico (4 dígitos)", type="password", max_chars=4)
                
                if st.button("Iniciar Sesión"):
                    pin_guardado = df_cred[df_cred['Usuario'] == nombre_input]['PIN'].values[0]
                    if str(pin_input) == str(pin_guardado):
                        st.session_state.autenticado = True
                        st.session_state.usuario_actual = nombre_input
                        st.rerun()
                    else:
                        st.error("PIN incorrecto. Intentá de nuevo.")
            else:
                st.warning(f"El usuario '{nombre_input}' no existe. Podés registrarlo ahora mismo.")
                pin_nuevo = st.text_input("Creá tu PIN Numérico (4 dígitos)", type="password", max_chars=4)
                pin_confirmar = st.text_input("Confirmá tu PIN", type="password", max_chars=4)
                
                if st.button("Crear Cuenta y Registrarse"):
                    if len(pin_nuevo) == 4 and pin_nuevo.isdigit():
                        if pin_nuevo == pin_confirmar:
                            guardar_credencial(nombre_input, pin_nuevo)
                            st.success("¡Cuenta creada con éxito! Ahora ingresá tu PIN para iniciar sesión.")
                            st.rerun()
                        else:
                            st.error("Los PINs no coinciden.")
                    else:
                        st.error("El PIN debe ser estrictamente de 4 números.")
    st.stop() # Detiene la ejecución para que no vean el dashboard si no están logueados

# --- SI ESTÁ AUTENTICADO, ARRANCA LA APLICACIÓN ---
usuario = st.session_state.usuario_actual
archivo_usuario = f"finanzas_{usuario.lower().replace(' ', '_')}.csv"

def cargar_datos(archivo):
    if os.path.exists(archivo):
        return pd.read_csv(archivo, parse_dates=['Fecha'])
    return pd.DataFrame(columns=['Fecha', 'Detalle', 'Monto', 'Categoría', 'Tipo', 'Billetera'])

def guardar_datos(df, archivo):
    df.to_csv(archivo, index=False)

if 'db' not in st.session_state or st.session_state.get('archivo_actual') != archivo_usuario:
    st.session_state.db = cargar_datos(archivo_usuario)
    st.session_state.archivo_actual = archivo_usuario

st.title("📊 Finanzas Pro IA - Tu Oficina al Volante")

# --- SIDEBAR: REGISTRO Y PERFIL ---
with st.sidebar:
    st.markdown(f"### 👤 Sesión activa: **{usuario}**")
    if st.button("🔒 Cerrar Sesión"):
        st.session_state.autenticado = False
        st.session_state.usuario_actual = None
        st.rerun()
        
    st.markdown("---")
    st.header("Registrar Movimiento")
    tipo = st.selectbox("Tipo de Operación", ["Gasto Efectivo/Débito", "Ingreso", "Tarjeta de Crédito"])
    detalle = st.text_input("Detalle (Ej: Combustible, Supermercado)")
    monto = st.number_input("Monto ($ / USD)", min_value=0.0, step=100.0)
    categoria = st.selectbox("Categoría", ["Combustible", "Comida", "Salud", "Hogar", "Sueldo", "Otros"])
    fecha_gasto = st.date_input("Fecha de Operación", date.today())

    if tipo == "Tarjeta de Crédito":
        tarjeta_elegida = st.selectbox("¿Qué tarjeta usaste?", ["Visa", "American Express", "Mastercard", "Otra"])
        cuotas = st.number_input("Cantidad de cuotas", min_value=1, max_value=24, value=1)
        dia_cierre = st.number_input("Día de Cierre", min_value=1, max_value=31, value=25)
        dia_vencimiento = st.number_input("1er Vencimiento (Día)", min_value=1, max_value=31, value=10)
        
        tiene_segundo_venc = st.checkbox("¿Tiene 2do Vencimiento?")
        if tiene_segundo_venc:
            dia_segundo_vencimiento = st.number_input("2do Vencimiento (Día)", min_value=1, max_value=31, value=15)
            
        origen_dinero = tarjeta_elegida
    else:
        billetera = st.selectbox("Origen / Destino", ["Efectivo", "Banco", "Mercado Pago", "AstroPay"])
        origen_dinero = billetera

    if st.button("Guardar Registro"):
        nuevos_registros = []
        
        if tipo == "Tarjeta de Crédito":
            monto_cuota = monto / cuotas
            inicio_pago = fecha_gasto
            if fecha_gasto.day > dia_cierre:
                inicio_pago += relativedelta(months=2)
            else:
                inicio_pago += relativedelta(months=1)
            
            for i in range(cuotas):
                fecha_mes_cuota = inicio_pago + relativedelta(months=i)
                ultimo_dia_mes = calendar.monthrange(fecha_mes_cuota.year, fecha_mes_cuota.month)[1]
                dia_real = min(dia_vencimiento, ultimo_dia_mes)
                fecha_cuota = fecha_mes_cuota.replace(day=dia_real)
                
                texto_venc = f" (Vence el {dia_vencimiento}"
                if tiene_segundo_venc:
                    texto_venc += f" o {dia_segundo_vencimiento})"
                else:
                    texto_venc += ")"
                    
                nuevos_registros.append({
                    'Fecha': fecha_cuota,
                    'Detalle': f"{detalle} (Cuota {i+1}/{cuotas}){texto_venc}",
                    'Monto': -monto_cuota,
                    'Categoría': categoria,
                    'Tipo': 'Tarjeta',
                    'Billetera': origen_dinero
                })
        else:
            valor_monto = monto if tipo == "Ingreso" else -monto
            nuevos_registros.append({
                'Fecha': fecha_gasto,
                'Detalle': detalle,
                'Monto': valor_monto,
                'Categoría': categoria,
                'Tipo': tipo,
                'Billetera': origen_dinero
            })
        
        nuevo_df = pd.DataFrame(nuevos_registros)
        st.session_state.db = pd.concat([st.session_state.db, nuevo_df], ignore_index=True)
        guardar_datos(st.session_state.db, archivo_usuario)
        st.success("¡Registro guardado correctamente!")

# --- CUERPO PRINCIPAL: DASHBOARD ---
df = st.session_state.db

hoy = datetime.now()
if not df.empty:
    df['Fecha'] = pd.to_datetime(df['Fecha'])
    mes_actual = df[df['Fecha'].dt.month == hoy.month]
else:
    mes_actual = df

st.markdown(f"### 📂 Viendo el panel privado de: **{usuario}**")

col1, col2, col3 = st.columns(3)
with col1:
    total_ingresos = df[df['Monto'] > 0]['Monto'].sum() if not df.empty else 0
    total_gastos = df[df['Monto'] < 0]['Monto'].sum() if not df.empty else 0
    st.metric("Balance Total", f"${total_ingresos + total_gastos:,.2f}")

with col2:
    gastos_mes = mes_actual[mes_actual['Monto'] < 0]['Monto'].sum() if not mes_actual.empty else 0
    st.metric("Gastos del Mes", f"${abs(gastos_mes):,.2f}", delta_color="inverse")

with col3:
    if not df.empty:
        pagos_pendientes = df[df['Fecha'] > pd.Timestamp(hoy.date())]['Monto'].sum()
    else:
        pagos_pendientes = 0
    st.metric("Comprometido a Futuro", f"${abs(pagos_pendientes):,.2f}")

st.subheader("Últimos Movimientos")
st.dataframe(df.sort_values(by='Fecha', ascending=False) if not df.empty else df, use_container_width=True)

if not df.empty:
    st.subheader("Gastos por Categoría")
    gastos_solo = df[df['Monto'] < 0]
    st.bar_chart(gastos_solo.groupby('Categoría')['Monto'].sum().abs())