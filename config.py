import os
from dotenv import load_dotenv

# Carga el .env
env_path = os.path.join(os.path.dirname(__file__), ".env")
load_dotenv(dotenv_path=env_path)

# Claves de API
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME")

# Validaciones
if not GOOGLE_API_KEY:
    raise ValueError(f"No se encontró GOOGLE_API_KEY en {env_path}")

if not PINECONE_API_KEY:
    raise ValueError(f"No se encontró PINECONE_API_KEY en {env_path}")

if not PINECONE_INDEX_NAME:
    raise ValueError(f"No se encontró PINECONE_INDEX_NAME en {env_path}")