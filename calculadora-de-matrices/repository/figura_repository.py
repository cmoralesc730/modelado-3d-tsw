# figura_repository.py
import time
from datetime import UTC, datetime

from database import connection
from pymongo import ASCENDING, DESCENDING, MongoClient
from pymongo.errors import DuplicateKeyError, PyMongoError


class FiguraDuplicada(Exception):
    """Ya existe una figura con ese nombre (sin distinguir mayúsculas)."""


class MongoNoDisponible(Exception):
    """MongoDB no responde: no se puede guardar ni consultar figuras."""


def clave(nombre: str) -> str:
    """Clave única del nombre: sin espacios sobrantes y sin distinguir mayúsculas."""
    return " ".join(nombre.split()).casefold()


class FiguraRepository:
    """Figuras del morph guardadas con nombre en MongoDB para consultarlas después.

    A diferencia de los logs, guardar una figura sí requiere Mongo: si no
    está disponible se lanza MongoNoDisponible (la API responde 503).
    """

    def __init__(self, url: str | None = None, db: str | None = None, coleccion: str | None = None):
        self._client = MongoClient(
            url or connection.MONGO_URL,
            serverSelectionTimeoutMS=connection.TIMEOUT_MS,
            connectTimeoutMS=connection.TIMEOUT_MS,
            tz_aware=True,
        )
        self._coleccion = self._client[db or connection.MONGO_DB][coleccion or connection.COLECCION_FIGURAS]
        self._disponible = False
        self._ultimo_intento = 0.0
        self.conectar()

    def conectar(self) -> bool:
        self._ultimo_intento = time.monotonic()
        try:
            self._client.admin.command("ping")
            self._coleccion.create_index([("clave", ASCENDING)], unique=True)
            self._coleccion.create_index([("creado_en", DESCENDING)])
            self._disponible = True
        except PyMongoError:
            self._disponible = False
        return self._disponible

    def disponible(self) -> bool:
        if not self._disponible and time.monotonic() - self._ultimo_intento > connection.REINTENTO_SEG:
            self.conectar()
        return self._disponible

    def _exigir(self) -> None:
        if not self.disponible():
            raise MongoNoDisponible()

    def guardar(self, figura: dict) -> dict:
        self._exigir()
        doc = {**figura, "clave": clave(figura["nombre"]), "creado_en": datetime.now(UTC)}
        try:
            self._coleccion.insert_one(doc)
        except DuplicateKeyError as e:
            raise FiguraDuplicada() from e
        except PyMongoError as e:
            self._disponible = False
            raise MongoNoDisponible() from e
        return self._serializar(doc)

    def obtener(self, nombre: str) -> dict | None:
        self._exigir()
        try:
            doc = self._coleccion.find_one({"clave": clave(nombre)})
        except PyMongoError as e:
            self._disponible = False
            raise MongoNoDisponible() from e
        return self._serializar(doc) if doc else None

    def listar(self) -> list[dict]:
        """Resumen de las figuras guardadas (sin los vértices), las más nuevas primero."""
        self._exigir()
        try:
            cursor = self._coleccion.find({}, {"vertices": 0}).sort("creado_en", DESCENDING)
            return [self._serializar(d) for d in cursor]
        except PyMongoError as e:
            self._disponible = False
            raise MongoNoDisponible() from e

    def eliminar(self, nombre: str) -> bool:
        self._exigir()
        try:
            return self._coleccion.delete_one({"clave": clave(nombre)}).deleted_count == 1
        except PyMongoError as e:
            self._disponible = False
            raise MongoNoDisponible() from e

    @staticmethod
    def _serializar(doc: dict) -> dict:
        doc = {k: v for k, v in doc.items() if k not in ("_id", "clave")}
        if isinstance(doc.get("creado_en"), datetime):
            doc["creado_en"] = doc["creado_en"].isoformat()
        return doc
