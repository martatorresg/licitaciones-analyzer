import os
import pandas as pd
from extractor import extract_licitacion_data

EXCEL_FILE = "resultados_licitaciones_2.xlsx"
DATA_DIR = "data"

def guardar_en_excel(datos_nuevos: list[dict]):
    if os.path.exists(EXCEL_FILE):
        df_existente = pd.read_excel(EXCEL_FILE)
    else:
        df_existente = pd.DataFrame()

    df_nuevos = pd.DataFrame(datos_nuevos)
    df_final = pd.concat([df_existente, df_nuevos], ignore_index=True)
    df_final.to_excel(EXCEL_FILE, index=False)
    print(f"💾 Datos guardados en '{EXCEL_FILE}' ({len(df_final)} registros totales)")

def main():
    resultados = []

    for carpeta in os.listdir(DATA_DIR):
        ruta = os.path.join(DATA_DIR, carpeta)
        if os.path.isdir(ruta):
            print(f"🚀 Procesando licitación: {carpeta}")
            data = extract_licitacion_data(ruta)
            resultados.append(data)

    guardar_en_excel(resultados)

if __name__ == "__main__":
    main()
