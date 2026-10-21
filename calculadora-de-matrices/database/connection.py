# connection.py
import os

MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
MONGO_DB = os.getenv("MONGO_DB", "matrices")
COLECCION_LOGS = os.getenv("MONGO_COLECCION_LOGS", "logs_ejecucion")

# Tiempo de espera corto: si Mongo no responde la API tiene que seguir
# atendiendo las operaciones de matrices igual.
TIMEOUT_MS = int(os.getenv("MONGO_TIMEOUT_MS", "2000"))

# Segundos a esperar antes de reintentar la conexión cuando está caída.
REINTENTO_SEG = int(os.getenv("MONGO_REINTENTO_SEG", "30"))
