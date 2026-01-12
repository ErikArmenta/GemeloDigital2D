import streamlit as st
from streamlit_image_coordinates import streamlit_image_coordinates
import pandas as pd
from PIL import Image, ImageDraw
import gspread

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(layout="wide", page_title="Hanon - Gestión de Fugas")

# --- CONEXIÓN CON GOOGLE SHEETS ---
def conectar_gsheet():
    try:
        credentials = st.secrets["gcp_service_account"]
        gc = gspread.service_account_from_dict(credentials)
        sh = gc.open_by_url("https://docs.google.com/spreadsheets/d/1on_gy_rcoLHiU-jlEisvArr38v90Nwuj_SysnooEuTY/edit#gid=0")
        return sh.get_worksheet(0)
    except Exception as e:
        st.error(f"Error de conexión: {e}")
        return None

sheet = conectar_gsheet()

def cargar_datos():
    if sheet:
        data = sheet.get_all_records()
        if not data:
            return pd.DataFrame(columns=['x1', 'y1', 'x2', 'y2', 'Zona', 'TipoFuga'])
        return pd.DataFrame(data)
    return pd.DataFrame()

if 'dfZonas' not in st.session_state:
    st.session_state.dfZonas = cargar_datos()

# --- CONFIGURACIÓN DE FLUIDOS ---
FLUIDOS = {
    "Aire": {"color": "#0000FF", "emoji": "💨"},
    "Gas": {"color": "#FFA500", "emoji": "🔥"},
    "Agua": {"color": "#00FFFF", "emoji": "💧"}
}

img_original = Image.open("PlanoHanon.png")

# --- SIDEBAR: FILTRO GLOBAL ---
st.sidebar.header("🎯 Filtros de Visualización")
filtro_fluidos = st.sidebar.multiselect(
    "Mostrar solo:",
    options=list(FLUIDOS.keys()),
    default=list(FLUIDOS.keys()),
    help="Filtra las fugas visibles en el mapa y el reporte."
)

tabMapa, tabConfig, tabReporte = st.tabs(["🗺️ Mapa Interactivo", "⚙️ Configuración y Recortes", "📊 Reporte de Fugas"])

# --- PESTAÑA 1: MAPA ---
with tabMapa:
    col_map, col_info = st.columns([3, 1])

    with col_info:
        st.subheader("🕵️ Panel de Inspección")
        zoom_mapa = st.slider("Nivel de Zoom", 800, 4000, 1500, step=100)
        st.caption("Usa el slider para ampliar y las barras para navegar.")
        info_placeholder = st.empty()

    with col_map:
        df_filtrado = st.session_state.dfZonas[st.session_state.dfZonas['TipoFuga'].isin(filtro_fluidos)]
        rescale = zoom_mapa / 1200
        img_mapa = img_original.resize((zoom_mapa, int(img_original.height * (zoom_mapa / img_original.width))))
        overlay = img_mapa.copy()
        draw = ImageDraw.Draw(overlay)

        for i, row in df_filtrado.iterrows():
            f_info = FLUIDOS.get(row['TipoFuga'], {"color": "red", "emoji": "⚠️"})
            rect = [row['x1']*rescale, row['y1']*rescale, row['x2']*rescale, row['y2']*rescale]
            draw.rectangle(rect, outline=f_info["color"], width=4)
            draw.text((rect[0], rect[1] - 20), f"ID:{i} {f_info['emoji']}", fill=f_info["color"])

        st.markdown(
            '<style>.element-container:has(#map_scroll) + div {overflow: auto !important; max-height: 750px; border: 2px solid #444;}</style><div id="map_scroll"></div>',
            unsafe_allow_html=True
        )

        click = streamlit_image_coordinates(overlay, width=zoom_mapa, key="click_mapa")

        if click:
            x_val = click.get('x') if click.get('x') is not None else click.get('x1')
            y_val = click.get('y') if click.get('y') is not None else click.get('y1')
            if x_val is not None:
                rescale_inv = 1200 / zoom_mapa
                xq, yq = x_val * rescale_inv, y_val * rescale_inv
                match = df_filtrado.query(f'x1 <= {xq} <= x2 and y1 <= {yq} <= y2')
                if not match.empty:
                    f = match.iloc[0]
                    info_placeholder.markdown(f"""
                        <div style="background-color:#262730; padding:20px; border-radius:10px; border-left: 5px solid {FLUIDOS[f['TipoFuga']]['color']};">
                            <h3>🔍 ID: {match.index[0]}</h3>
                            <b>Zona:</b> {f['Zona']}<br>
                            <b>Tipo:</b> {f['TipoFuga']} {FLUIDOS[f['TipoFuga']]['emoji']}<br>
                        </div>
                    """, unsafe_allow_html=True)

# --- PESTAÑA 2: CONFIGURACIÓN E HISTORIAL ---
with tabConfig:
    st.subheader("🛠️ Registro de Zonas")
    col_c1, col_c2 = st.columns([2, 1])

    with col_c1:
        base_width = 1200
        img_config = img_original.resize((base_width, int(base_width*img_original.height/img_original.width)))
        v_conf = streamlit_image_coordinates(img_config, width=base_width, click_and_drag=True, key="conf_draw")

    with col_c2:
        tipo_f = st.selectbox("Fluido", list(FLUIDOS.keys()))
        nombre_z = st.text_input("Nombre de la Zona")

        if v_conf and v_conf.get('x1') != v_conf.get('x2'):
            st.write("🖼️ **Vista previa:**")
            preview_crop = img_config.crop((v_conf['x1'], v_conf['y1'], v_conf['x2'], v_conf['y2']))
            overlay_color = Image.new('RGB', preview_crop.size, FLUIDOS[tipo_f]['color'])
            st.image(Image.blend(preview_crop, overlay_color, alpha=0.3))

        if st.button("💾 Guardar Registro", use_container_width=True) and v_conf:
            sheet.append_row([v_conf['x1'], v_conf['y1'], v_conf['x2'], v_conf['y2'], nombre_z, tipo_f])
            st.session_state.dfZonas = cargar_datos()
            st.rerun()

    st.divider()
    st.subheader("📋 Historial de Recortes Configuradores")
    # Mostrar historial de recortes con botón de eliminar mejorado
    for index, row in st.session_state.dfZonas.iterrows():
        with st.container(border=True):
            h1, h2, h3 = st.columns([1, 2, 1])
            with h1:
                recorte = img_config.crop((row['x1'], row['y1'], row['x2'], row['y2']))
                st.image(recorte)
            with h2:
                st.markdown(f"### {FLUIDOS[row['TipoFuga']]['emoji']} {row['Zona']}")
                st.write(f"**Tipo:** {row['TipoFuga']}")
            with h3:
                if st.button(f"🗑️ Eliminar Fuga", key=f"del_{index}", use_container_width=True):
                    sheet.delete_rows(index + 2)
                    st.session_state.dfZonas = cargar_datos()
                    st.rerun()

# --- PESTAÑA 3: REPORTE ---
with tabReporte:
    st.subheader("📊 Resumen Ejecutivo y Etiquetas en Plano")
    df_rep = st.session_state.dfZonas[st.session_state.dfZonas['TipoFuga'].isin(filtro_fluidos)]

    if not df_rep.empty:
        # Métricas superiores
        cols_m = st.columns(len(filtro_fluidos) + 1)
        cols_m[0].metric("Total Visible", len(df_rep))
        for i, f_name in enumerate(filtro_fluidos):
            count = len(df_rep[df_rep['TipoFuga'] == f_name])
            cols_m[i+1].metric(f"{FLUIDOS[f_name]['emoji']} {f_name}", count)

        # Dibujo del reporte con etiquetas detalladas
        report_img = img_original.copy()
        draw_report = ImageDraw.Draw(report_img)
        scale = img_original.width / 1200

        for _, row in df_rep.iterrows():
            f_info = FLUIDOS[row['TipoFuga']]
            coords = [row['x1']*scale, row['y1']*scale, row['x2']*scale, row['y2']*scale]

            # Dibujar el rectángulo con mayor grosor para el reporte
            draw_report.rectangle(coords, outline=f_info["color"], width=15)

            # ETIQUETAS: Texto con el color del fluido
            # Se coloca un poco arriba del cuadro
            etiqueta = f"{f_info['emoji']} {row['Zona']} ({row['TipoFuga']})"
            draw_report.text((coords[0], coords[1] - 65), etiqueta, fill=f_info["color"])

        st.image(report_img, use_container_width=True)

        # Opción de descarga
        report_img.save("reporte_hanon_final.png")
        with open("reporte_hanon_final.png", "rb") as f:
            st.download_button("🖼️ Descargar Plano con Etiquetas", f, "reporte_fugas_hanon.png")