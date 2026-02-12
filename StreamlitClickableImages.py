import streamlit as st
from streamlit_image_coordinates import streamlit_image_coordinates
import pandas as pd
from PIL import Image, ImageDraw
import gspread
import folium
from folium.plugins import Draw
from streamlit_folium import st_folium
from folium.raster_layers import ImageOverlay
import io
import altair as alt
from datetime import datetime



# --- 1. CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(
    page_title="Leak Hunter | Monitoring",
    page_icon="🏭",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 2. CONEXIÓN GSHEET ---
@st.cache_resource
def conectar_gsheet():
    try:
        credentials = st.secrets["gcp_service_account"]
        gc = gspread.service_account_from_dict(credentials)
        sh = gc.open_by_url("https://docs.google.com/spreadsheets/d/1on_gy_rcoLHiU-jlEisvArr38v90Nwuj_SysnooEuTY/edit#gid=0")
        return sh.get_worksheet(0)
    except: return None

sheet = conectar_gsheet()

def cargar_datos():
    if sheet:
        data = sheet.get_all_records()
        # Actualizamos columnas esperadas
        columnas_esperadas = [
            'x1', 'y1', 'x2', 'y2', 'Zona', 'TipoFuga', 'Area', 'Ubicacion',
            'ID_Maquina', 'Severidad', 'Categoria', 'L_min', 'CostoAnual', 'Estado'
        ]
        if data:
            df = pd.DataFrame(data)
            for col in columnas_esperadas:
                if col not in df.columns:
                    df[col] = "N/A"
            return df
        return pd.DataFrame(columns=columnas_esperadas)
    return pd.DataFrame()

if 'dfZonas' not in st.session_state:
    st.session_state.dfZonas = cargar_datos()


# --- 3. DIÁLOGO DE EDICIÓN ACTUALIZADO ---
@st.dialog("✏️ Editar Registro")
def editar_registro(index, datos_actuales):
    st.write(f"Modificando ID: {index}")
    col_ed1, col_ed2 = st.columns(2)

    # Identificamos qué fluido tiene este registro
    fluido_reg = datos_actuales.get('TipoFuga', 'Aire')
    dict_edit = RELACION_FUGAS.get(fluido_reg, RELACION_FUGAS["Aire"])
    cat_list_edit = list(dict_edit.keys())

    with col_ed1:
        nuevo_n = st.text_input("Nombre Zona", value=str(datos_actuales['Zona']))
        cat_val = datos_actuales.get('Categoria', 'Fuga A')

        # Validamos que la categoría exista para ese fluido
        idx_ed = cat_list_edit.index(cat_val) if cat_val in cat_list_edit else 0
        nueva_cat = st.selectbox("Categoría", cat_list_edit, index=idx_ed)

        nueva_medida = dict_edit[nueva_cat]["l_min"]
        st.text_input("I/min", value=nueva_medida, disabled=True)

    with col_ed2:
        nuevo_a = st.text_input("Área", value=str(datos_actuales.get('Area', 'N/A')))
        nueva_sev = st.select_slider("Severidad", options=["Baja", "Media", "Alta"], value=datos_actuales.get('Severidad', 'Media'))

        nuevo_costo = dict_edit[nueva_cat]["costo"]
        st.text_input("Costo por año (USD)", value=str(nuevo_costo), disabled=True)
        ubi_index = 0 if datos_actuales.get('Ubicacion') == "Terrestre" else 1
        nueva_ubi = st.radio("Tipo de Instalación", ["Terrestre", "Aérea"], index=ubi_index, horizontal=True)

        nuevo_estado = st.selectbox("Estado", ["En proceso de reparar", "Dañada", "Completada"],
                                  index=["En proceso de reparar", "Dañada", "Completada"].index(datos_actuales.get('Estado', 'Dañada')) if datos_actuales.get('Estado') in ["En proceso de reparar", "Dañada", "Completada"] else 1)

    if st.button("💾 Guardar Cambios"):
        fila_num = index + 2
        sheet.update_cell(fila_num, 5, nuevo_n)
        sheet.update_cell(fila_num, 7, nuevo_a)
        sheet.update_cell(fila_num, 10, nueva_sev)
        sheet.update_cell(fila_num, 11, nueva_cat)
        sheet.update_cell(fila_num, 12, nueva_medida)
        sheet.update_cell(fila_num, 13, nuevo_costo)
        sheet.update_cell(fila_num, 14, nuevo_estado)
        st.success("¡Actualizado!")
        st.session_state.dfZonas = cargar_datos()
        st.rerun()

## ventana emergente de planop de referencia  ###
@st.dialog("📥 Descargar Plano de Alta Resolución")
def dialogo_descarga_plano():
    st.write("Para una ubicación precisa sin pixelado, descarga el plano maestro en 16K.")
    st.warning("Nota: El archivo es pesado debido a su alta resolución.")

    with open("layout completo.png", "rb") as file:
        btn = st.download_button(
            label="💾 Descargar Plano Maestro (16K)",
            data=file,
            file_name="Plano_Maestro_Hanon_16K.png",
            mime="image/png",
            use_container_width=True
        )
    if btn:
        st.success("Descarga iniciada. Ábrelo en tu visualizador de imágenes para máximo zoom.")


# --- 4. CONFIGURACIÓN VISUAL ---
# --- Configuarcion de formulas de categorias por fluido ---
RELACION_FUGAS = {
    "Aire": {
        "Fuga A": {"l_min": "0.1-10", "costo": 60},
        "Fuga B": {"l_min": "10.1-20", "costo": 300},
        "Fuga C": {"l_min": "20.1-30", "costo": 680},
        "Fuga D": {"l_min": "30.1-40", "costo": 890},
        "Fuga E": {"l_min": "40.1-50", "costo": 1090},
    },
    "Helio": {
        "Fuga A": {"l_min": "0.1-17", "costo": 13200},
        "Fuga B": {"l_min": "17.1-32", "costo": 26400},
        "Fuga C": {"l_min": "33.1-50", "costo": 132000},
    },

    "Aceite": {
        "Fuga A": {"l_min": ".002-0.004", "costo": 2181.17},
        "Fuga B": {"l_min": "0.004-0.01", "costo": 10905.48},
        "Fuga C": {"l_min": "0.01-.1", "costo": 109058.40},
    },
    "Gas Natural": {
    "Fuga A": {"l_min": "1-50", "costo": 450},    # Fuga pequeña en conexión
    "Fuga B": {"l_min": "51-150", "costo": 1800},  # Fuga en sello de válvula
    "Fuga C": {"l_min": "151-500", "costo": 5200}, # Fuga en tubería principal
    },
    # --- NUEVO ESTADO: INSPECCIÓN (OK) ---
    "Inspección (OK)": {
        "Sin Fuga": {"l_min": "0", "costo": 0}
    }
}

# Definimos listas iniciales basadas en "Aire" para evitar el KeyError al cargar
categorias_list = list(RELACION_FUGAS["Aire"].keys())
medidas_list = [v["l_min"] for v in RELACION_FUGAS["Aire"].values()]
costos_list = [v["costo"] for v in RELACION_FUGAS["Aire"].values()]

FLUIDOS = {
    "Aire": {"color": "#0000FF", "emoji": "💨", "marker": "blue"},
    "Gas": {"color": "#FFA500", "emoji": "🔥", "marker": "orange"},
    "Agua": {"color": "#00FFFF", "emoji": "💧", "marker": "cadetblue"},
    "Helio": {"color": "#FF00FF", "emoji": "🎈", "marker": "purple"},
    "Aceite": {"color": "#FFFF00", "emoji": "🛢️", "marker": "darkred"},
    "Inspección (OK)": {"color": "#28A745", "emoji": "✅", "marker": "green"}  # Nuevo
}

img_original = Image.open("PlanoHanon.webp")
ancho_real, alto_real = img_original.size

# --- 5. SIDEBAR ---
with st.sidebar:
    try: st.image("EA_2.png", use_container_width=True)
    except: st.error("Logo no encontrado")
    st.markdown("<h2 style='text-align: center;'>🏭 Leak Hunter</h2>", unsafe_allow_html=True)
    filtro_fluidos = st.multiselect("Monitorear:", list(FLUIDOS.keys()), default=list(FLUIDOS.keys()))
    # --- NUEVOS FILTROS GLOBALES ---
    # 1. Filtro por Estado
    estados_disponibles = sorted(st.session_state.dfZonas['Estado'].unique())
    filtro_estados = st.multiselect("Estado de Fuga:", estados_disponibles, default=estados_disponibles)

    # 2. Filtro por Área de Planta
    areas_disponibles = sorted(st.session_state.dfZonas['Area'].unique())
    filtro_areas = st.multiselect("Área de Planta:", areas_disponibles, default=areas_disponibles)

    # 3. Filtro por Rango de Fechas (Basado en la columna 'Zona')
    st.info("📅 El filtro de fechas aplica al registro guardado.")
    # Nota: Como guardamos la fecha en la columna 'Zona', este filtro es textual
    # Para un filtrado de fecha exacto, se requeriría procesar el string de 'Zona'
    busqueda_fecha = st.text_input("🔍 Buscar Fecha (ej: 2026)")

    st.success("Conexión: Cloud Sync ✅")

    # --- FIRMA DE AUTOR (Movida al Sidebar) ---
    st.markdown(f"""
        <div style='text-align: center; padding: 20px; border: 1px solid #2d323d; border-radius: 15px; background-color: #161a22; margin-top: 20px;'>
            <p style='margin: 0; font-size: 0.9em; color: #888;'>Developed by:</p>
            <p style='margin: 5px 0; font-weight: bold; font-size: 1.2em; color: #5271ff;'>Master Engineer Erik Armenta</p>
            <p style='margin: 0; font-style: italic; font-size: 0.8em; color: #444;'>Innovating Digital Twins for Industrial Excellence</p>
        </div>
    """, unsafe_allow_html=True)

# --- Lógica de Triple Filtrado ---
df_filtrado = st.session_state.dfZonas[
    (st.session_state.dfZonas['TipoFuga'].isin(filtro_fluidos)) &
    (st.session_state.dfZonas['Estado'].isin(filtro_estados)) &
    (st.session_state.dfZonas['Area'].isin(filtro_areas))
]

# Aplicar búsqueda de fecha si el usuario escribió algo
if busqueda_fecha:
    df_filtrado = df_filtrado[df_filtrado['Zona'].str.contains(busqueda_fecha, case=False, na=False)]

# --- 6. TABS ---
tabMapa, tabConfig, tabReporte = st.tabs(["📍 Mapa", "⚙️ Gestión", "📊 Reporte"])

with tabMapa:
    # --- MÉTRICAS ACTUALIZADAS ---
    m1, m2, m3, m4, m5 = st.columns(5) # Añadimos m5
    
    with m1: 
        st.metric("Hallazgos Totales", len(df_filtrado))
    
    with m2:
        alta_count = len(df_filtrado[df_filtrado['Severidad'] == 'Alta'])
        st.metric("🚨 Prioridad Alta", alta_count)
    
    with m3:
        # IMPACTO TOTAL (General)
        costo_total = pd.to_numeric(df_filtrado['CostoAnual'], errors='coerce').sum()
        st.metric("💰 Impacto Total", f"${costo_total:,.0f} USD")
        
    with m4:
        # NUEVA MÉTRICA: AHORRO GENERADO (Solo 'Completada')
        df_completadas = df_filtrado[df_filtrado['Estado'] == 'Completada']
        ahorro_real = pd.to_numeric(df_completadas['CostoAnual'], errors='coerce').sum()
        st.metric("✅ Ahorro Generado", f"${ahorro_real:,.0f} USD", delta="¡Buen trabajo!", delta_color="normal")

    with m5:
        # IMPACTO PENDIENTE (Dañadas + En proceso)
        df_pendientes = df_filtrado[df_filtrado['Estado'] != 'Completada']
        costo_pendiente = pd.to_numeric(df_pendientes['CostoAnual'], errors='coerce').sum()
        st.metric("⏳ Por Mitigar", f"${costo_pendiente:,.0f} USD", delta=f"-{len(df_pendientes)} fugas", delta_color="inverse")

    st.markdown("---")



    # --- 2. INYECCIÓN DE CSS PARA ANIMACIÓN (Brinco/Pulso) ---
    # Esto hace que los iconos con la clase 'brinca-peppo' tengan movimiento
    marker_style = """
    <style>
    @keyframes bounce {
        0%, 20%, 50%, 80%, 100% {transform: translateY(0);}
        40% {transform: translateY(-10px);}
        60% {transform: translateY(-5px);}
    }
    .brinca-peppo {
        animation: bounce 2s infinite;
    }
    </style>
    """
    st.markdown(marker_style, unsafe_allow_html=True)

    # --- 3. CONFIGURACIÓN DEL MAPA (Zoom Libre) ---
    m = folium.Map(
        location=[alto_real / 2, ancho_real / 2],
        zoom_start=-1, # Inicio con vista general
        crs="Simple",
        min_zoom=-2,   # Permite alejar para ver todo el plano
        max_zoom=4     # Permite mucho acercamiento
    )

    ImageOverlay(
        image="PlanoHanon.webp",
        bounds=[[0, 0], [alto_real, ancho_real]],
        opacity=0.8
    ).add_to(m)

    # --- NUEVO: CAPA DE ZONAS INSPECCIONADAS (Tab 1) ---
    # Renderizamos rectángulos verdes para las zonas marcadas como "Inspección (OK)"
    inspecciones = df_filtrado[df_filtrado['TipoFuga'] == "Inspección (OK)"]
    if not inspecciones.empty:
        for _, row_ins in inspecciones.iterrows():
            factor_x = ancho_real / 1200
            factor_y = alto_real / (1200 * (alto_real / ancho_real))
            
            p1_map = [alto_real - (row_ins['y2'] * factor_y), row_ins['x1'] * factor_x]
            p2_map = [alto_real - (row_ins['y1'] * factor_y), row_ins['x2'] * factor_x]
            
            folium.Rectangle(
                bounds=[p1_map, p2_map],
                color="#28A745",
                weight=1,
                fill=True,
                fill_opacity=0.2, # Baja opacidad para no tapar mucho
                tooltip=f"Zona Inspeccionada: {row_ins['Area']}"
            ).add_to(m)

# --- 4. RENDERIZADO DE MARCADORES ---
    for i, row in df_filtrado.iterrows():
        factor_x, factor_y = ancho_real / 1200, alto_real / (1200 * (alto_real / ancho_real))
        cx, cy = (row['x1'] + row['x2']) / 2 * factor_x, alto_real - ((row['y1'] + row['y2']) / 2 * factor_y)

        f_info = FLUIDOS.get(row['TipoFuga'], {"color": "white", "marker": "red", "emoji": "⚠️"})
        color_sev = {"Alta": "#FF4B4B", "Media": "#FFA500", "Baja": "#28A745"}.get(row['Severidad'], "#333")

        # --- LÓGICA DE UBICACIÓN ---
        ubi = row.get('Ubicacion', 'Terrestre') # 'Ubicacion' debe ser el nombre de tu columna en GSheets
        ubi_emoji = "🚜" if ubi == "Terrestre" else "☁️"

        # Tooltip Elegante (Actualizado con Ubicación)
        hover_html = f"""
        <div style="background-color:#1d2129; color:white; padding:10px; border-radius:8px; border-left:5px solid {f_info['color']}; min-width:150px;">
            <b>{f_info['emoji']} {row['Area']}</b><br>
            <span style="color:#bdc3c7; font-size:0.85em;">{ubi_emoji} Instalación: {ubi}</span><br>
            <span style="color:{color_sev}; font-size:0.9em;">Severidad: {row['Severidad']}</span>
        </div>"""

# Popup (Clic) - Cambiamos "Zona" por "Área de Planta"
        # Popup (Clic) - Cambiamos "Zona" por "Área de Planta" y añadimos ID MAQUINA
        popup_content = f"""
        <div style="font-family: 'Segoe UI', sans-serif; color: #333; min-width: 250px;">
            <h4 style="margin:0 0 10px 0; color:{f_info['color']}; border-bottom: 2px solid {color_sev};">📋 Ficha Técnica</h4>
            <table style="width:100%; font-size: 13px; border-spacing: 0 5px;">
                <tr><td><b>ID Máquina:</b></td><td><b>{row.get('ID_Maquina', 'N/A')}</b></td></tr>
                <tr><td><b>Área de Planta:</b></td><td>{row['Area']}</td></tr>
                <tr><td><b>Instalación:</b></td><td>{ubi_emoji} {ubi}</td></tr>
                <tr><td><b>Estado:</b></td><td><b>{row.get('Estado', 'N/A')}</b></td></tr>
                <tr><td><b>Categoría:</b></td><td>{row.get('Categoria', 'N/A')}</td></tr>
                <tr><td><b>Caudal:</b></td><td>{row.get('L_min', 'N/A')} I/min</td></tr>
                <tr><td><b>Costo/Año:</b></td><td style="color:#d9534f; font-weight:bold;">${row.get('CostoAnual', '0')} USD</td></tr>
                <tr><td><b>Severidad:</b></td><td style="color:{color_sev}; font-weight:bold;">{row['Severidad']}</td></tr>
                <tr><td><b>Fechas:</b></td><td>{row['Zona']}</td></tr>
            </table>
        </div>
        """

        # Crear el Icono
        # Si es Severidad Alta, le añadimos la clase 'brinca-peppo' para que salte
        clase_css = "brinca-peppo" if row['Severidad'] == "Alta" else ""
        
        # --- ICONOGRAFÍA DINÁMICA ---
        # Por defecto info-sign. Si está completada o es inspección OK, usamos ok-sign (check)
        icono_mapa = "info-sign"
        if row['Estado'] == "Completada" or row['TipoFuga'] == "Inspección (OK)":
            icono_mapa = "ok-sign" # Check verde

        # Si es Inspección (OK), no queremos marcador, o sí? 
        # El user pide "Zonas Inspeccionadas" como rectángulos (ya hecho arriba), 
        # pero si está en el grid, quizás quiera ver el punto central también.
        # "Visualización: En el mapa de gestión (Tab 2), las zonas inspeccionadas deben renderizarse con un rectángulo verde sólido" -> Esto es para Tab 2 (Config/mapa 2), pero el user dijo "Tab 2...". 
        # Espera, punto 3 dice "Tab 'Mapa' ... Implementa la capa de 'Zonas Inspeccionadas' en el Tab 1".
        # Asumimos que también se dibujan marcadores normales para mantener consistencia, solo que verdes.

        folium.Marker(
            location=[cy, cx],
            popup=folium.Popup(popup_content, max_width=350),
            tooltip=folium.Tooltip(hover_html),
            icon=folium.Icon(color=f_info['marker'], icon=icono_mapa, extra_params=f'class="{clase_css}"')
        ).add_to(m)

    st_folium(m, width=1400, height=750, use_container_width=True)



with tabConfig:
    st.markdown("##### 1. Referencia de Alta Precisión (16K)")

    col_btn_1, col_btn_2 = st.columns([1, 2])
    with col_btn_1:
        if st.button("🔍 Obtener Plano 16K", use_container_width=True):
            dialogo_descarga_plano()
    with col_btn_2:
        st.info("Descarga el plano original para ver detalles técnicos sin pixelado antes de marcar.")

    st.markdown("---")
    st.markdown("##### 2. Localización y Recorte")
    st.info("Basándote en el plano de arriba, dibuja el área de la fuga aquí:")

    # --- CONFIGURACIÓN DEL MAPA DINÁMICO (Draw) ---
    m2 = folium.Map(
        location=[alto_real / 2, ancho_real / 2],
        zoom_start=-1,
        crs="Simple",
        min_zoom=-2,
        max_zoom=4
    )

    ImageOverlay(
        image="PlanoHanon.webp",
        bounds=[[0, 0], [alto_real, ancho_real]],
        opacity=1
    ).add_to(m2)

    # --- INICIO: CAPA DE MEMORIA (Zonas ya registradas) ---
    # Dibujamos lo que ya existe en el DataFrame para no encimar registros
    if not st.session_state.dfZonas.empty:
        for i, row in st.session_state.dfZonas.iterrows():
            try:
                # Revertimos la escala de 1200px a la escala real del plano
                factor_x = ancho_real / 1200
                factor_y = alto_real / (1200 * (alto_real / ancho_real))

                # Coordenadas Folium (Invertidas en Y)
                # p1: Top-Left, p2: Bottom-Right
                p1_map = [alto_real - (row['y1'] * factor_y), row['x1'] * factor_x]
                p2_map = [alto_real - (row['y2'] * factor_y), row['x2'] * factor_x]

                # Usamos el color del fluido para identificar la zona
                f_color = FLUIDOS.get(row['TipoFuga'], {"color": "gray"})['color']

                folium.Rectangle(
                    bounds=[p1_map, p2_map],
                    color=f_color,
                    weight=2,
                    fill=True,
                    fill_opacity=0.3,
                    tooltip=f"Ya registrado: {row['Area']} ({row['TipoFuga']})"
                ).add_to(m2)
            except:
                continue
    # --- FIN: CAPA DE MEMORIA ---

    # Configuración de herramientas de dibujo
    draw = Draw(
        export=False,
        position='topleft',
        draw_options={
            'polyline': False,
            'polygon': False,
            'circle': False,
            'marker': False,
            'circlemarker': False,
            'rectangle': True,
        },
        edit_options={'edit': False}
    )
    draw.add_to(m2)

    # Capturamos la salida del mapa con dibujo
    # Nota: mantenemos el key original "draw_map"
    output = st_folium(m2, width=1200, height=600, key="draw_map")

    coords_dibujadas = None
    if output["all_drawings"]:
        # Tomamos el último dibujo (el que el usuario acaba de hacer)
        last_draw = output["all_drawings"][-1]
        geometry = last_draw['geometry']
        if geometry['type'] == 'Polygon':
            # ... (Toda tu lógica de conversión de coordenadas se mantiene exactamente igual)
            lons = [p[0] for p in geometry['coordinates'][0]]
            lats = [p[1] for p in geometry['coordinates'][0]]

            x_min_map = min(lons)
            x_max_map = max(lons)
            y_min_map = min(lats)
            y_max_map = max(lats)

            scale_factor = 1200 / ancho_real

            x1_stored = x_min_map * scale_factor
            x2_stored = x_max_map * scale_factor
            y1_stored = (alto_real - y_max_map) * scale_factor
            y2_stored = (alto_real - y_min_map) * scale_factor

            coords_dibujadas = {
                'x1': x1_stored,
                'y1': y1_stored,
                'x2': x2_stored,
                'y2': y2_stored
            }
            st.success(f"Zona capturada: ({int(x1_stored)}, {int(y1_stored)}) - ({int(x2_stored)}, {int(y2_stored)})")

    st.markdown("---")
    # FORMULARIO EXTENDIDO
    # --- REEMPLAZAR EN TAB_CONFIG ---
    col1, col2, col3 = st.columns(3)
    with col1:
            t_f = st.selectbox("Fluido", list(FLUIDOS.keys()))

            # CAMBIO: Reemplazamos Nombre de Zona por Fechas
            f_inicio = st.date_input("📅 Fecha de Inicio", value=datetime.now())
            f_termino = st.date_input("📅 Fecha Estimada Término", value=datetime.now())

            # Convertimos las fechas a texto para guardarlas en GSheets
            n_z = f"{f_inicio.strftime('%d/%m/%Y')} - {f_termino.strftime('%d/%m/%Y')}"

            dict_actual = RELACION_FUGAS.get(t_f, RELACION_FUGAS["Aire"])
            cat_list_dinamica = list(dict_actual.keys())
            cat_f = st.selectbox("Categoría Critica", cat_list_dinamica)

    with col2:
        id_m = st.text_input("ID Equipo / Máquina")
        area_p = st.text_input("Área Planta")

        # Estos valores se actualizan solos al cambiar el fluido o la categoría
        med_f = dict_actual[cat_f]["l_min"]
        st.selectbox("I/min (Estimación)", [med_f], index=0, disabled=True)

    with col3:
        sev_p = st.select_slider("Severidad Visual", options=["Baja", "Media", "Alta"], value="Media")

        cost_f = dict_actual[cat_f]["costo"]
        st.selectbox("Costo por año (USD)", [cost_f], index=0, disabled=True)
        tipo_ubicacion = st.radio("Tipo de Instalación", ["Terrestre", "Aérea"], horizontal=True)
        
        # Lógica para Estado según Fluido
        opciones_estado = ["En proceso de reparar", "Dañada", "Completada"]
        if t_f == "Inspección (OK)":
            opciones_estado = ["Completada"] # Si es inspección, por defecto está OK/Completada
            
        est_f = st.selectbox("Estado Inicial", opciones_estado, index=len(opciones_estado)-1)

    if st.button("🚰📝 Record leak", use_container_width=True):
            if coords_dibujadas and n_z:
                # Creamos la lista para enviar a la fila
                # IMPORTANTE: Reemplazamos "N/A" por tipo_ubicacion
                fila_a_guardar = [
                    coords_dibujadas['x1'], coords_dibujadas['y1'],
                    coords_dibujadas['x2'], coords_dibujadas['y2'],
                    n_z,             # Columna E: Zona
                    t_f,             # Columna F: TipoFuga
                    area_p,          # Columna G: Area
                    tipo_ubicacion,  # Columna H: Ubicacion (ANTES DECÍA "N/A")
                    id_m,            # Columna I: ID_Maquina
                    sev_p,           # Columna J: Severidad
                    cat_f,           # Columna K: Categoria
                    med_f,           # Columna L: L_min
                    cost_f,          # Columna M: CostoAnual
                    est_f            # Columna N: Estado
                ]

                sheet.append_row(fila_a_guardar)
                st.session_state.dfZonas = cargar_datos()
                st.success(f"✅ Fuga en {n_z} ({tipo_ubicacion}) registrada.")
                st.rerun()
    else:
        st.warning("⚠️ Asegúrate de dibujar el área y poner un nombre a la zona.")

    st.subheader("📋 Historial de Gestión")
    
    # --- FILTROS LOCALES PARA GESTIÓN ---
    col_f1, col_f2, col_f3 = st.columns([2, 1, 1])
    with col_f1:
        search_query = st.text_input("🔍 Buscar en Historial (ID, Zona, Máquina...)", placeholder="Escribe para filtrar...")
    with col_f2:
        filtro_area_gest = st.multiselect("Filtrar Área", sorted(st.session_state.dfZonas['Area'].unique()), key="f_area_gest")
    with col_f3:
        filtro_estado_gest = st.multiselect("Filtrar Estado", sorted(st.session_state.dfZonas['Estado'].unique()), key="f_estado_gest")

    # Aplicamos filtros locales
    df_gestion = st.session_state.dfZonas.copy()
    if search_query:
        df_gestion = df_gestion[
            df_gestion.apply(lambda row: search_query.lower() in str(row.values).lower(), axis=1)
        ]
    if filtro_area_gest:
        df_gestion = df_gestion[df_gestion['Area'].isin(filtro_area_gest)]
    if filtro_estado_gest:
        df_gestion = df_gestion[df_gestion['Estado'].isin(filtro_estado_gest)]

    # --- OPTIMIZACIÓN: RENDERIZADO AL 50% SI NO HAY FILTROS ---
    # "Solo renderizamos la mitad y la otra mitad a través del filtro"
    if not search_query and not filtro_area_gest and not filtro_estado_gest:
        limit_regs = int(len(df_gestion) / 2)
        if limit_regs > 0:
            # Mostramos los MÁS RECIENTES (tail)
            df_gestion = df_gestion.tail(limit_regs)
            st.caption(f"ℹ️ Mostrando los {limit_regs} registros más recientes. Usa los filtros para ver más antiguos.")

    # --- RENDERIZADO EN GRID (Parrilla) ---
    # Usamos st.columns(3) dentro del bucle
    if not df_gestion.empty:
        cols = st.columns(3)
        for i, (idx, r) in enumerate(df_gestion.iterrows()):
            with cols[i % 3]: # Distribución cíclica en 3 columnas
                # Definimos color/borde según estado
                border_color = "#28a745" if r['Estado'] == "Completada" or r['TipoFuga'] == "Inspección (OK)" else "#d9534f" if r['Estado'] == "Dañada" else "#f0ad4e"
                
                with st.container(border=True):
                    # Header de la tarjeta
                    c_head1, c_head2 = st.columns([3,1])
                    with c_head1: st.markdown(f"**{r['Zona']}**")
                    with c_head2: st.markdown(f"<span style='color:{border_color}; font-size:1.5em;'>●</span>", unsafe_allow_html=True)
                    
                    try:
                        # Imagen pequeña
                        img_hist = img_original.resize((1200, int(1200*alto_real/ancho_real)))
                        st.image(img_hist.crop((r['x1'], r['y1'], r['x2'], r['y2'])), use_container_width=True)
                    except: st.caption("No image")
                    
                    st.caption(f"🆔 {r['ID_Maquina']} | 📍 {r['Area']}")
                    st.write(f"**Estado:** {r['Estado']}")
                    
                    # Botones de Acción
                    b1, b2 = st.columns(2)
                    with b1: 
                        if st.button("✏️ Editar", key=f"ed_{idx}", use_container_width=True): editar_registro(idx, r)
                    with b2:
                        if st.button("🗑️ Borrar", key=f"del_{idx}", use_container_width=True): 
                            sheet.delete_rows(idx+2)
                            st.session_state.dfZonas = cargar_datos()
                            st.rerun()
    else:
        st.info("No se encontraron registros con los filtros actuales.")

with tabReporte:
    st.subheader("📊 Panel de Control Operativo")

    # --- TODO DENTRO DE ESTE IF ---
    if not df_filtrado.empty:
        # 1. PREPARACIÓN DE DATOS
        df_filtrado['CostoAnual'] = pd.to_numeric(df_filtrado['CostoAnual'], errors='coerce').fillna(0)

        df_reparacion = df_filtrado.copy()
        df_reparacion['Eficiencia'] = df_reparacion['Estado'].apply(
            lambda x: 'Reparada' if x == 'Completada' else 'Pendiente'
        )
        total = len(df_reparacion)
        reparadas = len(df_reparacion[df_reparacion['Eficiencia'] == 'Reparada'])
        porcentaje = (reparadas / total * 100) if total > 0 else 0

        # 2. DEFINICIÓN DE GRÁFICAS (G1, G2, G3, G4)
        g1 = alt.Chart(df_filtrado).mark_bar().encode(
            x=alt.X('Severidad:N', sort=['Baja', 'Media', 'Alta'], title="Nivel de Severidad"), # Título del eje X
            y=alt.Y('count():Q', title="Cantidad de Hallazgos"), # Título del eje Y
            color=alt.Color('TipoFuga:N', scale=alt.Scale(domain=list(FLUIDOS.keys()),
                                                         range=[f['color'] for f in FLUIDOS.values()]), legend=None),
            tooltip=['TipoFuga', 'count()']
        ).properties(width=180, height=250, title="Distribución por Severidad") # Título superior de la gráfica

        g2 = alt.Chart(df_filtrado).mark_bar().encode(
            y=alt.Y('Estado:N', sort='-x', title=None),
            x=alt.X('count():Q', title="Fugas"),
            color=alt.Color('Estado:N', scale=alt.Scale(domain=['Dañada', 'En proceso de reparar', 'Completada'],
                                                       range=['#d9534f', '#f0ad4e', '#5cb85c']), legend=None),
            tooltip=['Estado', 'count()']
        ).properties(width=180, height=250, title="Estatus")

        g3 = alt.Chart(df_filtrado).mark_bar(color="#d9534f").encode(
            x=alt.X('Categoria:N', title="Cat"),
            y=alt.Y('sum(CostoAnual):Q', title="USD"),
            tooltip=['Categoria', 'sum(CostoAnual)']
        ).properties(width=180, height=250, title="Impacto ($)")

        base_anillo = alt.Chart(df_reparacion).encode(
            theta=alt.Theta("Eficiencia:N", aggregate="count"),
            color=alt.Color("Eficiencia:N", scale=alt.Scale(domain=['Reparada', 'Pendiente'],
                                                           range=['#5cb85c', '#d9534f']), legend=None)
        )
        anillo = base_anillo.mark_arc(innerRadius=45)
        texto = alt.Chart(pd.DataFrame({'t': [f'{porcentaje:.0f}%']})).mark_text(fontSize=20, fontWeight='bold', color='white').encode(text='t:N')
        g4 = (anillo + texto).properties(width=180, height=250, title="Eficiencia")

        # 3. RENDERIZADO DASHBOARD
        # NUEVA GRÁFICA: INSPECCIONADAS VS DETECTADAS
        # Contamos "Inspección (OK)" vs Resto de Fugas (Dañada + En Proceso + Completada (pero completada es fuga reparada))
        # El user pide: % Áreas Inspeccionadas vs Fugas Detectadas (Dañadas + En Proceso)
        
        # Total registros
        total_regs = len(df_filtrado)
        n_inspecciones = len(df_filtrado[df_filtrado['TipoFuga'] == "Inspección (OK)"])
        n_fugas_activas = len(df_filtrado[df_filtrado['Estado'].isin(['Dañada', 'En proceso de reparar'])])
        
        # Creamos DF para la gráfica
        data_pie = pd.DataFrame({
            'Categoria': ['Inspeccionado (OK)', 'Fugas Detectadas'],
            'Valor': [n_inspecciones, n_fugas_activas]
        })
        
        base_pie = alt.Chart(data_pie).encode(
            theta=alt.Theta("Valor", stack=True),
            color=alt.Color("Categoria", scale=alt.Scale(domain=['Inspeccionado (OK)', 'Fugas Detectadas'], range=['#28a745', '#d9534f']), legend=None)
        )
        pie = base_pie.mark_arc(outerRadius=80)
        text_pie = base_pie.mark_text(radius=100).encode(
            text=alt.Text("Valor"),
            order=alt.Order("Valor", sort="descending")
        )
        
        g5 = (pie + text_pie).properties(width=180, height=250, title="Cobertura vs Fugas")

        dashboard_unificado = alt.hconcat(g1, g2, g3, g4, g5).configure_view(stroke=None).configure_concat(spacing=30)
        st.altair_chart(dashboard_unificado, use_container_width=True)

        # 4. PLANO DE RIESGOS (BAJADO)
        st.markdown("---")
        st.markdown("#### 🗺️ Ubicación Física de Hallazgos")
        rep_img = img_original.copy()
        draw = ImageDraw.Draw(rep_img)
        sc = ancho_real / 1200
        for _, r in df_filtrado.iterrows():
            color_hex = FLUIDOS.get(r['TipoFuga'], {"color": "#FFFFFF"})['color']
            co = [r['x1']*sc, r['y1']*sc, r['x2']*sc, r['y2']*sc]
            draw.rectangle(co, outline=color_hex, width=25)

        st.image(rep_img, caption="Vista de Riesgos en Planta", use_container_width=True)

        # 5. BOTONES DE DESCARGA (TODOS JUNTOS)
        st.subheader("📥 Exportar Reportes")
        d_col1, d_col2, d_col3 = st.columns(3)

        with d_col1:
            # SANITIZACIÓN: Convertimos L_min a string con apóstrofe para Excel
            df_export = df_filtrado.copy()
            df_export['L_min'] = df_export['L_min'].apply(lambda x: f"'{x}")
            
            csv = df_export.to_csv(index=False).encode('utf-8')
            st.download_button("📊 Datos (CSV)", data=csv, file_name="Reporte_Fugas.csv", mime="text/csv", use_container_width=True)

        with d_col2:
            buf = io.BytesIO()
            rep_img.save(buf, format="PNG")
            st.download_button("🖼️ Imagen PNG", data=buf.getvalue(), file_name="Mapa_Riesgos.png", mime="image/png", use_container_width=True)

        with d_col3:
            # Aquí asumimos que el objeto 'm' (folium) ya fue creado arriba
            m.save("mapa_interactivo.html")
            with open("mapa_interactivo.html", "rb") as f:
                st.download_button("🗺️ Mapa HTML", data=f, file_name="Mapa_Interactivo.html", mime="text/html", use_container_width=True)

    else:
        # SOLO UN ELSE AL FINAL
        st.info("Filtra algún fluido en el menú lateral para ver el reporte.")

# --- FOOTER CON FIRMA ---
st.markdown(f"""<div style="text-align: center; color: #888; background-color: #161a22; padding: 25px; border-radius: 15px; border: 1px solid #2d323d; margin-top: 40px;">
    <h3 style="color: #fff;">🏭💧 Leak Hunter Digital Twin v1.1</h3>
    <p><b>Developed by:</b> Master Engineer Erik Armenta</p>
    <p style="font-style: italic; color: #5271ff;">"Accuracy is our signature, and innovation is our nature."</p>
</div>""", unsafe_allow_html=True)




