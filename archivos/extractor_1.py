from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import PromptTemplate
from config import GOOGLE_API_KEY
import json
import re


def extract_licitacion_data(text: str) -> dict:
    # 🔹 Crea el modelo con tu API key y versión correcta
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",  # modelo actualizado
        temperature=0,
        google_api_key=GOOGLE_API_KEY
    )

    # 🔹 Define el prompt
    prompt_template = PromptTemplate(
        input_variables=["document"],
        template=(
            "Eres un asistente que extrae información de pliegos de licitaciones públicas. "
            "A partir del siguiente texto, extrae los siguientes campos:\n"
            "- Número de expediente\n"
            "- Cliente (órgano de contratación)\n"
            "- Clasificación CPV\n"
            "- Valor estimado del contrato (sin IVA)\n"
            "- Valor del contrato con IVA\n"
            "- Plazo de presentación de la oferta (fecha límite)\n\n"
            "Devuelve los resultados en formato JSON **puro**, sin texto adicional ni triple comillas.\n\n"
            "Texto del documento:\n{document}"
        ),
    )

    # 🔹 Nueva sintaxis moderna (evita warnings)
    chain = prompt_template | llm
    result = chain.invoke({"document": text})

    # 🔹 Limpieza de posibles ```json ... ``` en la respuesta
    raw_output = result.content if hasattr(result, "content") else str(result)
    clean_output = re.sub(r"^```json|```$", "", raw_output.strip(), flags=re.MULTILINE).strip()

    # 🔹 Intento de convertir a JSON
    try:
        data = json.loads(clean_output)
    except Exception:
        data = {"error": "No se pudo parsear la respuesta del modelo.", "raw_output": raw_output}

    return data
