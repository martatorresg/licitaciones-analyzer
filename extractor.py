import os
import json
import re
import textwrap
from PyPDF2 import PdfReader
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import PromptTemplate
from config import GOOGLE_API_KEY

# ==========================================
# UTILIDADES
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
    """Divide el texto en chunks manejables y marca secciones clave."""
    texto = re.sub(r'\s+', ' ', texto).strip()
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

    chunks = []
    for nombre, contenido in secciones:
        subchunks = textwrap.wrap(contenido, max_chars)
        for sc in subchunks:
            chunk_final = f"[Sección: {nombre}]\n{sc}"
            chunks.append(chunk_final)

    return chunks

# ==========================================
# FUNCIÓN PARA LIMPIAR JSON
# ==========================================

def a_texto_plano_mejorado(data: dict) -> dict:
    """
    Convierte todos los valores de un diccionario en texto plano:
    - Listas → bullets
    - Diccionarios → esquemático
    - Clasificación CPV → cada código en bullet
    - Cliente → estructura detallada sin corchetes ni diccionarios crudos
    - Referencias a página → unificadas al final por campo
    """
    resultado = {}

    for key, value in data.items():
        if value is None:
            continue

        # --- CAMPO ESPECIAL: CLASIFICACIÓN CPV ---
        if key.lower() in ["clasificación cpv", "clasificacion cpv"]:
            if isinstance(value, list):
                resultado[key] = "\n".join([f"- {v}" for v in value])
            else:
                cpvs = [v.strip() for v in str(value).split(",")]
                resultado[key] = "\n".join([f"- {v}" for v in cpvs])
            continue

        # --- CAMPO ESPECIAL: CLIENTE ---
        if key.lower() == "cliente" and isinstance(value, dict):
            campos_orden = [
                "Entidad", "Responsable", "Forma de contacto",
                "Teléfono", "Fax", "Correo Electrónico",
                "Sitio Web", "Sede Electrónica"
            ]
            lineas_cliente = []

            for campo in campos_orden:
                subvalor = value.get(campo)
                if not subvalor:
                    continue

                # ✅ Si es lista de diccionarios (como Responsable)
                if isinstance(subvalor, list):
                    items_limpios = []
                    for item in subvalor:
                        if isinstance(item, dict):
                            nombre = item.get("nombre", "")
                            cargo = item.get("cargo", "")
                            texto = ", ".join(filter(None, [nombre, cargo]))
                            if texto:
                                items_limpios.append(texto)
                        else:
                            items_limpios.append(str(item))
                    subvalor_str = "; ".join(items_limpios)

                # ✅ Si es diccionario simple
                elif isinstance(subvalor, dict):
                    partes = [f"{k}: {v}" for k, v in subvalor.items() if v]
                    subvalor_str = ", ".join(partes)

                # ✅ Si es lista simple (como correos)
                elif isinstance(subvalor, list):
                    subvalor_str = ", ".join(str(x) for x in subvalor)

                else:
                    subvalor_str = str(subvalor)

                lineas_cliente.append(f"{campo}: {subvalor_str}")

            resultado[key] = "\n".join(lineas_cliente)
            continue

        # --- OTROS DICCIONARIOS ---
        if isinstance(value, dict):
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

        # --- LISTAS ---
        elif isinstance(value, list):
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


# ==========================================
# CONFIGURACIÓN LLM
# ==========================================

llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    temperature=0,
    google_api_key=GOOGLE_API_KEY
)

# ==========================================
# PROMPTS
# ==========================================

prompt_template_chunk = PromptTemplate(
    input_variables=["document"],
    template=(
        "Analiza el siguiente texto de una licitación pública y extrae la información en un JSON, siguiendo estrictamente estas reglas:\n\n"
        "- número de expediente: solo el número.\n"
        "- cliente: redacta de forma muy concisa y estructurada así:\n"
        "  Entidad: (nombre del órgano de contratación principal)\n"
        "  Responsable: (solo los dos cargos principales o de referencia, por ejemplo: Alcalde y Director de Área)\n"
        "  Forma de contacto: (dirección física)\n"
        "  Teléfono: (si aparece)\n"
        "  Fax: (si aparece)\n"
        "  Correo Electrónico: (hasta tres correos principales, separados por coma)\n"
        "  Sitio Web: (URL principal)\n"
        "  Sede Electrónica: (URL de la sede electrónica)\n"
        "  ❗ No incluyas suplentes, vocales ni otros cargos administrativos secundarios.\n"
        "- clasificación CPV: lista de códigos o descripciones CPV, uno por línea.\n"
        "- valor estimado del contrato: importe con y sin IVA, y si dura más de un año, indicar ejercicios.\n"
        "- plazo de presentación de la oferta: solo fecha y hora límite.\n"
        "- criterios de valoración: esquema con bullets.\n"
        "- resumen de trabajos o servicios a contratar: bullets.\n"
        "- prórroga: sí/no, e indicar duración si aplica.\n"
        "- requisitos de solvencia técnica: bullets, incluir referencia general a página.\n"
        "- acreditación de solvencia técnica: bullets, incluir referencia general a página.\n"
        "- requisitos de solvencia económica: bullets, incluir referencia general a página.\n"
        "- acreditación de solvencia económica: bullets, incluir referencia general a página.\n"
        "- esquema nacional de seguridad: sí/no, incluir nivel si aplica.\n"
        "- equipo de trabajo: bullets, formación y años de experiencia, referencia general a página.\n"
        "- acreditación del equipo de trabajo: bullets, referencia general a página.\n"
        "- nombre carpeta: igual.\n\n"
        "Texto a analizar:\n{document}\n\n"
        "Devuelve únicamente un JSON bien formado siguiendo estas reglas, sin texto adicional."
    )
)


prompt_template_final = PromptTemplate(
    input_variables=["partial_json"],
    template=(
        "Se han extraído múltiples respuestas parciales de una licitación en JSON. "
        "Fusiona todas en un único JSON limpio, siguiendo estas reglas:\n\n"
        "- Mantener la estructura y formato definido.\n"
        "- Campo 'cliente' debe incluir los subcampos Entidad, Responsable, Forma de contacto, Teléfono, Fax, Correo Electrónico, Sitio Web, Sede Electrónica.\n"
        "- Evitar duplicados.\n"
        "- Unificar referencias a páginas por campo, no por frase.\n"
        "- Los campos simples (número de expediente, plazo de presentación, prórroga, esquema nacional de seguridad) deben contener solo el dato limpio.\n\n"
        "Devuelve únicamente un JSON final, bien formado.\n\n"
        "Respuestas parciales:\n{partial_json}"
    )
)

# ==========================================
# FUNCIÓN PRINCIPAL
# ==========================================

def combinar_respuestas(respuestas: list[dict]) -> dict:
    """
    Combina múltiples respuestas parciales del modelo en un único diccionario coherente,
    fusionando correctamente listas, diccionarios y textos.
    """
    resultado_final = {}

    for r in respuestas:
        for k, v in r.items():
            if v is None:
                continue

            # Si el campo no existe aún → inicializar directamente
            if k not in resultado_final:
                resultado_final[k] = v
                continue

            existente = resultado_final[k]

            # Caso 1: ambos son listas
            if isinstance(existente, list) and isinstance(v, list):
                resultado_final[k] = existente + v

            # Caso 2: uno es lista y otro no → convertir todo a lista
            elif isinstance(existente, list):
                resultado_final[k].append(v)
            elif isinstance(v, list):
                resultado_final[k] = [existente] + v

            # Caso 3: ambos son diccionarios → fusionar clave a clave
            elif isinstance(existente, dict) and isinstance(v, dict):
                combinado = existente.copy()
                for subk, subv in v.items():
                    if subk not in combinado:
                        combinado[subk] = subv
                    else:
                        # Si ya existe y ambos son listas
                        if isinstance(combinado[subk], list) and isinstance(subv, list):
                            combinado[subk] += subv
                        elif isinstance(combinado[subk], list):
                            combinado[subk].append(subv)
                        elif isinstance(subv, list):
                            combinado[subk] = [combinado[subk]] + subv
                        else:
                            # Combinar texto simple
                            if str(subv).strip() not in str(combinado[subk]):
                                combinado[subk] = f"{combinado[subk]}\n{subv}"
                resultado_final[k] = combinado

            # Caso 4: tipos distintos (texto, número, etc.) → concatenar en string
            else:
                texto_existente = str(existente).strip()
                texto_nuevo = str(v).strip()
                if texto_nuevo not in texto_existente:
                    resultado_final[k] = f"{texto_existente}\n{texto_nuevo}"

    # Finalmente, limpiamos el resultado
    return a_texto_plano_mejorado(resultado_final)


def extract_licitacion_data(carpeta_licitacion: str) -> dict:
    """Extrae información de todos los PDFs de una licitación usando chunking y consolidación."""
    print(f"📁 Procesando carpeta: {carpeta_licitacion}")
    texto = extraer_texto_pdfs(carpeta_licitacion)
    chunks = dividir_en_chunks(texto)
    print(f"📚 Dividido en {len(chunks)} chunks.")

    respuestas_parciales = []

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
                    print(f"⚠️ Error parseando chunk {i}: {e}")
        except Exception as e:
            print(f"⚠️ Error analizando chunk {i}: {e}")

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
                except:
                    resultado_final = combinar_respuestas(respuestas_parciales)
            else:
                resultado_final = combinar_respuestas(respuestas_parciales)
        except:
            resultado_final = combinar_respuestas(respuestas_parciales)
    else:
        print(f"⚠️ No se pudieron extraer datos de la licitación {carpeta_licitacion}")
        resultado_final = {"nombre_carpeta": os.path.basename(carpeta_licitacion)}

    # Siempre agregar nombre de la carpeta
    resultado_final["nombre_carpeta"] = os.path.basename(carpeta_licitacion)
    return a_texto_plano_mejorado(resultado_final)
