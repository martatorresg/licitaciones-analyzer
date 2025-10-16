import os
from dotenv import load_dotenv

# Carga el .env desde la misma carpeta del script
env_path = os.path.join(os.path.dirname(__file__), ".env")
load_dotenv(dotenv_path=env_path)

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

if not GOOGLE_API_KEY:
    raise ValueError(
        f"No se encontró la variable GOOGLE_API_KEY en el entorno. "
        f"Ruta del .env probada: {env_path}"
    )
