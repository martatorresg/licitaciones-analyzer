import streamlit as st
import pandas as pd
import os
import shutil
from openpyxl.styles import Alignment
from io import BytesIO
from extractor import CAMPOS_A_EXTRAER
import time 
from extractor import extract_licitacion_data 

# ❗ NUEVAS IMPORTACIONES PARA GUARDAR EN EXCEL PERSISTENTE
# Importamos la alineación que se usa en la función de guardado
from openpyxl.styles import Alignment 

# ❗ CONSTANTE PARA EL ARCHIVO PERSISTENTE (MOVIDA DE main.py)
EXCEL_FILE = "mejoras_registro_licitaciones.xlsx" 

# ❗ FUNCIÓN MOVIDA DE main.py PARA GUARDAR RESULTADOS PERSISTENTEMENTE
def guardar_en_excel(datos_nuevos: list[dict]):
    """
    Carga el archivo Excel existente, concatena los nuevos datos, 
    y lo guarda, aplicando formato de salto de línea.
    """
    df_nuevos = pd.DataFrame(datos_nuevos)

    # Si existe archivo, cargamos y concatenamos
    if os.path.exists(EXCEL_FILE):
        try:
            # Cargar con engine='openpyxl' para consistencia
            df_existente = pd.read_excel(EXCEL_FILE)
            df_final = pd.concat([df_existente, df_nuevos], ignore_index=True)
        except Exception as e:
            # En caso de error de lectura (ej. archivo bloqueado/corrupto), 
            # procedemos solo con los datos nuevos
            st.warning(f"⚠️ Error al leer el archivo Excel existente: {e}. Se intentará guardar solo el registro actual.")
            df_final = df_nuevos
    else:
        df_final = df_nuevos

    # Guardar en Excel usando 'with'
    try:
        with pd.ExcelWriter(EXCEL_FILE, engine='openpyxl') as writer:
            df_final.to_excel(writer, index=False, sheet_name="Licitaciones")

            # Ajustar formato de celdas con saltos de línea
            ws = writer.sheets["Licitaciones"]
            for row in ws.iter_rows():
                for cell in row:
                    if isinstance(cell.value, str) and '\n' in cell.value:
                        # Solo aplicar el wrap_text si el texto contiene un salto de línea
                        cell.alignment = Alignment(wrap_text=True)
        
        # Feedback en la aplicación Streamlit
        st.success(f"💾 **¡Éxito!** Datos guardados persistentemente en **'{EXCEL_FILE}'** ({len(df_final)} registros totales).")
    except Exception as e:
        st.error(f"❌ Error al intentar guardar en '{EXCEL_FILE}': {e}. El archivo podría estar abierto o bloqueado por otra aplicación.")


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
    [data-testid="stFileUploadDropzone"] {{
        border: 2px dashed {COLOR_MORADO};
        background-color: #1e2126;  
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
        background-color: #4a1f9e;  
    }}

    /* Estilo de la barra de progreso (cambia el color de relleno) */
    .stProgress > div > div > div > div {{
        background-color: {COLOR_MORADO};  
    }}

    /* Estilo para los títulos */
    h2, h3 {{
        color: #ffffff;  
    }}
    
    /* Estilo para el Título principal: El "Q" es Lima, el resto es blanco */
    .title-text {{
        font-size: 3em;
        font-weight: 700;
        margin: 0;
    }}
    .title-q {{
        color: {COLOR_LIMA};
    }}

    /* NUEVO: Estilo para contenedores de pasos */
    .styled-container {{
        border: 2px solid {COLOR_MORADO};
        border-radius: 8px;
        padding: 15px;
        margin-top: 15px;
        margin-bottom: 25px;  
        background-color: #1e2126; /* Fondo sutil */
    }}
    
    /* Aplicar el estilo a los contenedores de Streamlit */
    /* st.container genera divs con data-testid="stVerticalBlock" */
    /* Usamos el índice [data-testid="stVerticalBlock"]:nth-child(...) para aplicar el estilo solo a los contenedores que queremos */

    </style>
    """,
    unsafe_allow_html=True
)

# Renderizado del título en la caja morada con el espacio y el color de texto ajustado
st.markdown(
    f"""
    <div class="header-box">
        <h1 class="title-text">
            <span class="title-q">QIA</span> Licitator
        </h1>
    </div>
    """,
    unsafe_allow_html=True
)

# Nuevo contenido para el Analizador de Licitaciones por IA
st.markdown("## 🔍 Analizador de Licitaciones por IA")
st.markdown("""
**¡Acelera tu proceso de licitación!** 🚀

Herramienta avanzada que utiliza la **API de Gemini** y la Búsqueda Semántica (**RAG**) para la gestión inteligente de documentos. Simplemente sube tus **PDF de licitaciones públicas** y obtén automáticamente:

* ⏰ **Plazos Clave:** Fechas límite y aperturas.
* ✅ **Requisitos de Solvencia:** Económica, técnica y profesional.
* ⚖️ **Criterios de Valoración:** Ponderación y fórmulas a aplicar.
* ➕ **¡Y Mucho Más!** 💡

Los resultados se presentan de forma **estructurada y lista para usar** en un práctico archivo **Excel** 📊.
""")

# --- LIMPIEZA Y PREPARACIÓN DE DIRECTORIOS ---
DATA_DIR = "data_uploads"

def setup_dirs():
    os.makedirs(DATA_DIR, exist_ok=True)

setup_dirs()

# --- FUNCIÓN PARA DESCARGAR EXCEL ---
# Nota: Esta función de descarga ahora NO lee el DataFrame de resultados_analisis, 
# sino que debería leer el archivo EXCEL_FILE para la descarga.
def to_excel(df):
    """Convierte el DataFrame a un objeto BytesIO para descarga."""
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        # Aquí convertimos el DataFrame de la sesión a bytes.
        # Para descargar el archivo persistente, cambiaríamos esta lógica.
        # Por ahora, se mantiene para descargar el resultado de la sesión.
        df.to_excel(writer, index=False, sheet_name='Resultados')
    processed_data = output.getvalue()
    return processed_data


# --- SUBIDA DE ARCHIVOS (PASO 1) ---
# Usamos st.container() para agrupar los widgets y luego aplicamos el CSS
step1_container = st.container(border=True) # Usamos el border nativo de Streamlit
with step1_container:
    st.markdown("### 📤 Paso 1: Subir Documentos PDF")
    uploaded_files = st.file_uploader(
        "Selecciona los archivos PDF de las licitaciones (debe haber al menos un PDF)",
        type=["pdf"],
        accept_multiple_files=True
    )
    # Mensaje si no hay archivos subidos
    if not uploaded_files:
        st.info("Sube uno o varios archivos PDF para comenzar el análisis de la licitación.")


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

        # INICIO del Recuadro del Paso 2
        step2_container = st.container(border=True)
        with step2_container:
            # 2. Barra de Progreso
            st.markdown("### ⏳ Paso 2: Progreso del Análisis")
            progress_bar = st.progress(0, text="Extrayendo texto de PDFs...")
            
            # Simulamos la función extract_licitacion_data pero con la actualización de la barra
            resultados_analisis = []
            try:
                st.warning("⚠️ Conectando con Gemini API. Esto puede tardar varios minutos dependiendo del tamaño del PDF.")
                
                # Aquí va la llamada a la función real, asumiendo que tiene la lógica de callback
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
                    
                    # ❗ LLAMADA A LA FUNCIÓN DE PERSISTENCIA: GUARDA LA NUEVA FILA EN EL EXCEL COMPARTIDO
                    guardar_en_excel(resultados_analisis)
                    
                    # Reordenar las columnas para mayor claridad
                    cols_orden = ["nombre carpeta", "número de expediente", "plazo de presentación de la oferta", "valor estimado del contrato", "cliente"]
                    cols_restantes = [c for c in df_resultados.columns if c not in cols_orden]
                    df_resultados = df_resultados[cols_orden + cols_restantes]

                    st.markdown("---")
                    
                    # INICIO del Recuadro del Paso 3
                    step3_container = st.container(border=True)
                    with step3_container:
                        st.markdown("### 📊 Paso 3: Resultados del Análisis")
                        
                        # Muestra la pequeña muestra del Excel (la tabla de resultados de esta sesión)
                        st.dataframe(
                            df_resultados,
                            height=250,
                            use_container_width=True
                        )
                        
                        # Botón de Descarga
                        # Opcional: Para asegurar que se descarga la última versión persistente,
                        # se podría leer 'resultados_licitaciones.xlsx' aquí y usar `to_excel` sobre ese DF
                        excel_data = to_excel(df_resultados)
                        st.download_button(
                            label="📥 Descargar Resultados (.xlsx)",
                            data=excel_data,
                            file_name="mejoras_licitaciones_quantia.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            key="download_btn"
                        )
                        
            except Exception as e:
                st.error(f"❌ Un error ha ocurrido durante el análisis: {e}")
            finally:
                st.info("🧹 Intentando limpiar archivos temporales de la sesión...")
                
                # --- LÓGICA DE LIMPIEZA MEJORADA CON REINTENTOS ---
                max_attempts = 3
                for attempt in range(max_attempts):
                    try:
                        # ❗ Intentamos borrar SOLO la carpeta única de esta sesión
                        shutil.rmtree(licitacion_dir) 
                        st.success(f"🧹 Carpeta temporal **{os.path.basename(licitacion_dir)}** eliminada con éxito.")
                        break # Si tiene éxito, salimos del bucle
                    except Exception as e:
                        if attempt < max_attempts - 1:
                            # Esperar un momento y reintentar
                            time.sleep(1) 
                            st.warning(f"⚠️ Intento {attempt + 1}/{max_attempts} fallido al eliminar {os.path.basename(licitacion_dir)}. Reintentando...")
                        else:
                            # Si falla el último intento, mostramos el error
                            st.error(f"❌ Fallo definitivo al eliminar la carpeta temporal **{os.path.basename(licitacion_dir)}** después de {max_attempts} intentos. Deberás borrarla manualmente.")
                            
                st.balloons()
                
                # Recreamos el directorio solo para que la próxima ejecución no falle
                os.makedirs(DATA_DIR, exist_ok=True)