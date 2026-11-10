"""Relevo del morph dona -> taza y de las figuras guardadas hacia el visor.

El visor manda por el WebSocket mensajes con un "tipo"; este módulo los
valida, se los pasa a la Calculadora de Matrices y arma la respuesta que
vuelve al visor. Se valida acá también (no solo en la calculadora) para
no gastar una petición en datos que ya se sabe que son inválidos.

    {"tipo": "morph", "t": 0.5, "resolucion": 100}
    {"tipo": "guardar_figura", "nombre": "mi taza", "t": 1, "resolucion": 100}
    {"tipo": "cargar_figura", "nombre": "mi taza"}
    {"tipo": "listar_figuras"}
"""
import math
import re
from collections.abc import Awaitable, Callable
from urllib.parse import quote

import httpx

RESOLUCION_MIN = 4
RESOLUCION_MAX = 150
# 100 x 100 = 10,000 puntos, igual que dona.csv
RESOLUCION_DEFECTO = 100
NOMBRE_MAX = 50
# Mismo formato que exige la calculadora (models.FiguraCreate)
NOMBRE_VALIDO = re.compile(r"^\w[\w .\-]*$")


class MensajeInvalido(ValueError):
    """El mensaje del visor no cumple el formato esperado."""


class ErrorCalculadora(Exception):
    """La calculadora rechazó la petición con un motivo que se puede mostrar."""

    def __init__(self, mensaje: str):
        super().__init__(mensaje)
        self.mensaje = mensaje


def _es_numero(valor) -> bool:
    return isinstance(valor, (int, float)) and not isinstance(valor, bool) and math.isfinite(valor)


def leer_t(data: dict) -> float:
    t = data.get("t")
    if not _es_numero(t) or not 0.0 <= t <= 1.0:
        raise MensajeInvalido("t debe ser un número entre 0 y 1")
    return float(t)


def leer_resolucion(data: dict) -> int:
    resolucion = data.get("resolucion", RESOLUCION_DEFECTO)
    if isinstance(resolucion, bool) or not isinstance(resolucion, int) \
            or not RESOLUCION_MIN <= resolucion <= RESOLUCION_MAX:
        raise MensajeInvalido(
            f"la resolución debe ser un entero entre {RESOLUCION_MIN} y {RESOLUCION_MAX}"
        )
    return resolucion


def leer_nombre(data: dict) -> str:
    nombre = data.get("nombre")
    nombre = " ".join(nombre.split()) if isinstance(nombre, str) else ""
    if not nombre or len(nombre) > NOMBRE_MAX:
        raise MensajeInvalido(f"el nombre de la figura debe tener entre 1 y {NOMBRE_MAX} caracteres")
    if not NOMBRE_VALIDO.match(nombre):
        raise MensajeInvalido(
            "el nombre solo admite letras, números, espacios, '.', '-' y '_', y empieza con letra o número"
        )
    return nombre


async def _pedir(cliente: httpx.AsyncClient, metodo: str, ruta: str, **kwargs):
    """Hace la petición a la calculadora.

    Los rechazos con motivo (400/404/409/422/503) se convierten en
    ErrorCalculadora para mostrarlos en el visor; los demás fallos se
    propagan como httpx.HTTPError ("Calculadora no disponible").
    """
    respuesta = await cliente.request(metodo, ruta, **kwargs)
    if respuesta.status_code in (400, 404, 409, 422, 503):
        try:
            detalle = respuesta.json().get("detail")
        except ValueError:
            detalle = None
        if respuesta.status_code == 422 or not isinstance(detalle, str):
            detalle = "la calculadora rechazó los datos enviados"
        raise ErrorCalculadora(detalle)
    respuesta.raise_for_status()
    return respuesta.json()


async def morph(cliente: httpx.AsyncClient, data: dict) -> dict:
    """Vértices del morph para (t, resolucion), calculados por la calculadora."""
    parametros = {"t": leer_t(data), "resolucion": leer_resolucion(data)}
    resultado = await _pedir(cliente, "POST", "/operaciones/morph", json=parametros)
    return {"tipo": "morph", "status": "ok", **resultado}


async def guardar_figura(cliente: httpx.AsyncClient, data: dict) -> dict:
    cuerpo = {"nombre": leer_nombre(data), "t": leer_t(data), "resolucion": leer_resolucion(data)}
    figura = await _pedir(cliente, "POST", "/figuras", json=cuerpo)
    figura.pop("vertices", None)  # el visor ya los tiene: solo se confirma
    return {"tipo": "figura_guardada", "status": "ok", **figura}


async def cargar_figura(cliente: httpx.AsyncClient, data: dict) -> dict:
    """Figura guardada; se responde como un morph más, con su nombre."""
    nombre = leer_nombre(data)
    figura = await _pedir(cliente, "GET", f"/figuras/{quote(nombre, safe='')}")
    return {"tipo": "morph", "status": "ok", **figura}


async def listar_figuras(cliente: httpx.AsyncClient, _: dict) -> dict:
    figuras = await _pedir(cliente, "GET", "/figuras")
    return {"tipo": "figuras", "status": "ok", "figuras": figuras}


MANEJADORES: dict[str, Callable[[httpx.AsyncClient, dict], Awaitable[dict]]] = {
    "morph": morph,
    "guardar_figura": guardar_figura,
    "cargar_figura": cargar_figura,
    "listar_figuras": listar_figuras,
}
