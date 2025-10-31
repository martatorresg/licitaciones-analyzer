import os
import json
import re
import time
from PyPDF2 import PdfReader
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings 
from langchain_core.prompts import PromptTemplate 
from langchain_core.documents import Document 
from langchain_text_splitters import CharacterTextSplitter
from langchain_community.vectorstores import Chroma 
from config import GOOGLE_API_KEY

# ==========================================
# UTILIDADES
# ==========================================

def extraer_texto_pdfs(carpeta: str) -> str:
    # ... (función existente: correcta) ...
    textos = []
    for archivo in os.listdir(carpeta):
        if archivo.lower().endswith(".pdf"):
            ruta_pdf = os.path.join(carpeta, archivo)
            print(f"📄 Extrayendo texto de: {archivo}")
            with open(ruta_pdf, "rb") as f:
                try:
                    reader = PdfReader(f)
                    texto = "".join([page.extract_text() or "" for page in reader.pages])
                    textos.append(texto)
                except Exception as e:
                    print(f"⚠️ Error al leer PDF {archivo}: {e}")
    return "\n".join(textos)



def a_texto_plano_mejorado(data: dict) -> dict:

    resultado = {}

    for key, value in data.items():
        if value is None:
            continue
        
        # Intentamos convertir el string plano a dict/list si parece JSON
        if isinstance(value, str):
            try:
                # Esto es útil si el LLM responde un JSON a pesar de la instrucción de texto plano
                value = json.loads(value)
            except:
                pass # Si no es JSON, se queda como string

        # --- CAMPO ESPECIAL: CLASIFICACIÓN CPV ---
        if key.lower() in ["clasificación cpv", "clasificacion cpv"]:
            if isinstance(value, list):
                resultado[key] = "\n".join([f"- {v}" for v in value])
            else:
                # Esto maneja el string plano que puede venir del RAG LLM
                cpvs = [v.strip() for v in str(value).split("\n") if v.strip().startswith('-')] # Buscar bullets o líneas
                if not cpvs:
                    cpvs = [v.strip() for v in str(value).split(",") if v.strip()] # Si no tiene bullets, por coma
                resultado[key] = "\n".join([f"{v}" if v.startswith('-') else f"- {v}" for v in cpvs])
            continue

        # --- CAMPO ESPECIAL: CLIENTE (MODIFICADO) ---
        # ❗ Ahora solo se espera el nombre de la entidad como string plano (sin subcampos).
        if key.lower() == "cliente":
            # Aseguramos que sea un string y lo limpiamos
            resultado[key] = str(value).strip()
            continue
        
        # --- ESTRUCTURAS COMPLEJAS: DICCIONARIOS Y LISTAS ---

        if isinstance(value, dict):
            # ... (Lógica de Diccionarios original, se mantiene) ...
            lines = []
            paginas = set()
            for subkey, subval in value.items():
                if isinstance(subval, list):
                    bullets = []
                    for v in subval:
                        m = re.search(r"\(Página.*?\)", str(v))
                        if m:
                            paginas.add(m.group(0))
                            v = re.sub(r"\(Página.*?\)", "", str(v)).strip()
                        bullets.append(f"- {v}")
                    lines.append(f"{subkey}:\n" + "\n".join(bullets))
                else:
                    lines.append(f"{subkey}: {subval}")
            texto = "\n".join(lines)
            if paginas:
                texto += f"\n(Páginas: {', '.join(sorted(paginas))})"
            resultado[key] = texto
            continue

        elif isinstance(value, list):
            # ... (Lógica de Listas original, se mantiene) ...
            bullets = []
            paginas = set()
            for v in value:
                m = re.search(r"\(Página.*?\)", str(v))
                if m:
                    paginas.add(m.group(0))
                    v = re.sub(r"\(Página.*?\)", "", str(v)).strip()
                bullets.append(f"- {v}")
            texto = "\n".join(bullets)
            if paginas:
                texto += f"\n(Páginas: {', '.join(sorted(paginas))})"
            resultado[key] = texto
            continue

        # --- TEXTO SIMPLE ---
        else:
            resultado[key] = str(value)

        # Limpieza final de saltos de línea múltiples
        resultado[key] = re.sub(r'\n+', '\n', resultado[key]).strip()

    return resultado

# ==========================================
# CONFIGURACIÓN LLM Y EMBEDDINGS
# ==========================================

llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    temperature=0,
    google_api_key=GOOGLE_API_KEY
)

embeddings = GoogleGenerativeAIEmbeddings(model="text-embedding-004", google_api_key=GOOGLE_API_KEY)

# ==========================================
# PROMPTS Y REGLAS 
# ==========================================
prompt_template_rag = PromptTemplate(
    input_variables=["campo", "reglas_campo", "document"], # ❗ Añadimos 'reglas_campo' al input
    template=(
        "Analiza el siguiente texto de una licitación pública y extrae el **valor para el campo: {campo}**, "
        "siguiendo estrictamente las reglas de formato indicadas. "
        "Si no encuentras el dato, responde únicamente con un guion (-).\n\n"
        "Reglas de formato para el campo '{campo}':\n"
        "{reglas_campo}\n\n"
        "Texto de referencia:\n{document}\n\n"
        "Devuelve únicamente el valor del campo **{campo}**, sin texto adicional ni formato JSON. Respeta los saltos de línea y bullets si son parte de las reglas."
    )
)

# 🆕 Se añaden las reglas completas para todos los campos para que la función principal funcione.
REGLAS_POR_CAMPO = {
    "número de expediente": "- solo el número limpio, sin texto adicional.",
    "cliente": "- nombre del cliente (entidad adjudicadora).",
    "clasificación CPV": "- Lista de códigos o descripciones CPV, uno por línea, precedido por un guion (-).",
    "valor estimado del contrato": "- Importe sin IVA, e indicar los ejercicios económicos si dura más de un año. Si no aparece, use (-).",
    "plazo de presentación de la oferta": "- **FORMATO ESTRICTO: DD/MM/AAAA a las HH:MM (Zona Horaria).** Extrae ÚNICAMENTE la fecha y hora LÍMITE para presentar ofertas (nunca la fecha de inicio o el plazo de ejecución del contrato). Si el formato de hora no está especificado, usa HH:MM 23:59. Si la Zona Horaria no está especificada, omítela.",
    "criterios de valoración": "- Esquema detallado con bullets, separando claramente los criterios evaluables mediante fórmulas (automáticos) de los juicios de valor (discrecionales). Añadir al final cómo obtener la máxima puntuación",
    "resumen de trabajos o servicios a contratar": "- Descripción concisa de los trabajos o servicios, en formato de lista con bullets.",
    "prórroga": "- Sí/No. Si es Sí, indicar duración total (Ejemplo: Sí, 2 años).",
    "requisitos de solvencia técnica": "- Bullets con los requisitos (relación trabajos principales + ISOS necesarias). Incluir al final la referencia general a la página del documento de la licitación (Ejemplo: (Página 12-14)).",
    "acreditación de solvencia técnica": "- Bullets con los documentos de acreditación (cómo se acreditan los requisitos de solvencia técnica). Incluir al final la referencia general a la página (Ejemplo: (Página 14)).",
    "requisitos de solvencia económica": "- Bullets con los requisitos (volumen anual de negocio que se tiene que cumplir). Incluir al final la referencia general a la página (Ejemplo: (Página 15)).",
    "acreditación de solvencia económica": "- Bullets con los documentos de acreditación (cómo se acreditan los requisitos de solvencia económica). Incluir al final la referencia general a la página (Ejemplo: (Página 15)).",
    "esquema nacional de seguridad": "- Sí/No. Si es Sí, indicar el nivel (Básico/Medio/Alto).",
    "equipo de trabajo": "- Bullets, detallando formación, años de experiencia y roles clave (añadir en este apartado los medios materiales). Incluir al final la referencia general a la página.",
    "acreditación del equipo de trabajo": "- Bullets con los documentos de acreditación (cómo se acreditan los requisitos del equipo de trabajo). Incluir al final la referencia general a la página.",
    "documentación por sobre (contenido de sobres)": "- Bullets resumiendo el contenido requerido para cada sobre (Técnico, Económico, etc.)(No repetir información sobre la solvencia técnica o económica). Incluir al final la referencia general a la página.",
    "¿cuándo se acredita la solvencia técnica?":" - Indicar el momento exacto (Indicar si se acredita en la licitación o en la adjudicación). Si no se especifica, usar (-).",
    "nombre carpeta": "- Solo el nombre de la carpeta (Ejemplo: 2024-001).",
}

# 🆕 Definición de los campos (consultas) a extraer
CAMPOS_A_EXTRAER = list(REGLAS_POR_CAMPO.keys()) # Usar las claves del diccionario de reglas.

# ==========================================
# FUNCIÓN PRINCIPAL RAG
# ==========================================

def extract_licitacion_data(carpeta_licitacion: str, progress_callback=None) -> dict:
    """Extrae información de los PDFs de una licitación usando RAG."""
    print(f"📁 Procesando carpeta con RAG: {carpeta_licitacion}")
    texto = extraer_texto_pdfs(carpeta_licitacion)

    if not texto.strip():
        print(f"⚠️ No se pudo extraer texto de la carpeta {carpeta_licitacion}. Retornando vacío.")
        return {"nombre_carpeta": os.path.basename(carpeta_licitacion)}

    # 1. Splitter de LangChain
    text_splitter = CharacterTextSplitter(
        separator="\n\n",
        chunk_size=3000,
        chunk_overlap=200,
        length_function=len,
        is_separator_regex=False,
    )
    chunks = text_splitter.split_text(texto)
    print(f"📚 Dividido en {len(chunks)} chunks con Text Splitter.")
    try:
        # 2. Indexación (Crear el Vector Store)
        print("⏳ Creando base de datos vectorial (Chroma)...")
        # Nota: Chroma guarda los datos en memoria por defecto si no se especifica 'persist_directory'.
        # Si quieres persistir, añade `persist_directory="./chroma_db"`
        vectorstore = Chroma.from_texts(
                texts=chunks,
                embedding=embeddings,
                collection_name=os.path.basename(carpeta_licitacion)
            )

        resultados_rag = {}

        # Parámetros para el progreso
        total_campos = len(CAMPOS_A_EXTRAER)

        # 3. y 4. Recuperación y Generación (RAG Loop)
        for i, campo in enumerate(CAMPOS_A_EXTRAER): # ❗ USAR enumerate
            # ❗ ACTUALIZAR LA BARRA DE PROGRESO AL INICIO DEL PROCESAMIENTO DEL CAMPO
            if progress_callback:
                progress_callback(i, total_campos, campo)

            k_value = 1
            if campo in ["plazo de presentación de la oferta", "documentación por sobre (contenido de sobres)"]:
                k_value = 2

            # El campo 'nombre carpeta' se añade al final y no necesita RAG
            if campo == "nombre carpeta":
                resultados_rag[campo] = os.path.basename(carpeta_licitacion)
                continue
                
            # print(f"🔍 Buscando información para: **{campo}** (k={k_value})") # Desactivar para Streamlit

            # 3. Recuperación: Obtener los chunks más relevantes (top k)
            retrieved_docs = vectorstore.similarity_search(query=campo, k=k_value)
            document_content = "\n\n---\n\n".join([doc.page_content for doc in retrieved_docs])
            
            if not document_content.strip():
                # print(f"⚠️ No se encontraron documentos relevantes para {campo}. Valor por defecto: (-)") # Desactivar para Streamlit
                resultados_rag[campo] = "-"
                continue

            # 4. Generación: Llamar al LLM con el texto relevante.
            try:
                reglas = REGLAS_POR_CAMPO.get(campo, "")
                
                prompt = prompt_template_rag.format(
                    campo=campo,
                    reglas_campo=reglas,
                    document=document_content
                )
                
                response = llm.invoke(prompt)
                raw_output = response.content if hasattr(response, "content") else str(response)
                
                clean_output = raw_output.strip().replace("```json", "").replace("```", "").strip() 
                
                resultados_rag[campo] = clean_output if clean_output else "-"
                
            except Exception as e:
                # print(f"⚠️ Error al generar respuesta para {campo}: {e}") # Desactivar para Streamlit
                resultados_rag[campo] = f"Error: {e}"
            time.sleep(1.5) # Pausa para evitar límites de tasa
            # print("-" * 50) # Desactivar para Streamlit
            
        # ❗ Llamada final para asegurar el 100% en la barra (opcional si la llamada final es fuera del bucle)
        if progress_callback:
            progress_callback(total_campos - 1, total_campos, "Completado") 

        # 5. Limpieza Final (Usa la función original para formatear Cliente, CPV, etc.)
        resultado_final = a_texto_plano_mejorado(resultados_rag)
    finally:
            # ❗ PASO CRÍTICO: Eliminar la colección de Chroma de la memoria/disco
            # Esto debería liberar cualquier bloqueo de archivo que Chroma haya creado.
            if 'vectorstore' in locals():
                try:
                    # Esto fuerza la liberación de recursos si Chroma lo permite
                    # Para un VectorStore en memoria, esto puede no ser necesario, 
                    # pero ayuda si se han creado archivos temporales.
                    del vectorstore 
                except:
                    pass

    return resultado_final