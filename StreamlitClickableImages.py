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

# --- 1. CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(
    page_title="PlanFlow Monitor | Digital Twin",
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
        columnas_esperadas = ['x1', 'y1', 'x2', 'y2', 'Zona', 'TipoFuga', 'Area', 'Ubicacion', 'ID_Maquina', 'Severidad']
        if data:
            df = pd.DataFrame(data)
            for col in columnas_esperadas:
                if col not in df.columns:
                    df[col] = "Media" if col == "Severidad" else "N/A"
            df['Severidad'] = df['Severidad'].apply(lambda x: x if x in ["Baja", "Media", "Alta"] else "Media")
            return df
        return pd.DataFrame(columns=columnas_esperadas)
    return pd.DataFrame()

if 'dfZonas' not in st.session_state:
    st.session_state.dfZonas = cargar_datos()

# --- 3. DIÁLOGO DE EDICIÓN ---
@st.dialog("✏️ Editar Registro")
def editar_registro(index, datos_actuales):
    st.write(f"Modificando ID: {index}")
    nuevo_n = st.text_input("Nombre Zona", value=str(datos_actuales['Zona']))
    nuevo_a = st.text_input("Área", value=str(datos_actuales.get('Area', 'N/A')))
    nuevo_id = st.text_input("ID Máquina", value=str(datos_actuales.get('ID_Maquina', 'N/A')))
    val_sev = datos_actuales.get('Severidad', 'Media')
    nueva_sev = st.select_slider("Severidad", options=["Baja", "Media", "Alta"], value=val_sev)

    if st.button("💾 Guardar Cambios"):
        fila_num = index + 2
        sheet.update_cell(fila_num, 5, nuevo_n)   # E: Zona
        sheet.update_cell(fila_num, 7, nuevo_a)   # G: Area
        sheet.update_cell(fila_num, 9, nuevo_id)  # I: ID_Maquina
        sheet.update_cell(fila_num, 10, nueva_sev) # J: Severidad
        st.success("¡Actualizado!")
        st.session_state.dfZonas = cargar_datos()
        st.rerun()

# --- 4. CONFIGURACIÓN VISUAL ---
FLUIDOS = {
    "Aire": {"color": "#0000FF", "emoji": "💨", "marker": "blue"},
    "Gas": {"color": "#FFA500", "emoji": "🔥", "marker": "orange"},
    "Agua": {"color": "#00FFFF", "emoji": "💧", "marker": "cadetblue"},
    "Helio": {"color": "#FF00FF", "emoji": "🎈", "marker": "purple"},
    "Aceite": {"color": "#FFFF00", "emoji": "🛢️", "marker": "darkred"}
}

img_original = Image.open("PlanoHanon.png")
ancho_real, alto_real = img_original.size

# --- 5. SIDEBAR ---
with st.sidebar:
    try: st.image("EA_2.png", use_container_width=True)
    except: st.error("Logo no encontrado")
    st.markdown("<h2 style='text-align: center;'>🏭 PlanFlow</h2>", unsafe_allow_html=True)
    filtro_fluidos = st.multiselect("Monitorear:", list(FLUIDOS.keys()), default=list(FLUIDOS.keys()))
    st.success("Conexión: Cloud Sync ✅")
    
    # --- FIRMA DE AUTOR (Movida al Sidebar) ---
    st.markdown(f"""
        <div style='text-align: center; padding: 20px; border: 1px solid #2d323d; border-radius: 15px; background-color: #161a22; margin-top: 20px;'>
            <p style='margin: 0; font-size: 0.9em; color: #888;'>Developed by:</p>
            <p style='margin: 5px 0; font-weight: bold; font-size: 1.2em; color: #5271ff;'>Master Engineer Erik Armenta</p>
            <p style='margin: 0; font-style: italic; font-size: 0.8em; color: #444;'>Innovating Digital Twins for Industrial Excellence</p>
        </div>
    """, unsafe_allow_html=True)

df_filtrado = st.session_state.dfZonas[st.session_state.dfZonas['TipoFuga'].isin(filtro_fluidos)]

# --- 6. TABS ---
tabMapa, tabConfig, tabReporte = st.tabs(["📍 Mapa", "⚙️ Gestión", "📊 Reporte"])

with tabMapa:
    # --- 1. MÉTRICAS SUPERIORES ---
    m1, m2, m3, m4 = st.columns(4)
    with m1: st.metric("Hallazgos Totales", len(df_filtrado))
    with m2:
        alta_count = len(df_filtrado[df_filtrado['Severidad'] == 'Alta'])
        st.metric("🚨 Prioridad Alta", alta_count, delta=f"{alta_count} urgentes", delta_color="inverse")
    with m3: st.metric("Prioridad Media", len(df_filtrado[df_filtrado['Severidad'] == 'Media']))
    with m4: st.metric("Prioridad Baja", len(df_filtrado[df_filtrado['Severidad'] == 'Baja']))

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
        image="PlanoHanon.png",
        bounds=[[0, 0], [alto_real, ancho_real]],
        opacity=0.8
    ).add_to(m)

    # --- 4. RENDERIZADO DE MARCADORES ---
    for i, row in df_filtrado.iterrows():
        factor_x, factor_y = ancho_real / 1200, alto_real / (1200 * (alto_real / ancho_real))
        cx, cy = (row['x1'] + row['x2']) / 2 * factor_x, alto_real - ((row['y1'] + row['y2']) / 2 * factor_y)

        f_info = FLUIDOS.get(row['TipoFuga'], {"color": "white", "marker": "red", "emoji": "⚠️"})
        color_sev = {"Alta": "#FF4B4B", "Media": "#FFA500", "Baja": "#28A745"}.get(row['Severidad'], "#333")

        # Tooltip Elegante
        hover_html = f"""
        <div style="background-color:#1d2129; color:white; padding:10px; border-radius:8px; border-left:5px solid {f_info['color']}; min-width:150px;">
            <b>{f_info['emoji']} {row['Zona']}</b><br>
            <span style="color:{color_sev}; font-size:0.9em;">Prioridad: {row['Severidad']}</span>
        </div>"""

        # Popup con Formulario Completo
        popup_content = f"""
        <div style="font-family: 'Segoe UI', sans-serif; color: #333; min-width: 220px;">
            <h4 style="margin:0 0 10px 0; color:{f_info['color']}; border-bottom: 2px solid {color_sev};">📋 Ficha Técnica</h4>
            <table style="width:100%; font-size: 13px; border-spacing: 0 5px;">
                <tr><td><b>Zona:</b></td><td>{row['Zona']}</td></tr>
                <tr><td><b>ID Máquina:</b></td><td>{row['ID_Maquina']}</td></tr>
                <tr><td><b>Área:</b></td><td>{row['Area']}</td></tr>
                <tr><td><b>Ubicación:</b></td><td>{row['Ubicacion']}</td></tr>
                <tr><td><b>Fluido:</b></td><td>{row['TipoFuga']} {f_info['emoji']}</td></tr>
                <tr><td><b>Severidad:</b></td><td style="color:{color_sev}; font-weight:bold;">{row['Severidad']}</td></tr>
            </table>
        </div>
        """

        # Crear el Icono
        # Si es Severidad Alta, le añadimos la clase 'brinca-peppo' para que salte
        clase_css = "brinca-peppo" if row['Severidad'] == "Alta" else ""

        folium.Marker(
            location=[cy, cx],
            popup=folium.Popup(popup_content, max_width=350),
            tooltip=folium.Tooltip(hover_html),
            icon=folium.Icon(color=f_info['marker'], icon="info-sign", extra_params=f'class="{clase_css}"')
        ).add_to(m)

    st_folium(m, width=1400, height=750, use_container_width=True)



with tabConfig:
    st.markdown("##### 1. Localización y Recorte")
    st.info("Utiliza las herramientas de dibujo (cuadrado) en el mapa para definir la zona. Puedes hacer Zoom.")

    # --- CONFIGURACIÓN DEL MAPA DINÁMICO (Draw) ---
    m2 = folium.Map(
        location=[alto_real / 2, ancho_real / 2],
        zoom_start=-1,
        crs="Simple",
        min_zoom=-2,
        max_zoom=4
    )

    ImageOverlay(
        image="PlanoHanon.png",
        bounds=[[0, 0], [alto_real, ancho_real]],
        opacity=1
    ).add_to(m2)

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
            'rectangle': True, # Solo permitimos rectángulos por ahora para mantener compatibilidad
        },
        edit_options={'edit': False}
    )
    draw.add_to(m2)

    # Capturamos la salida del mapa con dibujo
    output = st_folium(m2, width=1200, height=600, key="draw_map")

    coords_dibujadas = None
    if output["all_drawings"]:
        # Tomamos el último dibujo
        last_draw = output["all_drawings"][-1]
        geometry = last_draw['geometry']
        if geometry['type'] == 'Polygon':
            # Los rectángulos en GeoJSON son Polígonos de 5 puntos (el último cierra).
            # Coordenadas: [[lng, lat]]
            # En CRS Simple: Lng = X, Lat = Y
            # Bounds: xmin, ymin, xmax, ymax
            # Ojo: En Simple, Y crece hacia arriba (como Latitud), pero nuestra imagen original y coordenadas guardadas son Y hacia abajo (Top-Left 0,0).
            # Ya dedujimos que folium Simple pone 0,0 abajo-izquierda.
            # Y la imagen guardada:
            # cx = stored_x * scale
            # cy = alto_real - (stored_y * scale)
            # => stored_y * scale = alto_real - cy
            # => stored_y = (alto_real - cy) / scale
            
            # Extraemos coordenadas del bounding box del dibujo
            lons = [p[0] for p in geometry['coordinates'][0]]
            lats = [p[1] for p in geometry['coordinates'][0]]
            
            x_min_map = min(lons)
            x_max_map = max(lons)
            y_min_map = min(lats)
            y_max_map = max(lats)

            # Conversión a Sistema de Coordenadas de 1200px (Invertido Y)
            scale_factor = width_resize = 1200 / ancho_real
            
            # Map X (Lng) -> Stored X
            # Stored X = Map X * Scale
            x1_stored = x_min_map * scale_factor
            x2_stored = x_max_map * scale_factor

            # Map Y (Lat) -> Stored Y
            # La coord Y del mapa (Lat) va de 0 a alto_real (abajo a arriba).
            # La coord Y almacenada es de arriba a abajo.
            # stored_y = (alto_real - map_y) * scale_factor
            # Para bounding box:
            # y1 (top) corresponde a y_max_map
            # y2 (bottom) corresponde a y_min_map
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
    c1, c2 = st.columns(2)
    with c1:
        t_f = st.selectbox("Fluido", list(FLUIDOS.keys()))
        n_z = st.text_input("Zona")
        area_p = st.text_input("Área Planta")
    with c2:
        id_m = st.text_input("ID Equipo")
        sev_p = st.select_slider("Severidad", options=["Baja", "Media", "Alta"], value="Media")
        ubi_f = st.radio("Nivel", ["Aérea ☁️", "Terrestre 🌍"], horizontal=True)

    if st.button("🚀 Guardar Activo", use_container_width=True):
        if coords_dibujadas and n_z:
            sheet.append_row([
                coords_dibujadas['x1'], coords_dibujadas['y1'], 
                coords_dibujadas['x2'], coords_dibujadas['y2'], 
                n_z, t_f, area_p, ubi_f, id_m, sev_p
            ])
            st.session_state.dfZonas = cargar_datos()
            st.rerun()
        elif not coords_dibujadas:
            st.warning("⚠️ Debes dibujar una zona en el mapa primero.")
        elif not n_z:
            st.warning("⚠️ Debes asignar un nombre a la Zona.")

    st.subheader("📋 Historial Registrado")
    for idx, r in st.session_state.dfZonas.iterrows():
        with st.container(border=True):
            h1, h2, h3 = st.columns([1, 2, 1])
            with h1:
                try:
                    # Para mostrar el crop, reutilizamos la lógica de imagen estática resizeada
                    # puesto que 'r' tiene coordenadas en base 1200px
                    img_hist = img_original.resize((1200, int(1200*alto_real/ancho_real)))
                    st.image(img_hist.crop((r['x1'], r['y1'], r['x2'], r['y2'])))
                except: st.caption("No image")
            with h2: st.markdown(f"**{r['Zona']}** ({r['Severidad']})"); st.caption(f"{r['Area']} | {r['ID_Maquina']}")
            with h3:
                if st.button("✏️", key=f"ed_{idx}"): editar_registro(idx, r)
                if st.button("🗑️", key=f"del_{idx}"): sheet.delete_rows(idx+2); st.session_state.dfZonas = cargar_datos(); st.rerun()

with tabReporte:
    st.subheader("📊 Análisis Operativo")
    if not df_filtrado.empty:
        # Gráfica Altair
        chart = alt.Chart(df_filtrado).mark_bar().encode(
            x=alt.X('Severidad:N', sort=['Baja', 'Media', 'Alta']),
            y='count():Q', color=alt.Color('TipoFuga:N', scale=alt.Scale(domain=list(FLUIDOS.keys()),
                                                                       range=[f['color'] for f in FLUIDOS.values()]))
        ).properties(height=350).interactive()
        st.altair_chart(chart, use_container_width=True)

        # Plano con rectángulos de severidad
        rep_img = img_original.copy()
        draw = ImageDraw.Draw(rep_img)
        sc = ancho_real / 1200
        for _, r in df_filtrado.iterrows():
            color_hex = FLUIDOS.get(r['TipoFuga'])['color']
            co = [r['x1']*sc, r['y1']*sc, r['x2']*sc, r['y2']*sc]
            draw.rectangle(co, outline=color_hex, width=20)
        st.image(rep_img, caption="Vista de Riesgos en Planta", use_container_width=True)

        # --- BOTONES DE DESCARGA RESTAURADOS ---
        st.subheader("📥 Exportar")
        d1, d2 = st.columns(2)
        with d1:
            buf = io.BytesIO()
            rep_img.save(buf, format="PNG")
            st.download_button("🖼️ Bajar Imagen PNG", data=buf.getvalue(), file_name="Reporte_PlanFlow.png", mime="image/png")
        with d2:
            m.save("mapa_interactivo.html")
            with open("mapa_interactivo.html", "rb") as f:
                st.download_button("🌐 Plano Interactivo", data=f, file_name="Mapa_Interactivo.html", mime="text/html")
    else:
        st.info("Filtra algún fluido para ver el reporte.")

# --- FOOTER CON FIRMA ---
st.markdown(f"""<div style="text-align: center; color: #888; background-color: #161a22; padding: 25px; border-radius: 15px; border: 1px solid #2d323d; margin-top: 40px;">
    <h3 style="color: #fff;">🏭💧 PlanFlow Digital Twin v1.0</h3>
    <p><b>Developed by:</b> Master Engineer Erik Armenta</p>
    <p style="font-style: italic; color: #5271ff;">"Accuracy is our signature, and innovation is our nature."</p>
</div>""", unsafe_allow_html=True)


