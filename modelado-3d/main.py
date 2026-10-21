import csv
import os
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
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
 
 
@app.websocket("/ws/transform")
async def websocket_transform(websocket: WebSocket):
    """Canal WebSocket para recibir parámetros de movimiento y enviar matrices 4x4."""
    # Los navegadores no aplican CORS a WebSocket: se valida el Origin a mano
    if not security.origen_permitido(websocket.headers.get("origin")):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_json()
 
            # Extraer traslaciones y rotaciones recibidas
            parametros = {clave: float(data.get(clave, 0.0)) for clave in ("tx", "ty", "tz", "rx", "ry", "rz")}

            # La calculadora arma la matriz 4x4
            try:
                matrix_4x4 = await obtener_matriz_transformacion(parametros)
            except (httpx.HTTPError, KeyError, ValueError) as e:
                # El detalle (URL interna, excepción) queda solo en el log del servidor
                print(f"Calculadora no disponible en {CALCULADORA_URL}: {e!r}")
                await websocket.send_json({
                    "status": "error",
                    "error": "Calculadora no disponible"
                })
                continue

            # Responder con la matriz procesada
            await websocket.send_json({
                "matrix": matrix_4x4,
                "status": "ok"
            })
    except WebSocketDisconnect:
        print("Cliente WebSocket desconectado")
 
@app.get("/view", response_class=HTMLResponse)
def serve_viewer():
    """Servidor web directo para ver la interfaz 3D."""
    with open("index.html", "r", encoding="utf-8") as f:
        return f.read()