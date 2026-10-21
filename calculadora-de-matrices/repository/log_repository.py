# log_repository.py
import re
import time
from datetime import datetime

from bson import ObjectId
from bson.errors import InvalidId
from database import connection
from pymongo import ASCENDING, DESCENDING, MongoClient
from pymongo.errors import PyMongoError
from security import id_publico

# Formato de la cookie de sesión en crudo (uuid4). Los ids públicos son hashes
# hexadecimales sin guiones, así que no coinciden.
_SESION_CRUDA = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


class LogRepository:
    """Persistencia de los logs de ejecución en MongoDB.

    Si Mongo no está disponible la API no se cae: `registrar` devuelve None y
    las consultas devuelven vacío, mientras se reintenta la conexión cada
    REINTENTO_SEG segundos.
    """

    def __init__(self, url: str | None = None, db: str | None = None, coleccion: str | None = None):
        self.url = url or connection.MONGO_URL
        self.nombre_db = db or connection.MONGO_DB
        self.nombre_coleccion = coleccion or connection.COLECCION_LOGS
        # El constructor de MongoClient no abre la conexión, así que no falla acá.
        self._client = MongoClient(
            self.url,
            serverSelectionTimeoutMS=connection.TIMEOUT_MS,
            connectTimeoutMS=connection.TIMEOUT_MS,
            # BSON no guarda la zona: sin esto las fechas vuelven naive y el
            # navegador las interpretaría como hora local en vez de UTC.
            tz_aware=True,
        )
        self._coleccion = self._client[self.nombre_db][self.nombre_coleccion]
        self._disponible = False
        self._error: str | None = None
        self._ultimo_intento = 0.0
        self.conectar()

    # ---------- conexión ----------
    def conectar(self) -> bool:
        self._ultimo_intento = time.monotonic()
        try:
            self._client.admin.command("ping")
            self._coleccion.create_index([("datetime", DESCENDING)])
            self._coleccion.create_index([("session_id", ASCENDING), ("datetime", DESCENDING)])
            self._coleccion.create_index([("fecha_uso", ASCENDING)])
            self._anonimizar_sesiones()
            self._disponible, self._error = True, None
        except PyMongoError as e:
            self._disponible, self._error = False, str(e).split("\n")[0]
        return self._disponible

    def disponible(self) -> bool:
        if not self._disponible and time.monotonic() - self._ultimo_intento > connection.REINTENTO_SEG:
            self.conectar()
        return self._disponible

    def estado(self) -> dict:
        """Estado público: sin URL, nombres internos ni texto de errores."""
        conectado = self.disponible()
        if not conectado and self._error:
            print(f"MongoDB no disponible en {self.url}: {self._error}")
        return {
            "conectado": conectado,
            "total_logs": self.contar() if conectado else 0,
        }

    # ---------- escritura ----------
    def registrar(self, log: dict) -> str | None:
        """Guarda un log. Devuelve su id, o None si Mongo no está disponible."""
        if not self.disponible():
            return None
        try:
            return str(self._coleccion.insert_one(dict(log)).inserted_id)
        except PyMongoError as e:
            self._disponible, self._error = False, str(e).split("\n")[0]
            return None

    # ---------- lectura ----------
    def listar(
        self,
        session_id: str | None = None,
        tipo: str | None = None,
        exitoso: bool | None = None,
        fecha_uso: str | None = None,
        limite: int = 50,
    ) -> list[dict]:
        if not self.disponible():
            return []
        filtro: dict = {}
        if session_id:
            filtro["session_id"] = session_id
        if tipo:
            filtro["operacion.tipo"] = tipo
        if exitoso is not None:
            filtro["resultado.exitoso"] = exitoso
        if fecha_uso:
            filtro["fecha_uso"] = fecha_uso
        try:
            cursor = self._coleccion.find(filtro).sort("datetime", DESCENDING).limit(limite)
            return [self._serializar(d) for d in cursor]
        except PyMongoError:
            return []

    def obtener(self, id: str) -> dict | None:
        if not self.disponible():
            return None
        try:
            doc = self._coleccion.find_one({"_id": ObjectId(id)})
        except (PyMongoError, InvalidId):
            return None
        return self._serializar(doc) if doc else None

    def contar(self, session_id: str | None = None) -> int:
        if not self.disponible():
            return 0
        try:
            return self._coleccion.count_documents({"session_id": session_id} if session_id else {})
        except PyMongoError:
            return 0

    def resumen(self, session_id: str | None = None) -> dict:
        """Totales por operación y por éxito/fallo."""
        if not self.disponible():
            return {"total": 0, "exitosas": 0, "fallidas": 0, "por_operacion": {}, "sesiones": 0}
        filtro = {"session_id": session_id} if session_id else {}
        try:
            etapas = [
                {"$match": filtro},
                {"$group": {
                    "_id": {"tipo": "$operacion.tipo", "exitoso": "$resultado.exitoso"},
                    "n": {"$sum": 1},
                }},
            ]
            por_operacion: dict[str, dict] = {}
            exitosas = fallidas = 0
            for fila in self._coleccion.aggregate(etapas):
                tipo = fila["_id"]["tipo"]
                clave = "exitosas" if fila["_id"]["exitoso"] else "fallidas"
                entrada = por_operacion.setdefault(tipo, {"exitosas": 0, "fallidas": 0})
                entrada[clave] += fila["n"]
                if fila["_id"]["exitoso"]:
                    exitosas += fila["n"]
                else:
                    fallidas += fila["n"]
            return {
                "total": exitosas + fallidas,
                "exitosas": exitosas,
                "fallidas": fallidas,
                "por_operacion": por_operacion,
                "sesiones": len(self._coleccion.distinct("session_id", filtro)),
            }
        except PyMongoError:
            return {"total": 0, "exitosas": 0, "fallidas": 0, "por_operacion": {}, "sesiones": 0}

    # ---------- migración ----------
    def _anonimizar_sesiones(self) -> None:
        """Reemplaza los session_id guardados en crudo (la cookie) por su id público.

        Los logs anteriores guardaban el valor de la cookie y /logs lo exponía.
        Idempotente: solo toca valores con formato uuid.
        """
        for sid in self._coleccion.distinct("session_id"):
            if isinstance(sid, str) and _SESION_CRUDA.match(sid):
                self._coleccion.update_many({"session_id": sid}, {"$set": {"session_id": id_publico(sid)}})

    # ---------- helpers ----------
    @staticmethod
    def _serializar(doc: dict) -> dict:
        doc = dict(doc)
        doc["id"] = str(doc.pop("_id"))
        for campo in ("datetime", "creado_en"):
            if isinstance(doc.get(campo), datetime):
                doc[campo] = doc[campo].isoformat()
        return doc
