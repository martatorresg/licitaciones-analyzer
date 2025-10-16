import os
import json
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import PromptTemplate
from config import GOOGLE_API_KEY
from PyPDF2 import PdfReader
import textwrap
import re
import textwrap

# ==========================================
# FUNCIONES DE UTILIDAD
# ==========================================

def extraer_texto_pdfs(carpeta: str) -> str:
    """Extrae y combina texto de todos los PDFs en una carpeta."""
    textos = []
    for archivo in os.listdir(carpeta):
        if archivo.lower().endswith(".pdf"):
            ruta_pdf = os.path.join(carpeta, archivo)
            print(f"📄 Extrayendo texto de: {archivo}")
            with open(ruta_pdf, "rb") as f:
                reader = PdfReader(f)
                texto = "".join([page.extract_text() or "" for page in reader.pages])
                textos.append(texto)
    return "\n".join(textos)



def dividir_en_chunks(texto: str, max_chars: int = 15000) -> list[str]:
    """
    Divide el texto en chunks manejables y marca secciones clave.
    - Detecta encabezados de "Solvencia técnica" y "Solvencia económica".
    - Añade meta-información del chunk para que Gemini sepa a qué sección pertenece.
    """

    # Normalizar saltos de línea y espacios
    texto = re.sub(r'\s+', ' ', texto).strip()

    # Buscar secciones
    secciones = []
    patron = re.compile(r"(Solvencia técnica|Solvencia económica)", re.IGNORECASE)
    matches = list(patron.finditer(texto))

    if matches:
        for i, m in enumerate(matches):
            inicio = m.start()
            fin = matches[i + 1].start() if i + 1 < len(matches) else len(texto)
            seccion_nombre = m.group(1).strip()
            seccion_texto = texto[inicio:fin].strip()
            secciones.append((seccion_nombre, seccion_texto))
    else:
        secciones.append(("general", texto))

    # Dividir cada sección en chunks de tamaño max_chars
    chunks = []
    for nombre, contenido in secciones:
        subchunks = textwrap.wrap(contenido, max_chars)
        for sc in subchunks:
            # Añadimos meta-información de la sección al chunk
            chunk_final = f"[Sección: {nombre}]\n{sc}"
            chunks.append(chunk_final)

    return chunks


def combinar_respuestas(respuestas: list[dict]) -> dict:
    """
    Combina varias respuestas parciales de los chunks en un único diccionario limpio.
    - Campos únicos (expediente, cliente, fechas, dinero) → primera respuesta válida.
    - Campos extensos (prórroga, solvencia técnica, solvencia económica) → concatenar y resumir.
    """
    resultado_final = {}

    campos_unicos = [
        "número de expediente",
        "cliente (órgano de contratación)",
        "clasificación cpv",
        "valor estimado del contrato (con y sin iva)",
        "plazo de presentación de la oferta (fecha límite)"
        "esquema nacional de seguridad (si se exige, nivel requerido)"
    ]
    campos_extensos = [
        "criterios de valoración",
        "resumen trabajos o servicios a contratar",
        "prórroga",
        "requisitos de solvencia técnica",
        "acreditación de solvencia técnica",
        "requisitos de solvencia económica",
        "acreditación de solvencia económica",
        "equipo de trabajo (número de personas, requisitos, formación, experiencia)",
        "acreditación del equipo de trabajo (cómo se debe demostrar el equipo de trabajo)"
    ]

    for campo in campos_unicos:
        for r in respuestas:
            if campo in r and r[campo]:
                resultado_final[campo] = r[campo]
                break

    for campo in campos_extensos:
        textos = []
        for r in respuestas:
            if campo in r and r[campo]:
                valor = r[campo]
                if isinstance(valor, str):
                    valor = valor.strip()
                    if valor and valor not in textos:
                        textos.append(valor)
                elif isinstance(valor, list):
                    textos.extend([str(v).strip() for v in valor if str(v).strip() not in textos])
                else:
                    textos.append(str(valor).strip())
        if textos:
            resultado_final[campo] = " / ".join(textos)

    return resultado_final


# ==========================================
# CONFIGURACIÓN DEL MODELO
# ==========================================

llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    temperature=0,
    google_api_key=GOOGLE_API_KEY
)


# ==========================================
# PROMPTS
# ==========================================

# Prompt para cada chunk
prompt_template_chunk = PromptTemplate(
    input_variables=["document"],
    template=(
        "Analiza el siguiente texto de una licitación pública y extrae en formato JSON los siguientes campos:\n"
        "- número de expediente (obligatorio)\n"
        "- cliente (órgano de contratación) (obligatorio)\n"
        "- clasificación CPV (obligatorio)\n"
        "- valor estimado del contrato (con y sin IVA, también añadir si el contrato dura más de un año) (obligatorio)\n"
        "- plazo de presentación de la oferta (fecha límite) (obligatorio)\n"
        "- criterios de valoración (extrae los criterios con sus puntuaciones o porcentaj, si hay alguna fórmula incluyela)(obligatorio)\n"
        "- resumen trabajos o servicios a contratar (obligatorio)\n"
        "- prórroga (si existe, duración)\n"
        "- requisitos de solvencia técnica (resumir experiencia, formación, medios humanos y materiales)(obligatorio)\n"
        "- acreditación de solvencia técnica (como se debe demostrar la solvencia técnica)(obligatorio)\n"
        "- requisitos de solvencia económica (resumir, incluyendo cómo se acredita)(obligatorio)\n"
        "- acreditación de solvencia económica (como se debe demostrar la solvencia económica)(obligatorio)\n"
        "- esquema nacional de seguridad (si se exige, nivel requerido)(obligatorio)\n"
        "- equipo de trabajo (número de personas, requisitos, formación, experiencia)\n"
        "- acreditación del equipo de trabajo (cómo se debe demostrar el equipo de trabajo)\n"
        "Texto:\n{document}\n\n"
        "Devuelve solo el JSON, sin texto adicional."
    )
)

# Prompt para consolidar respuestas parciales
prompt_template_final = PromptTemplate(
    input_variables=["partial_json"],
    template=(
        "Se han extraído múltiples respuestas parciales de una licitación en JSON. "
        "Fusiona todas en un único JSON limpio y completo con los siguientes campos:\n"
        "- número de expediente\n"
        "- cliente (órgano de contratación)\n"
        "- clasificación CPV\n"
        "- valor estimado del contrato (con y sin IVA)\n"
        "- plazo de presentación de la oferta (fecha límite)\n"
        "- criterios de valoración\n"
        "- resumen trabajos o servicios a contratar\n"
        "- prórroga\n"
        "- requisitos de solvencia técnica\n"
        "- acreditación de solvencia técnica\n"
        "- requisitos de solvencia económica\n"
        "- acreditación de solvencia económica\n"
        "- esquema nacional de seguridad (si se exige, nivel requerido)(obligatorio)\n"
        "- equipo de trabajo\n"
        "- acreditación del equipo de trabajo (cómo se debe demostrar el equipo de trabajo)\n"
        "Reglas:\n"
        "1. Para los campos únicos, usa la primera respuesta válida.\n"
        "2. Para los campos extensos, genera un resumen claro y conciso, eliminando duplicados.\n"
        "3. Devuelve solo el JSON final, sin texto adicional.\n\n"
        "Respuestas parciales:\n{partial_json}"
    )
)


# ==========================================
# FUNCIÓN PRINCIPAL
# ==========================================

def extract_licitacion_data(carpeta_licitacion: str) -> dict:
    """
    Extrae información de todos los PDFs de una licitación usando chunking y consolidación.
    """
    print(f"📁 Procesando carpeta: {carpeta_licitacion}")
    
    # 1️⃣ Extraer texto completo de todos los PDFs
    texto = extraer_texto_pdfs(carpeta_licitacion)
    
    # 2️⃣ Dividir en chunks
    chunks = dividir_en_chunks(texto)
    print(f"📚 Dividido en {len(chunks)} chunks.")

    respuestas_parciales = []

    # 3️⃣ Analizar cada chunk
    for i, chunk in enumerate(chunks, 1):
        print(f"🤖 Analizando chunk {i}/{len(chunks)}...")
        try:
            prompt = prompt_template_chunk.format(document=chunk)
            response = llm.invoke(prompt)
            raw_output = response.content if hasattr(response, "content") else str(response)
            clean_output = raw_output.strip().replace("```json", "").replace("```", "").strip()

            if clean_output:
                try:
                    data = json.loads(clean_output)
                    respuestas_parciales.append(data)
                except Exception as e:
                    print(f"⚠️ Error parsing JSON chunk {i}: {e}")
            else:
                print(f"⚠️ Chunk {i} vacío, se omite.")

        except Exception as e:
            print(f"⚠️ Error analizando chunk {i}: {e}")

    # 4️⃣ Consolidar respuestas parciales
    if respuestas_parciales:
        try:
            partial_json_str = json.dumps(respuestas_parciales)
            prompt_final = prompt_template_final.format(partial_json=partial_json_str)
            response_final = llm.invoke(prompt_final)
            raw_final = response_final.content if hasattr(response_final, "content") else str(response_final)
            clean_final = raw_final.strip().replace("```json", "").replace("```", "").strip()
            if clean_final:
                try:
                    resultado_final = json.loads(clean_final)
                except Exception as e:
                    print(f"⚠️ Error parsing JSON final: {e}")
                    resultado_final = combinar_respuestas(respuestas_parciales)
            else:
                resultado_final = combinar_respuestas(respuestas_parciales)
        except Exception as e:
            print(f"⚠️ Error consolidando respuestas: {e}")
            resultado_final = combinar_respuestas(respuestas_parciales)
    else:
        print(f"⚠️ No se pudieron extraer datos de la licitación {carpeta_licitacion}")
        resultado_final = {"nombre_carpeta": os.path.basename(carpeta_licitacion)}

    # 5️⃣ Siempre agregar nombre de la carpeta
    resultado_final["nombre_carpeta"] = os.path.basename(carpeta_licitacion)
    
    return resultado_final
