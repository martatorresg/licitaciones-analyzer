import os
import pandas as pd
from extractor import extract_licitacion_data
from openpyxl.styles import Alignment

EXCEL_FILE = "resultados_licitaciones_3.xlsx"
DATA_DIR = "data"

def guardar_en_excel(datos_nuevos: list[dict]):
    df_nuevos = pd.DataFrame(datos_nuevos)

    # Si existe archivo, cargamos y concatenamos
    if os.path.exists(EXCEL_FILE):
        df_existente = pd.read_excel(EXCEL_FILE)
        df_final = pd.concat([df_existente, df_nuevos], ignore_index=True)
    else:
        df_final = df_nuevos

    # Guardar en Excel usando 'with' (sin writer.save())
    with pd.ExcelWriter(EXCEL_FILE, engine='openpyxl') as writer:
        df_final.to_excel(writer, index=False, sheet_name="Licitaciones")

        # Ajustar formato de celdas con saltos de línea
        ws = writer.sheets["Licitaciones"]
        for row in ws.iter_rows():
            for cell in row:
                if isinstance(cell.value, str) and '\n' in cell.value:
                    cell.alignment = Alignment(wrap_text=True)

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
