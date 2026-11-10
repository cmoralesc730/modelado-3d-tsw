# main.py
import time
from collections.abc import Callable

import security
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from models.models import (
    CadenaMatrices,
    FiguraCreate,
    FiguraOut,
    FiguraResumen,
    LogOut,
    MatrixCreate,
    Morph,
    Transformacion,
)
from repository.figura_repository import (
    FiguraDuplicada,
    FiguraRepository,
    MongoNoDisponible,
)
from repository.log_repository import LogRepository
from repository.repository import MatrixRepository
from services import log_service, morph, services, transformaciones

_docs = security.docs_habilitadas()
app = FastAPI(
    title="Calculadora de Matrices",
    docs_url="/docs" if _docs else None,
    redoc_url="/redoc" if _docs else None,
    openapi_url="/openapi.json" if _docs else None,
)
security.configurar(app)
repo = MatrixRepository()
logs = LogRepository()
figuras = FiguraRepository()

@app.get("/")
def home():
    return FileResponse("web/index.html", media_type="text/html")

@app.get("/matrices")
def listar_matrices():
    return repo.listar()

@app.get("/matrices/{id}")
def obtener_matriz(id: int):
    matriz = repo.obtener(id)
    if not matriz:
        raise HTTPException(404, "matriz no encontrada")
    return matriz

@app.post("/matrices")
def crear_matriz(payload: MatrixCreate):
    return repo.crear(payload.model_dump())

# ---------------------------------------------------------------- operaciones

def _ejecutar(request: Request, tipo: str, metodo: str, ids: dict[str, int], calculo: Callable):
    """Resuelve las matrices, corre la operación y deja el log en MongoDB.

    Registra tanto el éxito como el fallo (matriz inexistente o dimensiones
    incompatibles), para que el historial refleje toda la ejecución.
    """
    registrar = _registrador(request, tipo, metodo, ids)

    matrices: dict[str, dict] = {}
    for clave, valor in ids.items():
        matriz = repo.obtener(valor)
        if not matriz:
            registrar(False, {}, error="matriz no encontrada")
            raise HTTPException(404, "matriz no encontrada")
        matrices[clave] = matriz

    entradas = {c: {"id": m["id"], "nombre": m["nombre"], "datos": m["datos"]} for c, m in matrices.items()}
    return _calcular(registrar, entradas, calculo, [m["datos"] for m in matrices.values()])

def _registrador(request: Request, tipo: str, metodo: str, parametros: dict) -> Callable:
    """Devuelve una función que guarda el log de la operación en MongoDB."""
    endpoint = f"/operaciones/{tipo}"
    session_id = log_service.session_id_de(request)
    inicio = time.perf_counter()

    def registrar(exitoso, entradas, resultado=None, error=None):
        logs.registrar(log_service.construir_log(
            session_id=session_id, tipo=tipo, metodo=metodo, endpoint=endpoint,
            parametros=parametros, entradas=entradas, exitoso=exitoso,
            resultado=resultado, error=error,
            duracion_ms=(time.perf_counter() - inicio) * 1000,
        ))
    return registrar

def _calcular(registrar: Callable, entradas: dict, calculo: Callable, datos: list):
    try:
        resultado = calculo(*datos)
    except ValueError as e:
        registrar(False, entradas, error=str(e))
        raise HTTPException(400, str(e))

    registrar(True, entradas, resultado=resultado)
    return {"resultado": resultado}

@app.post("/operaciones/sumar")
def sumar_matrices(request: Request, id1: int, id2: int):
    return _ejecutar(request, "sumar", "POST", {"id1": id1, "id2": id2}, services.sumar)

@app.post("/operaciones/multiplicar")
def multiplicar_matrices(request: Request, id1: int, id2: int):
    return _ejecutar(request, "multiplicar", "POST", {"id1": id1, "id2": id2}, services.multiplicar)

@app.post("/operaciones/multiplicar-cadena")
def multiplicar_cadena(request: Request, payload: CadenaMatrices):
    """Multiplica matrices enviadas en el cuerpo (M1 @ M2 @ ... @ Mn) sin guardarlas.

    Lo usa el visualizador de modelado-3d para componer su matriz de transformación.
    """
    registrar = _registrador(request, "multiplicar-cadena", "POST", {"cantidad": len(payload.matrices)})
    entradas = {f"m{i + 1}": {"datos": m} for i, m in enumerate(payload.matrices)}
    return _calcular(registrar, entradas, services.multiplicar_cadena, payload.matrices)

@app.post("/operaciones/transformacion")
def matriz_transformacion(request: Request, payload: Transformacion):
    """Arma la matriz 4x4 M = T @ Rz @ Ry @ Rx a partir de traslación y rotaciones (grados).

    Devuelve la matriz por filas y también aplanada en column-major para Three.js.
    Lo usa el visualizador de modelado-3d en cada cuadro.
    """
    parametros = payload.model_dump()
    registrar = _registrador(request, "transformacion", "POST", parametros)
    respuesta = _calcular(registrar, {}, transformaciones.matriz_transformacion, list(parametros.values()))
    respuesta["column_major"] = transformaciones.column_major(respuesta["resultado"])
    return respuesta

def _calcular_morph(registrar: Callable, t: float, resolucion: int) -> dict:
    """Corre el morph y registra el log (sin los vértices, que pesan demasiado)."""
    try:
        vertices = morph.morph(t, resolucion)
    except ValueError as e:
        registrar(False, {}, error=str(e))
        raise HTTPException(400, str(e))
    registrar(True, {})
    return {
        "t": t,
        "resolucion": resolucion,
        "figura": morph.nombre_figura(t),
        "total_vertices": len(vertices),
        "vertices": vertices,
    }

@app.post("/operaciones/morph")
def morph_dona_taza(request: Request, payload: Morph):
    """Vértices del morph dona -> taza: V(t) = (1 - t) * Dona + t * Taza.

    `t` va de 0 (dona) a 1 (taza); `resolucion` es la cantidad de puntos por
    lado de la malla, así que se devuelven resolucion² vértices [x, y, z].
    """
    parametros = payload.model_dump()
    registrar = _registrador(request, "morph", "POST", parametros)
    return _calcular_morph(registrar, payload.t, payload.resolucion)

# ---------------------------------------------------- figuras guardadas (Mongo)

FIGURAS_NO_DISPONIBLE = "MongoDB no disponible: no se pueden guardar ni consultar figuras"

@app.post("/figuras", status_code=201, response_model=FiguraOut)
def guardar_figura(request: Request, payload: FiguraCreate):
    """Calcula el morph para (t, resolucion) y lo guarda con un nombre único."""
    registrar = _registrador(request, "guardar-figura", "POST", payload.model_dump())
    figura = {"nombre": payload.nombre, **_calcular_morph(registrar, payload.t, payload.resolucion)}
    try:
        return figuras.guardar(figura)
    except FiguraDuplicada:
        raise HTTPException(409, f"ya existe una figura llamada '{payload.nombre}'")
    except MongoNoDisponible:
        raise HTTPException(503, FIGURAS_NO_DISPONIBLE)

@app.get("/figuras", response_model=list[FiguraResumen])
def listar_figuras():
    try:
        return figuras.listar()
    except MongoNoDisponible:
        raise HTTPException(503, FIGURAS_NO_DISPONIBLE)

@app.get("/figuras/{nombre}", response_model=FiguraOut)
def obtener_figura(nombre: str):
    try:
        figura = figuras.obtener(nombre)
    except MongoNoDisponible:
        raise HTTPException(503, FIGURAS_NO_DISPONIBLE)
    if not figura:
        raise HTTPException(404, "figura no encontrada")
    return figura

@app.delete("/figuras/{nombre}")
def eliminar_figura(nombre: str):
    try:
        eliminada = figuras.eliminar(nombre)
    except MongoNoDisponible:
        raise HTTPException(503, FIGURAS_NO_DISPONIBLE)
    if not eliminada:
        raise HTTPException(404, "figura no encontrada")
    return {"mensaje": "figura eliminada"}

@app.get("/operaciones/transponer")
def transponer_matriz(request: Request, id: int):
    return _ejecutar(request, "transponer", "GET", {"id": id}, services.transponer)

@app.get("/operaciones/determinante")
def determinante_matriz(request: Request, id: int):
    return _ejecutar(request, "determinante", "GET", {"id": id}, services.determinante)

@app.put("/matrices/{id}")
def actualizar_matriz(id: int, payload: MatrixCreate):
    matriz = repo.obtener(id)
    if not matriz:
        raise HTTPException(404, "matriz no encontrada")
    matriz.update(payload.model_dump())
    return matriz

@app.delete("/matrices/{id}")
def eliminar_matriz(id: int):
    matriz = repo.obtener(id)
    if not matriz:
        raise HTTPException(404, "matriz no encontrada")
    del repo._data[id]
    return {"mensaje": "matriz eliminada"}

# ---------------------------------------------------- log de ejecución (Mongo)

@app.get("/logs/estado")
def estado_logs():
    return logs.estado()

@app.get("/sesion")
def sesion_actual(request: Request):
    """Id público de la sesión: hash de la cookie HttpOnly, que nunca se devuelve."""
    return {"id": log_service.session_id_de(request)}

@app.get("/logs/resumen")
def resumen_logs(request: Request, mia: bool = False):
    return logs.resumen(log_service.session_id_de(request) if mia else None)

@app.get("/logs", response_model=list[LogOut])
def listar_logs(
    request: Request,
    mia: bool = False,
    tipo: str | None = None,
    exitoso: bool | None = None,
    fecha_uso: str | None = None,
    limite: int = Query(50, ge=1, le=500),
):
    if not logs.disponible():
        raise HTTPException(503, "MongoDB no disponible")
    session_id = log_service.session_id_de(request) if mia else None
    return logs.listar(session_id=session_id, tipo=tipo, exitoso=exitoso,
                       fecha_uso=fecha_uso, limite=limite)

@app.get("/logs/{id}", response_model=LogOut)
def obtener_log(id: str):
    if not logs.disponible():
        raise HTTPException(503, "MongoDB no disponible")
    log = logs.obtener(id)
    if not log:
        raise HTTPException(404, "log no encontrado")
    return log

app.mount("/", StaticFiles(directory="web", html=True), name="web")
