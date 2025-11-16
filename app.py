import streamlit as st
import streamlit_authenticator as stauth
import pandas as pd
import sqlite3
from datetime import time
from pathlib import Path
from PIL import Image
from utils import calcular_horas_semana, calcular_nomina

# ---------- Config general ----------
st.set_page_config("Nómina Restaurante", "👩‍🍳")
# ======= AUTENTICACIÓN =======
# Construimos el dict 'credentials' a partir de st.secrets
creds = {"usernames": {}}
for u in st.secrets["credentials"]["usernames"]:
    email = u["email"]
    creds["usernames"][email] = {
        "name": u["name"],
        "password": u["password"],  # hash bcrypt
    }

cookie_conf = st.secrets["cookie"]

# Crear el autenticador (API 0.4.x)
authenticator = stauth.Authenticate(
    credentials=creds,
    cookie_name=cookie_conf["name"],
    key=cookie_conf["key"],
    cookie_expiry_days=int(cookie_conf["expiry_days"]),
)

# Mostrar el formulario de login en el cuerpo principal
# Llama a login (no devuelve tupla en 0.4.x; usa session_state)
authenticator.login(
    location="main",
    fields={
        "Form name": "Iniciar sesión",
        "Username": "Email",
        "Password": "Contraseña",
        "Login": "Entrar",
    },
    key="login",  # clave para evitar choques de widgets
)

# Lee los valores desde session_state
auth_status = st.session_state.get("authentication_status", None)
username    = st.session_state.get("username", None)
name        = st.session_state.get("name", None)

# Manejo de estados (idéntico a antes)
if auth_status is False:
    st.error("Usuario o contraseña incorrectos.")
    st.stop()
elif auth_status is None:
    st.info("Por favor ingresa tus credenciales.")
    st.stop()
# Si es True, continuamos con el resto de la app


# Manejo de estados
if auth_status is False:
    st.error("Usuario o contraseña incorrectos.")
    st.stop()
elif auth_status is None:
    st.info("Por favor ingresa tus credenciales.")
    st.stop()

# Si llegó aquí, está autenticado

# Limpieza defensiva: elimina clave 'logout' si quedó de sesiones anteriores
if "logout" in st.session_state:
    del st.session_state["logout"]

# Botón de cierre de sesión (clave distinta)
authenticator.logout(button_name="Cerrar sesión", location="sidebar", key="logout_btn")
st.sidebar.success(f"Sesión iniciada: {name}")

# ======= FIN AUTENTICACIÓN =======

BASE_DIR = Path(__file__).parent.resolve()
DB_PATH = BASE_DIR / "data" / "payroll.db"
LOGO_PATH = BASE_DIR / "assets" / "logo.jpeg"   # cambia el nombre si tu archivo no es .png


# ---------- Conexión y tablas ----------
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    # Tabla principal
    conn.execute("""CREATE TABLE IF NOT EXISTS payroll (    
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT,
        cargo TEXT,
        tipo TEXT,
        valor_hora REAL,
        valor_cheque REAL,
        valor_cash REAL,
        horas_semana REAL,
        fecha_semana TEXT
    )""")
    # Tabla de turnos
    conn.execute("""CREATE TABLE IF NOT EXISTS shifts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        payroll_id INTEGER,
        dia TEXT,
        inicio TEXT,
        fin TEXT,
        FOREIGN KEY(payroll_id) REFERENCES payroll(id) ON DELETE CASCADE
    )""")
    return conn

conn = get_conn()

# ---------- Sidebar (logo centrado + selector de semana) ----------
with st.sidebar:
    col1, col2, col3 = st.columns([1, 3, 1])  # centra el logo
    if LOGO_PATH.exists():
        col2.image(str(LOGO_PATH), use_container_width=True)
    else:
        col2.write("No se encontró el logo.")
        st.caption(f"Ruta buscada: {LOGO_PATH}")
    st.markdown("---")

    st.header("📅 Semana")
    fecha_semana = st.date_input(
        "Seleccione lunes de la semana",
        value=pd.Timestamp.today().normalize(),
        key="semana_selector"
    )



# ---------- Tabs principales ----------
tabs = st.tabs(["Registrar", "Editar", "Resumen", "Asistente IA", "Cash/Cheque/Límite", "Administrador"])

# =======================
# TAB 1: REGISTRAR
# =======================
with tabs[0]:
    st.header("➕ Registrar nómina semanal")
    tipo = st.radio("Tipo de trabajador", ["Por horas", "Fijo"], horizontal=True)
    # ----- Nombre y Cargo (MISMA columna, uno debajo del otro) -----
    col_left, col_right = st.columns(2)

    with col_left:
        nombres_exist = pd.read_sql_query("SELECT DISTINCT nombre FROM payroll", conn)
        nombre = st.selectbox(
            "Nombre del trabajador",
            ["-- Nuevo --"] + nombres_exist["nombre"].tolist(),
            key="reg_nombre_sel"
        )
        if nombre == "-- Nuevo --":
            nombre = st.text_input("Escriba el nombre", key="reg_nombre_nuevo")

        cargo = st.selectbox(
            "Cargo",
            ["mesero", "dishwasher", "cocina", "jefe cocina", "administrador", "operativo"],
            key="reg_cargo"
        )

    # ----- Pagos a la derecha -----
    with col_right:
        if tipo == "Por horas":
            valor_hora = st.selectbox(
                "Valor por hora (USD)",
                [8, 9, 10, 11, 12, 13, 14, 15, 16, 18, 19, 20],
                key="reg_valor_hora"
            )
        else:
            valor_hora = 0.0

        valor_cheque = st.number_input("Valor cheque (USD)", min_value=0.0, key="reg_cheque")
        valor_cash   = st.number_input("Valor cash   (USD)", min_value=0.0, key="reg_cash")

    # ----- Horario a lo ancho (debajo de ambos) -----
    st.markdown("### 🕒 Horario semanal")
    dias = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
    horarios = {}
    for d in dias:
        descanso = st.checkbox(f"{d} descanso", key=f"reg_{d}_rest")
        if descanso:
            horarios[d] = (None, None)
        else:
            c1, c2 = st.columns(2)
            with c1:
                inicio = st.time_input(f"{d} Inicio", value=time(9, 0), key=f"reg_{d}_ini")
            with c2:
                fin = st.time_input(f"{d} Fin", value=time(17, 0), key=f"reg_{d}_fin")
            horarios[d] = (inicio, fin)

    # ----- Previsualización en vivo -----
    horas_preview, _ = calcular_horas_semana(horarios)
    if tipo == "Por horas":
        pago_preview = horas_preview * valor_hora
        st.info(f"⏱️ **{horas_preview:.2f} h** • 💵 Pago bruto: **${pago_preview:.2f}**", icon="💰")
    else:
        st.info(f"💰 Suma cheque+cash: **${valor_cheque + valor_cash:.2f}**", icon="💰")

    # ====== FORM MINIMAL (solo botón) ======
    with st.form("entrada_nomina"):
        submitted = st.form_submit_button("Guardar registro")
        if submitted:
            horas_sem, detalle = calcular_horas_semana(horarios)

            if tipo == "Fijo":
                total_ingresado = valor_cheque + valor_cash
                if total_ingresado == 0:
                    st.error("❗ Debes ingresar al menos cheque o cash (no puede ser 0 + 0).")
                    st.stop()
            else:
                base = valor_hora * horas_sem
                if valor_cheque > 0:
                    valor_cash = max(base - valor_cheque, 0)
                else:
                    valor_cash = base

            conn.execute("""
                INSERT INTO payroll
                (nombre, cargo, tipo, valor_hora, valor_cheque, valor_cash, horas_semana, fecha_semana)
                VALUES (?,?,?,?,?,?,?,?)""",
                (nombre, cargo, tipo, valor_hora, valor_cheque, valor_cash, horas_sem, fecha_semana.isoformat()))
            conn.commit()

            payroll_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            for dia, (ini, fin) in horarios.items():
                conn.execute(
                    "INSERT INTO shifts (payroll_id, dia, inicio, fin) VALUES (?,?,?,?)",
                    (payroll_id,
                     dia,
                     ini.strftime("%H:%M") if ini else None,
                     fin.strftime("%H:%M") if fin else None)
                )
            conn.commit()

            st.success(f"Registro guardado ({horas_sem:.2f} h) ✅")
            with st.expander("Detalle por día"):
                st.write(detalle)

            # Limpiar solo widgets de registro (los que empiezan con 'reg_')
            for k in list(st.session_state.keys()):
                if k.startswith("reg_"):
                    del st.session_state[k]

            st.rerun()  # se mantiene la fecha seleccionada

    # ----- Tabla de la semana (¡FUERA del form!) -----
    st.subheader("📊 Nómina de la semana seleccionada")
    df = pd.read_sql_query(
        "SELECT * FROM payroll WHERE fecha_semana = ?",
        conn, params=[fecha_semana.isoformat()]
    )

    if df.empty:
        st.info("Sin datos aún.")
    else:
        df["base_horas"] = df["horas_semana"] * df["valor_hora"]
        df["valor_cash_mostrado"] = df["valor_cash"]
        df["valor_cheque_mostrado"] = df["valor_cheque"]

        mask_horas = df["tipo"] == "Por horas"
        sin_cheque = (df["valor_cheque"] <= 0) & mask_horas
        df.loc[sin_cheque, "valor_cash_mostrado"] = df.loc[sin_cheque, "base_horas"]
        con_cheque = (df["valor_cheque"] > 0) & mask_horas
        df.loc[con_cheque, "valor_cash_mostrado"] = (
            df.loc[con_cheque, "base_horas"] - df.loc[con_cheque, "valor_cheque"]
        ).clip(lower=0)

        df["total_pago"] = df["valor_cheque_mostrado"] + df["valor_cash_mostrado"]

        cols = ["nombre", "cargo", "tipo", "horas_semana", "valor_hora",
                "valor_cheque_mostrado", "valor_cash_mostrado", "total_pago"]

        st.dataframe(
            df[cols].rename(columns={
                "valor_cheque_mostrado": "valor_cheque",
                "valor_cash_mostrado": "valor_cash"
            })
        )

        st.download_button(
            "⬇️ Descargar CSV",
            df[cols].to_csv(index=False).encode(),
            file_name=f"nomina_{fecha_semana}.csv",
            mime="text/csv",
            key=f"dl_{fecha_semana.isoformat()}"
        )



# =======================
# TAB 2: EDITAR
# =======================
with tabs[1]:
    st.header("✏️ Editar turnos diarios")

    nombres = pd.read_sql_query("SELECT DISTINCT nombre FROM payroll", conn)["nombre"].tolist()
    if not nombres:
        st.info("No hay registros todavía.")
        st.stop()

    nombre_sel = st.selectbox("Selecciona trabajador", nombres)

    semanas_df = pd.read_sql_query(
        "SELECT id, fecha_semana FROM payroll WHERE nombre = ?",
        conn, params=[nombre_sel]
    )
    semanas_df["rango"] = pd.to_datetime(semanas_df["fecha_semana"]).dt.strftime("%d %b") + " – " + \
        (pd.to_datetime(semanas_df["fecha_semana"]) + pd.Timedelta(days=6)).dt.strftime("%d %b")
    sem_opciones = dict(zip(semanas_df["rango"], semanas_df["id"]))
    semana_rango = st.selectbox("Selecciona semana", list(sem_opciones.keys()))
    payroll_id = sem_opciones[semana_rango]

    turnos = pd.read_sql_query(
        "SELECT * FROM shifts WHERE payroll_id = ? ORDER BY id",
        conn, params=[payroll_id]
    )

    # Tipo y pagos actuales (para mostrar y editar si es fijo)
    registro = pd.read_sql_query(
        "SELECT tipo, valor_cheque, valor_cash FROM payroll WHERE id = ?",
        conn, params=[payroll_id]
    ).iloc[0]

    with st.form(f"edit_shifts_{payroll_id}"):
        nuevos_horarios = {}

        for _, row in turnos.iterrows():
            dia = row["dia"]
            col1, col2, col3 = st.columns(3)
            with col1:
                descanso = st.checkbox(f"{dia} descanso",
                                       value=(row["inicio"] is None),
                                       key=f"d_{payroll_id}_{dia}")
            if descanso:
                nuevos_horarios[dia] = (None, None)
            else:
                ini_val = time.fromisoformat(row["inicio"]) if row["inicio"] else time(9, 0)
                fin_val = time.fromisoformat(row["fin"]) if row["fin"] else time(17, 0)
                with col2:
                    ini = st.time_input("Inicio", value=ini_val, key=f"i_{payroll_id}_{dia}")
                with col3:
                    fin = st.time_input("Fin", value=fin_val, key=f"f_{payroll_id}_{dia}")
                nuevos_horarios[dia] = (ini, fin)

        # Si es Fijo, permitir editar cheque/cash
        if registro["tipo"] == "Fijo":
            st.markdown("### 💵 Pago fijo")
            valor_cheque_e = st.number_input(
                "Valor cheque (USD)",
                value=float(registro["valor_cheque"]),
                key=f"cheque_edit_{payroll_id}"
            )
            valor_cash_e = st.number_input(
                "Valor cash (USD)",
                value=float(registro["valor_cash"]),
                key=f"cash_edit_{payroll_id}"
            )
        else:
            valor_cheque_e = float(registro["valor_cheque"])
            valor_cash_e = float(registro["valor_cash"])

        guardar_turnos = st.form_submit_button("Guardar cambios")

        if guardar_turnos:
            # Actualizar shifts
            for dia, (ini, fin) in nuevos_horarios.items():
                conn.execute(
                    "UPDATE shifts SET inicio = ?, fin = ? WHERE payroll_id = ? AND dia = ?",
                    (ini.strftime("%H:%M") if ini else None,
                     fin.strftime("%H:%M") if fin else None,
                     payroll_id, dia)
                )

            # Recalcular horas y actualizar payroll (y pago si es fijo)
            horas_sem, _ = calcular_horas_semana(nuevos_horarios)
            conn.execute(
                """UPDATE payroll
                   SET horas_semana = ?, valor_cheque = ?, valor_cash = ?
                   WHERE id = ?""",
                (horas_sem, valor_cheque_e, valor_cash_e, payroll_id)
            )
            conn.commit()
            st.success(f"Cambios guardados • Total semana: {horas_sem:.2f} h ✅")

# =======================
# TAB 3: RESUMEN
# =======================
with tabs[2]:
    st.header("📈 Resumen semanal")

    # Traer datos de la semana seleccionada
    df = pd.read_sql_query(
        "SELECT * FROM payroll WHERE fecha_semana = ?",
        conn, params=[fecha_semana.isoformat()]
    )

    if df.empty:
        st.info("No hay registros para la semana seleccionada.")
    else:
        # ---------- Normalizamos columnas auxiliares ----------
        # Base de pago por horas (horas * tarifa)
        df["base_horas"] = df["horas_semana"] * df["valor_hora"]

        # Total de pago: para Fijos ya está en (cheque+cash); para Por horas, total = base_horas
        df["total_pago"] = df["valor_cheque"] + df["valor_cash"]
        mask_horas = df["tipo"] == "Por horas"
        df.loc[mask_horas, "total_pago"] = df.loc[mask_horas, "base_horas"]

        # ---------- QUIÉN TRABAJÓ MÁS ----------
        st.subheader("⏱️ Quién trabajó más (ordenado de mayor a menor)")

        col_h1, col_h2 = st.columns(2)

        # Por horas
        with col_h1:
            st.markdown("**Por horas**")
            df_horas = df[df["tipo"] == "Por horas"].copy()
            if df_horas.empty:
                st.caption("No hay trabajadores por horas en esta semana.")
            else:
                st.dataframe(
                    df_horas.sort_values("horas_semana", ascending=False)[
                        ["nombre", "cargo", "horas_semana", "valor_hora", "total_pago"]
                    ].rename(columns={
                        "horas_semana": "horas",
                        "total_pago": "pago_total"
                    }),
                    use_container_width=True
                )

        # Fijos
        with col_h2:
            st.markdown("**Fijos**")
            df_fijos = df[df["tipo"] == "Fijo"].copy()
            if df_fijos.empty:
                st.caption("No hay trabajadores fijos en esta semana.")
            else:
                st.dataframe(
                    df_fijos.sort_values("horas_semana", ascending=False)[
                        ["nombre", "cargo", "horas_semana", "total_pago"]
                    ].rename(columns={
                        "horas_semana": "horas",
                        "total_pago": "pago_total"
                    }),
                    use_container_width=True
                )

        st.markdown("---")

        # ---------- QUIÉN GANÓ MÁS POR CARGO ----------
        st.subheader("💵 Quién ganó más en la semana — organizado por cargo")

        # Ordenamos por cargo y dentro de cada cargo por total_pago desc
        df_por_cargo = df.sort_values(["cargo", "total_pago"], ascending=[True, False])[
            ["cargo", "nombre", "tipo", "horas_semana", "total_pago"]
        ].rename(columns={
            "horas_semana": "horas",
            "total_pago": "pago_total"
        })

        st.dataframe(df_por_cargo, use_container_width=True)

        # (Opcional) Totales por cargo
        with st.expander("Ver totales por cargo"):
            totales_cargo = (
                df.groupby("cargo", as_index=False)["total_pago"]
                  .sum()
                  .sort_values("total_pago", ascending=False)
                  .rename(columns={"total_pago": "pago_total"})
            )
            st.dataframe(totales_cargo, use_container_width=True)

        # Botones de descarga
        col_d1, col_d2 = st.columns(2)
        with col_d1:
            st.download_button(
                "⬇️ Descargar 'Quién trabajó más'",
                df.sort_values("horas_semana", ascending=False)[
                    ["nombre", "cargo", "tipo", "horas_semana", "total_pago"]
                ].rename(columns={"horas_semana": "horas", "total_pago": "pago_total"}).to_csv(index=False).encode(),
                file_name=f"ranking_horas_{fecha_semana}.csv",
                mime="text/csv",
                key=f"dl_ranking_horas_{fecha_semana.isoformat()}"
            )
        with col_d2:
            st.download_button(
                "⬇️ Descargar 'Quién ganó más por cargo'",
                df_por_cargo.to_csv(index=False).encode(),
                file_name=f"ranking_por_cargo_{fecha_semana}.csv",
                mime="text/csv",
                key=f"dl_ranking_por_cargo_{fecha_semana.isoformat()}"
            )
# =======================
# TAB 4: ASISTENTE IA (Recomendaciones y explicaciones)
# =======================
with tabs[3]:
    st.header("🤖 Asistente IA — Recomendaciones de programación")

    # Parámetros
    st.caption("Usa el selector de la izquierda (sidebar) para elegir la semana base.")
    semanas_hist = st.number_input("Semanas de historial a considerar", min_value=1, max_value=12, value=4, step=1)
    limite_nomina = 9000.0
    umbral_alerta = 8500.0

    # Cargar historial (las N semanas previas a la seleccionada + la seleccionada)
    # Tomamos desde fecha_semana - semanas_hist*7 hasta fecha_semana (inclusive)
    fecha_inicio_hist = (pd.to_datetime(fecha_semana) - pd.Timedelta(weeks=semanas_hist)).normalize()
    df_hist = pd.read_sql_query(
        "SELECT * FROM payroll WHERE date(fecha_semana) BETWEEN ? AND ?",
        conn, params=[fecha_inicio_hist.date().isoformat(), fecha_semana.isoformat()]
    )

    if df_hist.empty:
        st.info("No hay suficientes datos históricos para generar recomendaciones.")
        st.stop()

    # Auxiliares
    df_hist["base_horas"] = df_hist["horas_semana"] * df_hist["valor_hora"]
    df_hist["total_pago"] = df_hist["valor_cheque"] + df_hist["valor_cash"]
    mask_horas = (df_hist["tipo"] == "Por horas")
    df_hist.loc[mask_horas, "total_pago"] = df_hist.loc[mask_horas, "base_horas"]

    # ====== 1) Insights rápidos ======
    st.subheader("📊 Insights rápidos (últimas semanas)")
    col_i1, col_i2, col_i3 = st.columns(3)

    # Ranking por horas totales recientes
    ranking_horas = (
        df_hist.groupby("nombre", as_index=False)
              .agg(rol=("cargo","last"), horas_totales=("horas_semana","sum"), tarifa_prom=("valor_hora","mean"))
              .sort_values("horas_totales", ascending=False)
    )
    # Quien ganó más (total_pago) recientes
    ranking_pago = (
        df_hist.groupby(["nombre","cargo"], as_index=False)
              .agg(pago_total=("total_pago","sum"))
              .sort_values("pago_total", ascending=False)
    )
    # Totales por cargo (pago)
    totales_cargo = (
        df_hist.groupby("cargo", as_index=False)
              .agg(pago_total=("total_pago","sum"), horas=("horas_semana","sum"))
              .sort_values("pago_total", ascending=False)
    )

    with col_i1:
        st.markdown("**Top por horas (global)**")
        st.dataframe(ranking_horas.head(10), use_container_width=True)
    with col_i2:
        st.markdown("**Top por pago (global)**")
        st.dataframe(ranking_pago.head(10), use_container_width=True)
    with col_i3:
        st.markdown("**Totales por cargo (global)**")
        st.dataframe(totales_cargo, use_container_width=True)

    st.markdown("---")

    # ====== 2) Recomendaciones por cargo ======
    st.subheader("🗓️ Recomendación de programación por cargo")

    # UI: cargo + cupos
    cargos_disponibles = sorted(df_hist["cargo"].dropna().unique().tolist())
    rec_cargo = st.selectbox("Selecciona cargo a programar", cargos_disponibles, key="ai_cargo_sel")
    cupos = st.number_input("¿Cuántas personas necesitas para ese cargo?", min_value=1, max_value=20, value=3, step=1)

    # Heurística de selección
    # Score alto = mejor candidato. Priorizamos:
    #  - Menos horas acumuladas recientes (balanceo) -> mayor puntaje
    #  - Menor tarifa por hora -> ligera preferencia
    #  - Si es "Fijo", lo tratamos con costo fijo promedio de sus semanas recientes
    df_cargo_hist = df_hist[df_hist["cargo"] == rec_cargo].copy()
    if df_cargo_hist.empty:
        st.warning("No hay historial para ese cargo.")
    else:
        # Agregar métricas por persona (en el historial)
        agg = (
            df_cargo_hist.groupby(["nombre","tipo"], as_index=False)
                         .agg(
                             horas_ult=("horas_semana","sum"),
                             horas_sem_prom=("horas_semana","mean"),
                             tarifa_prom=("valor_hora","mean"),
                             pago_prom=("total_pago","mean")
                         )
        )

        # Normalizaciones simples
        # Evitar división por cero: si todos tienen mismas horas, sumamos un epsilon
        eps = 1e-6
        max_hrs = max(agg["horas_ult"].max(), eps)
        max_tar = max(agg["tarifa_prom"].max(), eps)

        # Score = w1*(1 - norm_horas) + w2*(1 - norm_tarifa)
        # w1 > w2 para priorizar balanceo de horas
        w1, w2 = 0.7, 0.3
        agg["score"] = w1 * (1 - (agg["horas_ult"] / max_hrs)) + w2 * (1 - (agg["tarifa_prom"] / max_tar))

        # Ordenar por score y tomar top "cupos"
        recomendados = agg.sort_values("score", ascending=False).head(int(cupos)).copy()

        # Estimar costo para la semana objetivo:
        # - Por horas: horas_semana estimadas = max(horas_sem_prom, 20) como base simple (ajústalo a tu realidad)
        # - Fijo: costo estimado = pago_prom
        def costo_estimado(row):
            if row["tipo"] == "Por horas":
                horas_est = max(row["horas_sem_prom"], 20.0)  # ← puedes cambiar este mínimo
                return horas_est * row["tarifa_prom"]
            else:
                return row["pago_prom"]

        recomendados["costo_estimado_semana"] = recomendados.apply(costo_estimado, axis=1)

        st.markdown("**Sugerencia de personal para la semana objetivo:**")
        st.dataframe(
            recomendados[["nombre","tipo","horas_ult","horas_sem_prom","tarifa_prom","pago_prom","score","costo_estimado_semana"]]
            .rename(columns={
                "horas_ult":"horas_recientes",
                "horas_sem_prom":"horas_semana_prom",
                "tarifa_prom":"tarifa_prom_usd_h",
                "pago_prom":"pago_prom_semanal",
                "costo_estimado_semana":"costo_est_semana_usd"
            }),
            use_container_width=True
        )

        # Advertencia de presupuesto con estos recomendados
        costo_equipo = float(recomendados["costo_estimado_semana"].sum())
        st.metric("Costo estimado (solo este cargo)", f"${costo_equipo:,.2f}")

        if costo_equipo > limite_nomina:
            st.error("🚨 Con esta selección ya **excedes** el límite de $9,000.")
        elif costo_equipo >= umbral_alerta:
            st.warning("⚠️ Con esta selección **te acercas** al límite de $9,000.")

        # Descarga CSV
        st.download_button(
            "⬇️ Descargar recomendación (CSV)",
            recomendados.to_csv(index=False).encode(),
            file_name=f"recomendacion_{rec_cargo}_{fecha_semana}.csv",
            mime="text/csv",
            key=f"dl_ai_recom_{rec_cargo}_{fecha_semana.isoformat()}"
        )

    st.markdown("---")
    # Explicación del criterio
    with st.expander("¿Cómo se calculan estas recomendaciones?"):
        st.write(
            """
            • Se usa el historial de las últimas *N* semanas (configurable) para cada trabajador del cargo elegido.  
            • El **score** prioriza:  
              - **Balanceo**: más puntaje para quien **ha trabajado menos** recientemente.  
              - **Costo**: ligera preferencia por tarifas más bajas.  
            • El **costo estimado**:
              - Para **Por horas** = horas_semana_prom (mínimo 20 h por defecto) × tarifa_prom.  
              - Para **Fijos** = pago_prom semanal histórico.  
            • Puedes ajustar los pesos `w1` y `w2`, y el mínimo de horas estimadas.
            """
        )


# =======================
# TAB 5: CASH / CHEQUE / LÍMITE
# =======================
with tabs[4]:
    st.header("💵 Cash / 🧾 Cheque / 🎯 Límite")

    LIMITE = 9000.0
    UMBRAL_ADVERTENCIA = 8500.0

    # Traer la nómina de la semana seleccionada
    df_lim = pd.read_sql_query(
        "SELECT * FROM payroll WHERE fecha_semana = ?",
        conn, params=[fecha_semana.isoformat()]
    )

    if df_lim.empty:
        st.info("No hay registros para la semana seleccionada.")
    else:
        # Base y reglas de visualización para "Por horas"
        df_lim["base_horas"] = df_lim["horas_semana"] * df_lim["valor_hora"]
        df_lim["valor_cash_mostrado"] = df_lim["valor_cash"].astype(float)
        df_lim["valor_cheque_mostrado"] = df_lim["valor_cheque"].astype(float)

        mask_horas = df_lim["tipo"] == "Por horas"

        # Sin cheque => todo en cash
        sin_cheque = (df_lim["valor_cheque"] <= 0) & mask_horas
        df_lim.loc[sin_cheque, "valor_cash_mostrado"] = df_lim.loc[sin_cheque, "base_horas"]

        # Con cheque => cash = base - cheque (no negativo)
        con_cheque = (df_lim["valor_cheque"] > 0) & mask_horas
        df_lim.loc[con_cheque, "valor_cash_mostrado"] = (
            df_lim.loc[con_cheque, "base_horas"] - df_lim.loc[con_cheque, "valor_cheque"]
        ).clip(lower=0)

        total_cash = float(df_lim["valor_cash_mostrado"].sum())
        total_cheque = float(df_lim["valor_cheque_mostrado"].sum())
        gran_total = total_cash + total_cheque

        c1, c2, c3 = st.columns(3)
        c1.metric("Total CASH", f"${total_cash:,.2f}")
        c2.metric("Total CHEQUE", f"${total_cheque:,.2f}")
        c3.metric("GRAN TOTAL", f"${gran_total:,.2f}")

        # Alertas por límite
        if gran_total > LIMITE:
            st.error("🚨 **Pasaste el límite de $9,000 para la nómina.**")
        elif gran_total >= UMBRAL_ADVERTENCIA:
            st.warning("⚠️ **Estás cerca a $9,000 (tu límite final). ¡Cuidado!**")

        st.markdown("### Detalle por trabajador")
        tabla_lim = (
            df_lim[["nombre", "cargo", "tipo", "horas_semana", "valor_hora",
                    "valor_cheque_mostrado", "valor_cash_mostrado"]]
            .rename(columns={
                "valor_cheque_mostrado": "valor_cheque",
                "valor_cash_mostrado": "valor_cash"
            })
        )
        st.dataframe(tabla_lim, use_container_width=True)

        st.download_button(
            "⬇️ Descargar resumen (CSV)",
            tabla_lim.to_csv(index=False).encode(),
            file_name=f"cash_cheque_limite_{fecha_semana}.csv",
            mime="text/csv",
            key=f"dl_cash_cheque_{fecha_semana.isoformat()}"
        )

# =======================
# TAB 6: ADMINISTRADOR
# =======================
with tabs[5]:
    st.header("🗑️ Administrador - Eliminar registros")

    nombres_admin = pd.read_sql_query("SELECT DISTINCT nombre FROM payroll", conn)["nombre"].tolist()
    if not nombres_admin:
        st.info("Aún no hay registros.")
        st.stop()

    nombre_admin = st.selectbox("Selecciona trabajador", nombres_admin, key="admin_trabajador")

    sem_admin_df = pd.read_sql_query(
        "SELECT id, fecha_semana, horas_semana FROM payroll WHERE nombre = ?",
        conn, params=[nombre_admin]
    )
    sem_admin_df["rango"] = pd.to_datetime(sem_admin_df["fecha_semana"]).dt.strftime("%d %b") + " – " + \
        (pd.to_datetime(sem_admin_df["fecha_semana"]) + pd.Timedelta(days=6)).dt.strftime("%d %b")

    if sem_admin_df.empty:
        st.warning("Ese trabajador no tiene semanas registradas.")
        st.stop()

    sem_opc = dict(zip(sem_admin_df["rango"], sem_admin_df["id"]))
    semana_sel = st.selectbox("Selecciona semana a eliminar", list(sem_opc.keys()), key="admin_semana")
    payroll_id_del = sem_opc[semana_sel]

    st.write("Horas registradas esa semana:",
             sem_admin_df.loc[sem_admin_df["id"] == payroll_id_del, "horas_semana"].values[0])

    if st.button("❌ Eliminar este registro"):
        conn.execute("DELETE FROM payroll WHERE id = ?", (payroll_id_del,))
        conn.commit()
        st.success("Registro eliminado ✅")
        st.rerun()
