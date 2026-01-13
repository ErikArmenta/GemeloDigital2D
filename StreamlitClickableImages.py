import streamlit as st
from streamlit_image_coordinates import streamlit_image_coordinates
import pandas as pd
from PIL import Image, ImageDraw
import gspread
import folium
from streamlit_folium import st_folium
from folium.raster_layers import ImageOverlay
import io

# --- 1. CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(
    page_title="PlanFlow Monitor | Digital Twin ",
    page_icon="🏭",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 2. CSS DARK MODE PRO (Custom UI) ---
st.markdown("""
    <style>
    /* Fondo general y contenedores */
    .stApp {
        background-color: #0E1117;
    }
    div[data-testid="stMetricValue"] {
        color: #5271ff !important;
        font-family: 'Courier New', monospace;
    }
    /* Estilo para las tarjetas de KPIs */
    div[data-testid="metric-container"] {
        background-color: #1d2129;
        border: 1px solid #2d323d;
        padding: 15px;
        border-radius: 12px;
    }
    /* Tabs en Dark Mode */
    .stTabs [data-baseweb="tab-list"] {
        background-color: #1d2129;
        border-radius: 10px;
        padding: 5px;
    }
    .stTabs [data-baseweb="tab"] {
        color: #ffffff !important;
    }
    /* Firma en Dark Mode */
    .footer-container {
        text-align: center;
        color: #888;
        background-color: #161a22;
        padding: 25px;
        border-radius: 15px;
        border: 1px solid #2d323d;
        margin-top: 40px;
    }
    </style>
    """, unsafe_allow_html=True)

# --- CONEXIÓN GSHEET (Sin cambios en lógica) ---
@st.cache_resource
def conectar_gsheet():
    try:
        credentials = st.secrets["gcp_service_account"]
        gc = gspread.service_account_from_dict(credentials)
        sh = gc.open_by_url("https://docs.google.com/spreadsheets/d/1on_gy_rcoLHiU-jlEisvArr38v90Nwuj_SysnooEuTY/edit#gid=0")
        return sh.get_worksheet(0)
    except Exception as e:
        return None

sheet = conectar_gsheet()

def cargar_datos():
    if sheet:
        data = sheet.get_all_records()
        return pd.DataFrame(data) if data else pd.DataFrame(columns=['x1', 'y1', 'x2', 'y2', 'Zona', 'TipoFuga'])
    return pd.DataFrame()

if 'dfZonas' not in st.session_state:
    st.session_state.dfZonas = cargar_datos()

# --- CONFIGURACIÓN DE FLUIDOS ---
FLUIDOS = {
    "Aire": {"color": "#0000FF", "emoji": "💨", "marker": "blue"},
    "Gas": {"color": "#FFA500", "emoji": "🔥", "marker": "orange"},
    "Agua": {"color": "#00FFFF", "emoji": "💧", "marker": "cadetblue"},
    "Helio": {"color": "#FF00FF", "emoji": "🎈", "marker": "purple"},
    "Aceite": {"color": "#FFFF00", "emoji": "🛢️", "marker": "darkred"}
}

img_original = Image.open("PlanoHanon.png")
ancho_real, alto_real = img_original.size

# --- 3. SIDEBAR DARK ---
with st.sidebar:
    # 1. Mostrar el logo (Asegúrate de que el archivo EA_2.png esté en la misma carpeta que tu script)
    try:
        st.image("EA_2.png", use_container_width=True)
    except:
        st.error("⚠️ No se encontró el archivo EA_2.png")

    st.markdown("<h2 style='text-align: center;'>🏭💧 PlanFlow</h2>", unsafe_allow_html=True)
    st.markdown("---")

    st.header("🎯 Filtros Globales")
    filtro_fluidos = st.multiselect(
        "Líneas a monitorear:",
        options=list(FLUIDOS.keys()),
        default=list(FLUIDOS.keys())
    )

    st.markdown("---")
    st.success("Cloud Link: Active ✅")

    # Firma en el sidebar
    st.markdown(f"""
        <div style='text-align: center; padding: 10px; border: 1px solid #2d323d; border-radius: 10px;'>
            <p style='margin: 0; font-size: 0.8em; color: #888;'>Developed by:</p>
            <p style='margin: 0; font-weight: bold; color: #5271ff;'>Master Engineer Erik Armenta</p>
        </div>
    """, unsafe_allow_html=True)

# --- 4. HEADER & KPIs (CORREGIDOS) ---
st.title("🏭 Gemelo Digital de Planta I v1.0")
df_filtrado = st.session_state.dfZonas[st.session_state.dfZonas['TipoFuga'].isin(filtro_fluidos)]

# CORRECCIÓN DE KPI: Ahora cuenta líneas reales con datos, no la selección del filtro
lineas_con_fuga = df_filtrado['TipoFuga'].nunique()

k1, k2, k3, k4 = st.columns(4)
with k1:
    st.metric("Puntos Críticos", len(df_filtrado))
with k2:
    st.metric("Líneas con Fuga", lineas_con_fuga) # Ahora muestra 1 si solo has cargado una
with k3:
    status = "Normal" if len(df_filtrado) < 3 else "Atención"
    st.metric("Status Operativo", status)
with k4:
    st.metric("Resolución Plano", "4K UHD")

st.markdown("---")

# --- 5. TABS ---
tabMapa, tabConfig, tabReporte = st.tabs(["📍 Mapa Interactivo", "⚙️ Gestión de Activos", "📊 Inteligencia de Datos"])

# --- PESTAÑA 1: MAPA ---
with tabMapa:
    st.subheader("📍 Monitoreo de Redes en Tiempo Real")

    # Crear el mapa base
    m = folium.Map(
        location=[alto_real / 2, ancho_real / 2],
        zoom_start=-1,
        crs="Simple",
        min_zoom=-2,
        max_zoom=2
    )

    # Capa del plano
    ImageOverlay(
        image="PlanoHanon.png",
        bounds=[[0, 0], [alto_real, ancho_real]],
        opacity=0.9
    ).add_to(m)

    for i, row in df_filtrado.iterrows():
        # Cálculo de coordenadas
        factor_x, factor_y = ancho_real / 1200, alto_real / (1200 * (alto_real / ancho_real))
        cx, cy = (row['x1'] + row['x2']) / 2 * factor_x, alto_real - ((row['y1'] + row['y2']) / 2 * factor_y)

        f_info = FLUIDOS.get(row['TipoFuga'], {"color": "white", "marker": "red", "emoji": "⚠️"})

        # --- DISEÑO DEL HOVER (TOOLTIP) ---
        # Este es el que sale al pasar el cursor
        hover_html = f"""
        <div style="
            background-color: #1d2129;
            color: white;
            padding: 10px;
            border-radius: 8px;
            border: 1px solid {f_info['color']};
            box-shadow: 0px 0px 10px rgba(0,0,0,0.5);
            font-family: 'Arial';
            min-width: 140px;
        ">
            <span style='font-size: 1.2em;'>{f_info['emoji']}</span>
            <b style='color: {f_info['color']};'>{row['Zona']}</b><br>
            <small style='color: #bbb;'>Línea: {row['TipoFuga']}</small><br>
            <div style='margin-top: 5px; font-size: 0.8em; color: #5271ff;'>Mantenimiento: Requerido</div>
        </div>
        """

        # --- DISEÑO DEL CLIC (POPUP) ---
        # Este se mantiene para detalles más profundos
        popup_html = f"<div style='color:black; font-family:Arial;'><b>ID: {i}</b><br>Registro completo en la nube.</div>"

        # Añadir marcador con HOVER
        folium.Marker(
            location=[cy, cx],
            popup=folium.Popup(popup_html, max_width=150),
            tooltip=folium.Tooltip(hover_html), # <--- Aquí activamos el Hover elegante
            icon=folium.Icon(
                color=f_info['marker'],
                icon="info-sign" if row['TipoFuga'] != "Aceite" else "tint"
            )
        ).add_to(m)

    # Renderizado
    st_folium(m, width=1400, height=750, use_container_width=True)

# PESTAÑA 2: CONFIGURACIÓN
with tabConfig:
    c1, c2 = st.columns([2, 1])
    with c1:
        base_w = 1200
        img_c = img_original.resize((base_w, int(base_w*alto_real/ancho_real)))
        v_c = streamlit_image_coordinates(img_c, width=base_w, click_and_drag=True, key="dark_conf")
    with c2:
        st.subheader("📝 Nuevo Registro")
        t_f = st.selectbox("Línea afectada", list(FLUIDOS.keys()))
        n_z = st.text_input("Identificador de Zona")
        if v_c and v_c.get('x1') != v_c.get('x2'):
            st.image(img_c.crop((v_c['x1'], v_c['y1'], v_c['x2'], v_c['y2'])), caption="Crop Preview")
        if st.button("🚀 Enviar a Base de Datos", use_container_width=True):
            sheet.append_row([v_c['x1'], v_c['y1'], v_c['x2'], v_c['y2'], n_z, t_f])
            st.session_state.dfZonas = cargar_datos()
            st.rerun()

# --- PESTAÑA 3: REPORTE ---
with tabReporte:
    st.subheader("📊 Métricas por Fluido")
    # METRICAS RECUPERADAS
    cols_f = st.columns(len(filtro_fluidos))
    for i, f_name in enumerate(filtro_fluidos):
        count = len(df_filtrado[df_filtrado['TipoFuga'] == f_name])
        cols_f[i].metric(f"{FLUIDOS[f_name]['emoji']} {f_name}", count)

    st.markdown("---")

    # DIBUJO DEL PLANO HD
    rep_img = img_original.copy()
    draw = ImageDraw.Draw(rep_img)
    sc = ancho_real / 1200
    for _, r in df_filtrado.iterrows():
        fi = FLUIDOS.get(r['TipoFuga'])
        co = [r['x1']*sc, r['y1']*sc, r['x2']*sc, r['y2']*sc]
        draw.rectangle(co, outline=fi["color"], width=18)
        draw.text((co[0], co[1]-75), f"{fi['emoji']} {r['Zona']}", fill=fi["color"], font_size=50)

    st.image(rep_img, use_container_width=True)

    # BOTONES DE DESCARGA
    st.subheader("📥 Exportar Resultados")
    d1, d2 = st.columns(2)

    with d1:
        # Descarga de Imagen PNG
        buf = io.BytesIO()
        rep_img.save(buf, format="PNG")
        st.download_button("🖼️ Descargar Plano HD (Imagen)", data=buf.getvalue(), file_name="PlanFlow_Static_Report.png", mime="image/png")

    with d2:
        # Descarga de Mapa Interactivo HTML
        # Esto guarda el mapa de la pestaña 1 con sus clics y popups
        map_html = io.BytesIO()
        m.save("mapa_interactivo.html") # Guardamos el objeto folium 'm' de arriba
        with open("mapa_interactivo.html", "rb") as f:
            st.download_button("🌐 Descargar Mapa Interactivo (HTML)", data=f, file_name="PlanFlow_Interactive_Map.html", mime="text/html")

# --- FOOTER ---
st.markdown(f"""<div class="footer-container">
    <h3 style="color: #fff;">🏭💧 Gemelo Digital de Planta I v1.0</h3>
    <p><b>Developed by:</b> Master Engineer Erik Armenta</p>
    <p style="font-style: italic; color: #5271ff;">"Accuracy is our signature, and innovation is our nature."</p>
</div>""", unsafe_allow_html=True)
