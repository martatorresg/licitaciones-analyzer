from dotenv import load_dotenv
import os

load_dotenv()
print(os.getcwd())  # Muestra la ruta actual
print(os.listdir()) # Muestra los archivos en la carpeta
print(os.getenv("GOOGLE_API_KEY"))
