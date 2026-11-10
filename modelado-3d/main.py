import csv
import json
import math
import os
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
import morph_relay
import security
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, status
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

# URL de la Calculadora de Matrices (proyecto calculadora-de-matrices)
CALCULADORA_URL = os.getenv("CALCULADORA_URL", "http://localhost:8000").rstrip("/")
# Identifica las peticiones de este proyecto en los logs de la calculadora
SESSION_ID = "modelado-3d"
# Token compartido con la calculadora: sin él, la calculadora ignora X-Session-Id
SERVICIO_TOKEN = os.getenv("SERVICIO_TOKEN", "")

calculadora: httpx.AsyncClient | None = None


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Mantiene un único cliente HTTP (conexiones keep-alive) hacia la calculadora."""
    global calculadora
    calculadora = httpx.AsyncClient(
        base_url=CALCULADORA_URL,
        headers={"X-Session-Id": SESSION_ID, "X-Servicio-Token": SERVICIO_TOKEN},
        timeout=5.0,
    )
    yield
    await calculadora.aclose()


_docs = security.docs_habilitadas()
app = FastAPI(
    title="3D Model & Matrix Transformation API",
    lifespan=lifespan,
    docs_url="/docs" if _docs else None,
    redoc_url="/redoc" if _docs else None,
    openapi_url="/openapi.json" if _docs else None,
)
# Sin CORS: el visualizador (/view) y la API comparten origen.
security.configurar(app)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Decimales con que se sirven los vértices (evita cadenas largas de dígitos)
DECIMALES_VERTICES = 6
 
# Archivos CSV con las coordenadas de cada modelo (en el mismo directorio o volumen Docker)
MODELOS_CSV = {
    "dona": Path("dona.csv"),
    "esfera": Path("esfera.csv"),
    "cubo": Path("cubo.csv"),
}
 
 
def cargar_puntos_csv(path: Path) -> list[list[float]]:
    """Lee un archivo CSV con encabezados x,y,z y retorna una lista de vertices [[x, y, z], ...]."""
    puntos = []
    if not path.exists():
        print(f"Advertencia: No se encontró el archivo {path}")
        return puntos
 
    with open(path, mode="r", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        for row in reader:
            try:
                puntos.append([
                    round(float(row["x"]), DECIMALES_VERTICES),
                    round(float(row["y"]), DECIMALES_VERTICES),
                    round(float(row["z"]), DECIMALES_VERTICES)
                ])
            except (KeyError, ValueError):
                # Omitir filas mal formadas o vacías
                continue
    return puntos
 
 
async def obtener_matriz_transformacion(parametros: dict[str, float]) -> list[float]:
    """Pide a la Calculadora de Matrices la matriz 4x4 (Traslación * Rotación Z-Y-X).

    Devuelve los 16 valores en orden Column-Major, listos para Three.js.
    """
    response = await calculadora.post("/operaciones/transformacion", json=parametros)
    response.raise_for_status()
    return response.json()["column_major"]
 
 
@app.get("/")
def read_root():
    """Endpoint raíz para verificar disponibilidad del servicio."""
    return {
        "status": "online",
        "message": "API de Modelo 3D y Transformaciones Matriciales activa",
        "endpoints": {
            "modelos": "/api/modelos",
            "csv_model": "/api/modelo-csv?modelo=dona",
            "websocket": "/ws/transform",
            "websocket_tipos": ["transform", *morph_relay.MANEJADORES],
            "viewer": "/view"
        }
    }
 
 
@app.get("/api/modelos")
def listar_modelos():
    """Nombres de los modelos CSV disponibles."""
    return list(MODELOS_CSV)


@app.get("/api/modelo-csv")
def obtener_puntos_modelo(modelo: str = "dona"):
    """Devuelve los vértices 3D parseados desde el archivo CSV del modelo pedido."""
    if modelo not in MODELOS_CSV:
        raise HTTPException(404, f"modelo no encontrado; disponibles: {', '.join(MODELOS_CSV)}")
    puntos = cargar_puntos_csv(MODELOS_CSV[modelo])
    return {
        "modelo": modelo,
        "total_puntos": len(puntos),
        "vertices": puntos
    }
 
 
EJES_TRANSFORMACION = ("tx", "ty", "tz", "rx", "ry", "rz")


def leer_transformacion(data: dict) -> dict[str, float]:
    """Traslaciones y rotaciones del mensaje (0 si faltan); deben ser números finitos."""
    parametros = {}
    for clave in EJES_TRANSFORMACION:
        valor = data.get(clave, 0.0)
        if isinstance(valor, bool) or not isinstance(valor, (int, float)) or not math.isfinite(valor):
            raise morph_relay.MensajeInvalido(f"{', '.join(EJES_TRANSFORMACION)} deben ser números")
        parametros[clave] = float(valor)
    return parametros


async def atender_mensaje(data) -> dict:
    """Resuelve un mensaje del visor y devuelve la respuesta (nunca lanza).

    Sin "tipo" (o "transform"): matriz 4x4 de transformación.
    Con "tipo" morph / guardar_figura / cargar_figura / listar_figuras:
    relevo hacia la calculadora (ver morph_relay).
    """
    tipo = data.get("tipo", "transform") if isinstance(data, dict) else None
    if not isinstance(tipo, str):
        tipo = "desconocido"
    try:
        if not isinstance(data, dict):
            raise morph_relay.MensajeInvalido("el mensaje debe ser un objeto JSON")
        if tipo == "transform":
            matrix_4x4 = await obtener_matriz_transformacion(leer_transformacion(data))
            return {"tipo": "transform", "matrix": matrix_4x4, "status": "ok"}
        manejador = morph_relay.MANEJADORES.get(tipo)
        if manejador is None:
            raise morph_relay.MensajeInvalido(f"tipo de mensaje desconocido: {tipo[:30]}")
        return await manejador(calculadora, data)
    except morph_relay.MensajeInvalido as e:
        return {"tipo": tipo, "status": "error", "error": str(e)}
    except morph_relay.ErrorCalculadora as e:
        return {"tipo": tipo, "status": "error", "error": e.mensaje}
    except (httpx.HTTPError, KeyError, ValueError) as e:
        # El detalle (URL interna, excepción) queda solo en el log del servidor
        print(f"Calculadora no disponible en {CALCULADORA_URL}: {e!r}")
        return {"tipo": tipo, "status": "error", "error": "Calculadora no disponible"}


@app.websocket("/ws/transform")
async def websocket_transform(websocket: WebSocket):
    """Canal WebSocket del visor: matrices 4x4 y relevo del morph dona -> taza."""
    # Los navegadores no aplican CORS a WebSocket: se valida el Origin a mano
    if not security.origen_permitido(websocket.headers.get("origin")):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    await websocket.accept()
    try:
        while True:
            texto = await websocket.receive_text()
            try:
                data = json.loads(texto)
            except ValueError:
                await websocket.send_json({"tipo": "desconocido", "status": "error",
                                           "error": "el mensaje no es JSON válido"})
                continue
            await websocket.send_json(await atender_mensaje(data))
    except WebSocketDisconnect:
        print("Cliente WebSocket desconectado")


@app.get("/view", response_class=HTMLResponse)
def serve_viewer():
    """Servidor web directo para ver la interfaz 3D."""
    with open("index.html", "r", encoding="utf-8") as f:
        return f.read()