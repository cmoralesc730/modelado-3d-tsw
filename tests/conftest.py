"""Fixtures compartidas: cargan las dos apps en el mismo proceso, sin Docker.

calculadora-de-matrices y modelado-3d tienen módulos con el mismo nombre
(main, security), así que cada app se importa por separado y sus módulos se
sacan de sys.modules para que no se pisen.

MongoDB se apunta a un puerto cerrado: las pruebas nunca tocan la base real.
Las figuras se guardan en un repositorio en memoria (fixture `figuras`).
"""
import importlib
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient

# No ensuciar las carpetas de los proyectos con __pycache__
sys.dont_write_bytecode = True

os.environ["MONGO_URL"] = "mongodb://127.0.0.1:9"   # nadie escucha: Mongo "caído"
os.environ["MONGO_TIMEOUT_MS"] = "200"
os.environ["MONGO_REINTENTO_SEG"] = "3600"

RAIZ = Path(__file__).resolve().parents[1]
CALCULADORA = RAIZ / "calculadora-de-matrices"
MODELADO = RAIZ / "modelado-3d"
ORIGEN_VISOR = "http://localhost:8001"

# Paquetes/módulos de primer nivel que existen en alguno de los dos proyectos
_PROPIOS = {"main", "security", "models", "repository", "services", "database", "morph_relay"}


def _es_propio(nombre: str) -> bool:
    return nombre.split(".")[0] in _PROPIOS


def cargar_app(carpeta: Path) -> SimpleNamespace:
    """Importa main.py de `carpeta` y devuelve sus módulos aislados."""
    previos = {k: sys.modules.pop(k) for k in list(sys.modules) if _es_propio(k)}
    cwd = os.getcwd()
    sys.path.insert(0, str(carpeta))
    os.chdir(carpeta)   # StaticFiles valida su carpeta al importar
    try:
        importlib.import_module("main")
        modulos = {k: sys.modules.pop(k) for k in list(sys.modules) if _es_propio(k)}
    finally:
        os.chdir(cwd)
        sys.path.remove(str(carpeta))
        sys.modules.update(previos)
    return SimpleNamespace(main=modulos["main"], modulos=modulos, carpeta=carpeta)


@pytest.fixture(scope="session")
def calc() -> SimpleNamespace:
    return cargar_app(CALCULADORA)


@pytest.fixture(scope="session")
def modelado() -> SimpleNamespace:
    return cargar_app(MODELADO)


@pytest.fixture(scope="session")
def morph(calc):
    """Módulo services.morph de la calculadora."""
    return calc.modulos["services.morph"]


class FigurasEnMemoria:
    """Mismo contrato que FiguraRepository, sin MongoDB."""

    def __init__(self, repo_mod):
        self._mod = repo_mod
        self._datos: dict[str, dict] = {}
        self._contador = 0

    def guardar(self, figura: dict) -> dict:
        clave = self._mod.clave(figura["nombre"])
        if clave in self._datos:
            raise self._mod.FiguraDuplicada()
        self._contador += 1
        doc = {**figura, "creado_en": f"2026-01-01T00:00:{self._contador:02d}+00:00"}
        self._datos[clave] = doc
        return dict(doc)

    def obtener(self, nombre: str) -> dict | None:
        doc = self._datos.get(self._mod.clave(nombre))
        return dict(doc) if doc else None

    def listar(self) -> list[dict]:
        docs = sorted(self._datos.values(), key=lambda d: d["creado_en"], reverse=True)
        return [{k: v for k, v in d.items() if k != "vertices"} for d in docs]

    def eliminar(self, nombre: str) -> bool:
        return self._datos.pop(self._mod.clave(nombre), None) is not None


@pytest.fixture
def figuras(calc, monkeypatch) -> FigurasEnMemoria:
    repo = FigurasEnMemoria(calc.modulos["repository.figura_repository"])
    monkeypatch.setattr(calc.main, "figuras", repo)
    return repo


@pytest.fixture
def cliente_calc(calc, monkeypatch) -> TestClient:
    monkeypatch.chdir(calc.carpeta)   # la calculadora sirve web/ con rutas relativas
    return TestClient(calc.main.app)


def _cliente_hacia(app) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://calculadora")


@pytest.fixture
def cliente_modelado(modelado, monkeypatch):
    """modelado-3d con la calculadora real servida en memoria."""
    monkeypatch.chdir(modelado.carpeta)   # /view y los CSV usan rutas relativas
    with TestClient(modelado.main.app) as cliente:
        yield cliente


@pytest.fixture
def ws(cliente_modelado, modelado, calc, figuras):
    """WebSocket del visor conectado; modelado-3d habla con la calculadora en memoria."""
    modelado.main.calculadora = _cliente_hacia(calc.main.app)
    with cliente_modelado.websocket_connect("/ws/transform", headers={"origin": ORIGEN_VISOR}) as conexion:
        yield conexion


@pytest.fixture
def ws_sin_calculadora(cliente_modelado, modelado):
    """WebSocket del visor con la calculadora caída (toda petición falla al conectar)."""
    def caida(request):
        raise httpx.ConnectError("conexión rechazada", request=request)

    modelado.main.calculadora = httpx.AsyncClient(transport=httpx.MockTransport(caida),
                                                  base_url="http://calculadora")
    with cliente_modelado.websocket_connect("/ws/transform", headers={"origin": ORIGEN_VISOR}) as conexion:
        yield conexion
