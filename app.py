import streamlit as st
import pandas as pd
import os
import shutil
from io import BytesIO
from extractor import CAMPOS_A_EXTRAER
import time # Para simular la barra de progreso
from extractor import extract_licitacion_data # Asume que extractor.py está en el mismo directorio

# --- CONFIGURACIÓN DE PÁGINA Y ESTILO ---
st.set_page_config(
    page_title="Licitator",
    page_icon="🔎",
    layout="centered",
    initial_sidebar_state="auto"
)

# Colores Corporativos (Ajustados para buen contraste en tema oscuro)
COLOR_MORADO = "#5f27cd" # Un morado intenso
COLOR_LIMA = "#b8ff33" # Verde Lima brillante

# Personalización del tema y CSS para el título en caja morada
st.markdown(
    f"""
    <style>
    /* Estilo para el fondo de la aplicación y modo oscuro */
    .stApp {{
        background-color: #0e1117; /* Fondo oscuro */
    }}
    
    /* Caja Morada del Título */
    .header-box {{
        background-color: {COLOR_MORADO};
        color: white;
        padding: 20px;
        border-radius: 10px;
        text-align: center;
        margin-bottom: 20px;
    }}
    .header-box h1 {{
        color: white !important;
        margin: 0;
        font-size: 3em;
        font-weight: 700;
    }}
    
    /* Botones y Barra de Progreso */
    /* Este CSS ajusta los elementos primarios de Streamlit, incluyendo botones */
    [data-testid="stFileUploadDropzone"] {{
        border: 2px dashed {COLOR_MORADO};
        background-color: #1e2126; /* Un gris oscuro para el área de subida */
    }}
    
    /* Botón Primario (Analizar) */
    .stButton>button:first-child {{
        background-color: {COLOR_MORADO};
        color: white;
        border: none;
        padding: 10px 20px;
        border-radius: 5px;
        font-weight: bold;
    }}
    .stButton>button:hover {{
        background-color: #4a1f9e; /* Un morado un poco más oscuro al pasar el ratón */
    }}

    /* Estilo de la barra de progreso (cambia el color de relleno) */
    .stProgress > div > div > div > div {{
        background-color: {COLOR_MORADO}; 
    }}

    /* Estilo para los títulos (opcional, para usar el lima) */
    h2, h3 {{
        color: #ffffff; /* Blanco */
    }}
    
    /* Color de la fuente del logo "Q" */
    .logo-q {{
        color: {COLOR_LIMA};
        font-size: 1.2em;
        font-weight: bold;
    }}

    </style>
    """,
    unsafe_allow_html=True
)

# --- LIMPIEZA Y PREPARACIÓN DE DIRECTORIOS ---
DATA_DIR = "data_uploads"

def setup_dirs():
    # Solamente asegura que el directorio exista, no intenta borrarlo.
    os.makedirs(DATA_DIR, exist_ok=True)

setup_dirs()

# --- FUNCIÓN PARA DESCARGAR EXCEL ---
def to_excel(df):
    """Convierte el DataFrame a un objeto BytesIO para descarga."""
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Resultados')
    processed_data = output.getvalue()
    return processed_data

# --- INTERFAZ ---

# Título en la caja morada
st.markdown(
    f'<div class="header-box"><h1><span class="logo-q">QIA</span>Licitator</h1></div>', 
    unsafe_allow_html=True
)

# Descripción
st.markdown("## 🔍 Analizador de Licitaciones por IA")
st.markdown(
    """
    Herramienta avanzada que utiliza la **API de Gemini** y **búsqueda semántica (RAG)** para escanear documentos PDF de licitaciones 
    públicas y extraer automáticamente campos clave como plazos, solvencias, criterios de valoración y más, 
    presentando los resultados de forma estructurada en un archivo Excel.
    """
)
st.markdown("---")

# --- SUBIDA DE ARCHIVOS ---
st.markdown("### 📤 Paso 1: Subir Documentos PDF")
uploaded_files = st.file_uploader(
    "Selecciona los archivos PDF de las licitaciones (debe haber al menos un PDF)",
    type=["pdf"],
    accept_multiple_files=True
)

# --- PROCESO DE ANÁLISIS ---
if uploaded_files:
    if st.button("🚀 Analizar Licitaciones", key="analizar_btn"):
        # 1. Generar nombre de carpeta único con timestamp
        timestamp = int(time.time())
        licitacion_dir = os.path.join(DATA_DIR, f"licitacion_temp_{timestamp}")
        os.makedirs(licitacion_dir, exist_ok=True)
        
        for uploaded_file in uploaded_files:
            # Guardamos el archivo en la subcarpeta temporal
            file_path = os.path.join(licitacion_dir, uploaded_file.name)
            with open(file_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
        
        st.info(f"✅ Documentos guardados temporalmente en la carpeta 'licitacion_temp'. Iniciando el análisis de {len(uploaded_files)} archivos.")
        st.markdown("---")

        # 2. Barra de Progreso
        st.markdown("### ⏳ Paso 2: Progreso del Análisis")
        progress_bar = st.progress(0, text="Extrayendo texto de PDFs...")
        
        # Simular el proceso de RAG para la barra
        total_steps = len(CAMPOS_A_EXTRAER)
        
        # Simulamos la función extract_licitacion_data pero con la actualización de la barra
        resultados_analisis = []
        try:
            st.warning("⚠️ Conectando con Gemini API. Esto puede tardar varios minutos dependiendo del tamaño del PDF.")
            
            # La función extract_licitacion_data debe aceptar el argumento 'progress_callback'
            # (Hemos modificado extractor.py para esto, ver sección 2)
            data = extract_licitacion_data(
                carpeta_licitacion=licitacion_dir, 
                progress_callback=lambda current, total, campo: progress_bar.progress(
                    (current + 1) / total, 
                    text=f"Analizando campo: **{campo}** ({current+1}/{total})"
                )
            )
            resultados_analisis.append(data)
            
            progress_bar.progress(1.0, text="✅ Análisis completado. Formateando resultados...")

            # 3. Presentar Resultados
            if resultados_analisis:
                df_resultados = pd.DataFrame(resultados_analisis)
                
                # Reordenar las columnas para mayor claridad
                cols_orden = ["nombre carpeta", "número de expediente", "plazo de presentación de la oferta", "valor estimado del contrato", "cliente"]
                cols_restantes = [c for c in df_resultados.columns if c not in cols_orden]
                df_resultados = df_resultados[cols_orden + cols_restantes]

                st.markdown("---")
                st.markdown("### 📊 Paso 3: Resultados del Análisis")
                
                # Muestra la pequeña muestra del Excel (la tabla de resultados)
                st.dataframe(
                    df_resultados,
                    height=250,
                    use_container_width=True
                )
                
                # Botón de Descarga
                excel_data = to_excel(df_resultados)
                st.download_button(
                    label="📥 Descargar Resultados (.xlsx)",
                    data=excel_data,
                    file_name="resultados_licitaciones_quantia.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key="download_btn"
                )
                
        except Exception as e:
            st.error(f"❌ Un error ha ocurrido durante el análisis: {e}")
        finally:
            st.info("🧹 Intentando limpiar archivos temporales de la sesión...")
            try:
                # ❗ Intentamos borrar SOLO la carpeta única de esta sesión
                shutil.rmtree(licitacion_dir, ignore_errors=True) 
            except Exception as e:
                st.warning(f"⚠️ No se pudo eliminar la carpeta temporal {licitacion_dir}: {e}. Tendrás que borrarla manualmente.")
            st.balloons()
            
            # Recreamos el directorio solo para que la próxima ejecución no falle
            os.makedirs(DATA_DIR, exist_ok=True)

elif 'download_btn' in st.session_state and st.session_state.download_btn:
    # Si la descarga ya se realizó, se limpia el directorio por si acaso.
    shutil.rmtree(DATA_DIR, ignore_errors=True)
    setup_dirs()
    
# Mensaje si no hay archivos subidos
else:
    st.info("Sube uno o varios archivos PDF para comenzar el análisis de la licitación.")