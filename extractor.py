import os
import json
import re
import time
import textwrap
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


# --- La función 'a_texto_plano_mejorado' es esencial para el formato final y se mantiene. ---
def a_texto_plano_mejorado(data: dict) -> dict:
    # ... (función existente: se mantiene) ...
    # NOTA: Asegúrate de que esta función maneje los valores planos (strings) que devuelve RAG LLM.

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

        # ... (Resto de la lógica de limpieza para CPV, CLIENTE, etc., se mantiene) ...

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

        # --- CAMPO ESPECIAL: CLIENTE ---
        # ❗ EL LLM RAG debería devolver un TEXTO PLANO. Adaptamos para re-parsear si el texto plano sigue el formato Entidad: X\nResponsable: Y
        if key.lower() == "cliente":
            if isinstance(value, str):
                # Intentar parsear el string plano del LLM a un dict temporal
                temp_dict = {}
                for line in value.split('\n'):
                    if ':' in line:
                        k, v = line.split(':', 1)
                        temp_dict[k.strip()] = v.strip()
                value = temp_dict
            
            if isinstance(value, dict):
                # El resto de la lógica de limpieza de cliente (la original)
                campos_orden = ["Entidad", "Responsable", "Forma de contacto", "Teléfono", "Fax", "Correo Electrónico", "Sitio Web", "Sede Electrónica"]
                lineas_cliente = []
                for campo in campos_orden:
                    subvalor = value.get(campo) or value.get(campo.lower()) # Manejar posibles minúsculas
                    if not subvalor: continue

                    subvalor_str = str(subvalor) # Simplemente convertir a string para el RAG simple
                    
                    # Pequeña mejora para Responsable si es solo un string de nombres/cargos
                    if campo == "Responsable" and subvalor_str.lower().startswith('entidad:'):
                        continue # Evitar duplicados si el LLM repitió la estructura
                    
                    lineas_cliente.append(f"{campo}: {subvalor_str}")

                resultado[key] = "\n".join(lineas_cliente)
                continue
            
            # Si sigue siendo un string simple (que no pudo ser parseado)
            resultado[key] = str(value)
            continue
        
        # --- OTROS DICCIONARIOS Y LISTAS ---
        # ❗ En el RAG simple, todo viene como TEXTO PLANO, por lo que estas secciones no deberían aplicarse.
        # Las dejamos para robustez si el LLM se desvía.

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

        resultado[key] = re.sub(r'\n+', '\n', resultado[key]).strip()

    return resultado


# ❌ ELIMINAMOS 'combinar_respuestas' ya que en el RAG simple cada campo se extrae una vez.
# Si el RAG recupera información para el mismo campo de 3 chunks, el LLM fusiona esa información.
# Si quisiéramos mantenerla, el RAG loop debería modificarse para enviar JSONs parciales,
# lo que complica la eficiencia. Por eso, optamos por el valor plano.


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
# PROMPTS Y REGLAS (ADAPTADAS)
# ==========================================

# ❌ Eliminamos 'prompt_template_chunk' y 'prompt_template_final'
# ya que el RAG simple los reemplaza con 'prompt_template_rag'.

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
    "cliente": "- Redacta de forma concisa la información de contacto y organización. Formato: Entidad: (...)\nResponsable: (...)\nForma de contacto: (...)\nTeléfono: (...)\nFax: (...)\nCorreo Electrónico: (...)\nSitio Web: (...)\nSede Electrónica: (...). No incluyas suplentes ni cargos secundarios. Si no existe un subcampo, omítelo.",
    "clasificación CPV": "- Lista de códigos o descripciones CPV, uno por línea, precedido por un guion (-).",
    "valor estimado del contrato": "- Importe total con y sin IVA, e indicar los ejercicios económicos si dura más de un año. Si no aparece, use (-).",
    "plazo de presentación de la oferta": "- **FORMATO ESTRICTO: DD/MM/AAAA a las HH:MM (Zona Horaria).** Extrae ÚNICAMENTE la fecha y hora LÍMITE para presentar ofertas (nunca la fecha de inicio o el plazo de ejecución del contrato). Si el formato de hora no está especificado, usa HH:MM 23:59. Si la Zona Horaria no está especificada, omítela.",
    "criterios de valoración": "- Esquema detallado con bullets, separando claramente los criterios evaluables mediante fórmulas (automáticos) de los juicios de valor (discrecionales).",
    "resumen de trabajos o servicios a contratar": "- Descripción concisa de los trabajos o servicios, en formato de lista con bullets.",
    "prórroga": "- Sí/No. Si es Sí, indicar duración total (Ejemplo: Sí, 2 años).",
    "requisitos de solvencia técnica": "- Bullets con los requisitos. Incluir al final la referencia general a la página del documento de la licitación (Ejemplo: (Página 12-14)).",
    "acreditación de solvencia técnica": "- Bullets con los documentos de acreditación. Incluir al final la referencia general a la página (Ejemplo: (Página 14)).",
    "requisitos de solvencia económica": "- Bullets con los requisitos (Ejemplo: Volumen de negocio mínimo). Incluir al final la referencia general a la página (Ejemplo: (Página 15)).",
    "acreditación de solvencia económica": "- Bullets con los documentos de acreditación. Incluir al final la referencia general a la página (Ejemplo: (Página 15)).",
    "esquema nacional de seguridad": "- Sí/No. Si es Sí, indicar el nivel (Básico/Medio/Alto).",
    "equipo de trabajo": "- Bullets, detallando formación, años de experiencia y roles clave. Incluir al final la referencia general a la página.",
    "acreditación del equipo de trabajo": "- Bullets con los documentos de acreditación. Incluir al final la referencia general a la página.",
    "documentación por sobre (contenido de sobres)": "- Bullets detallando el contenido requerido para cada sobre (Técnico, Económico, etc.). Incluir al final la referencia general a la página.",
    "nombre carpeta": "- Solo el nombre de la carpeta (Ejemplo: 2024-001).",
}

# 🆕 Definición de los campos (consultas) a extraer
CAMPOS_A_EXTRAER = list(REGLAS_POR_CAMPO.keys()) # Usar las claves del diccionario de reglas.

# ==========================================
# FUNCIÓN PRINCIPAL RAG
# ==========================================

def extract_licitacion_data(carpeta_licitacion: str) -> dict:
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

    # 3. y 4. Recuperación y Generación (RAG Loop)
    for campo in CAMPOS_A_EXTRAER:
        k_value = 1
        if campo in ["plazo de presentación de la oferta", "documentación por sobre (contenido de sobres)"]:
            k_value = 2 
        print(f"🔍 Buscando información para: **{campo}** (k={k_value})")
        # El campo 'nombre carpeta' se añade al final y no necesita RAG
        if campo == "nombre carpeta":
            resultados_rag[campo] = os.path.basename(carpeta_licitacion)
            continue
            
        print(f"🔍 Buscando información para: **{campo}**")

        # 3. Recuperación: Obtener los chunks más relevantes (top 1)
        retrieved_docs = vectorstore.similarity_search(query=campo, k=k_value)
        document_content = "\n\n---\n\n".join([doc.page_content for doc in retrieved_docs])
        
        if not document_content.strip():
            print(f"⚠️ No se encontraron documentos relevantes para {campo}. Valor por defecto: (-)")
            resultados_rag[campo] = "-"
            continue

        # 4. Generación: Llamar al LLM con el texto relevante.
        try:
            reglas = REGLAS_POR_CAMPO.get(campo, "") # Obtener reglas específicas
            
            prompt = prompt_template_rag.format(
                campo=campo,
                reglas_campo=reglas,
                document=document_content
            )
            
            response = llm.invoke(prompt)
            raw_output = response.content if hasattr(response, "content") else str(response)
            
            # El LLM devuelve el valor plano (string)
            clean_output = raw_output.strip().replace("```json", "").replace("```", "").strip() 
            
            resultados_rag[campo] = clean_output if clean_output else "-"
            
        except Exception as e:
            print(f"⚠️ Error al generar respuesta para {campo}: {e}")
            resultados_rag[campo] = f"Error: {e}"
        time.sleep(1.5)  # Pequeña pausa para evitar límites de tasa
        print("-" * 50)
    # 5. Limpieza Final (Usa la función original para formatear Cliente, CPV, etc.)
    resultado_final = resultados_rag
    
    # Limpieza final y formateo (cliente, CPV, etc.)
    return a_texto_plano_mejorado(resultado_final)