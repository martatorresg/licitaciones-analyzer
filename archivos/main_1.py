import os
import pandas as pd
from pdf_loader import extract_text_from_pdf
from extractor import extract_licitacion_data

# Ruta base donde están las carpetas de licitaciones
DATA_DIR = "data"
EXCEL_FILE = "resultados_licitaciones.xlsx"


def procesar_licitacion(pdf_path: str) -> dict:
    """Extrae los datos de un PDF concreto."""
    print(f"📄 Procesando: {pdf_path}")
    text = extract_text_from_pdf(pdf_path)
    data = extract_licitacion_data(text)
    return data


def obtener_licitaciones():
    """Recorre las carpetas dentro de /data y busca PDFs."""
    licitaciones = []
    for folder in os.listdir(DATA_DIR):
        folder_path = os.path.join(DATA_DIR, folder)
        if os.path.isdir(folder_path):
            # Busca el primer PDF en la carpeta
            for file in os.listdir(folder_path):
                if file.lower().endswith(".pdf"):
                    licitaciones.append(os.path.join(folder_path, file))
                    break
    return licitaciones


def guardar_en_excel(datos_nuevos: list[dict]):
    """Guarda los datos nuevos sin borrar los existentes y unifica nombres de columnas."""
    
    # 🔹 Normalizar claves en los resultados nuevos
    datos_normalizados = []
    for d in datos_nuevos:
        nuevo = {}
        for k, v in d.items():
            k_limpio = k.strip().lower()

            # Normalización de claves comunes
            if k_limpio in ["cliente", "organo de contratacion", "cliente (organo de contratacion)", "cliente (órgano de contratación)"]:
                k_limpio = "cliente (órgano de contratación)"
            elif "numero" in k_limpio and "expediente" in k_limpio:
                k_limpio = "número de expediente"
            elif "clasificacion" in k_limpio:
                k_limpio = "clasificación cpv"
            elif "valor" in k_limpio and "sin" in k_limpio:
                k_limpio = "valor estimado del contrato (sin iva)"
            elif "valor" in k_limpio and "iva" in k_limpio and "sin" not in k_limpio:
                k_limpio = "valor del contrato con iva"
            elif "plazo" in k_limpio:
                k_limpio = "plazo de presentación de la oferta (fecha límite)"

            nuevo[k_limpio] = v
        datos_normalizados.append(nuevo)

    # 🔹 Si ya existe el Excel, lo cargamos
    if os.path.exists(EXCEL_FILE):
        df_existente = pd.read_excel(EXCEL_FILE)
    else:
        df_existente = pd.DataFrame()

    # 🔹 Convertimos a DataFrame
    df_nuevos = pd.DataFrame(datos_normalizados)

    # 🔹 Evitar duplicados por número de expediente
    if "número de expediente" in df_existente.columns and "número de expediente" in df_nuevos.columns:
        expedientes_existentes = set(df_existente["número de expediente"].dropna())
        df_nuevos = df_nuevos[~df_nuevos["número de expediente"].isin(expedientes_existentes)]

    # 🔹 Concatenar y guardar
    df_final = pd.concat([df_existente, df_nuevos], ignore_index=True)

    # 🔹 Unificar columnas duplicadas ("cliente" y "cliente (órgano de contratación)")
    if "cliente" in df_final.columns and "cliente (órgano de contratación)" in df_final.columns:
        df_final["cliente (órgano de contratación)"] = df_final["cliente (órgano de contratación)"].combine_first(df_final["cliente"])
        df_final.drop(columns=["cliente"], inplace=True)

    # 🔹 Guardar
    df_final.to_excel(EXCEL_FILE, index=False)
    print(f"💾 Datos guardados en '{EXCEL_FILE}' ({len(df_final)} registros totales)")



def main():
    print("🚀 Iniciando extracción de múltiples licitaciones...\n")

    pdfs = obtener_licitaciones()
    if not pdfs:
        print("⚠️ No se encontraron PDFs en las subcarpetas dentro de /data.")
        return

    resultados = []
    for pdf in pdfs:
        datos = procesar_licitacion(pdf)
        if "error" not in datos:
            resultados.append(datos)
        else:
            print(f"⚠️ Error procesando {pdf}: {datos['error']}")

    if resultados:
        guardar_en_excel(resultados)
    else:
        print("⚠️ No se obtuvieron resultados válidos.")


if __name__ == "__main__":
    main()
