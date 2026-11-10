"""Morph dona -> taza como operación de matrices.

Ambas figuras se muestrean sobre la misma malla (u, v) de `resolucion x resolucion`
puntos, así que el vértice k de la dona corresponde al vértice k de la taza.
Cada figura es una matriz N x 3 (una fila por vértice) y el morph es

    V(t) = (1 - t) * D + t * T        con t en [0, 1]

t = 0 da la dona y t = 1 la taza. Las dos figuras son de género 1 (un agujero):
el agujero de la dona termina siendo el de la oreja de la taza.
"""
import math
from functools import lru_cache
from itertools import pairwise

from services.services import escalar, sumar

RESOLUCION_MIN = 4
RESOLUCION_MAX = 150
# 100 x 100 = 10,000 puntos, igual que dona.csv de modelado-3d
RESOLUCION_DEFECTO = 100
DECIMALES = 6

# Dona: toro de radio mayor R y menor r (igual que dona.csv de modelado-3d)
R_DONA = 2.0
r_DONA = 1.0

# Taza: cuerpo de revolución (pared con grosor y fondo) + oreja tubular
RADIO_EXT = 1.6
RADIO_INT = 1.4
Z_FONDO_EXT = -1.6
Z_FONDO_INT = -1.4
Z_BORDE = 1.6
OREJA_CENTRO_Z = 0.1
OREJA_ALTO = 0.9      # semieje vertical de la oreja
OREJA_ANCHO = 0.9     # cuánto sobresale de la pared
OREJA_GROSOR = 0.18   # radio del tubo de la oreja

# Perfil (r, z) de la pared de la taza, recorrido como el círculo del toro:
# arranca afuera a media altura, sube, cruza el borde, baja por dentro,
# cubre el fondo y vuelve por fuera.
PERFIL_TAZA = [
    (RADIO_EXT, 0.0),
    (RADIO_EXT, Z_BORDE),
    (RADIO_INT, Z_BORDE),
    (RADIO_INT, Z_FONDO_INT),
    (0.0, Z_FONDO_INT),
    (0.0, Z_FONDO_EXT),
    (RADIO_EXT, Z_FONDO_EXT),
    (RADIO_EXT, 0.0),
]


def validar(t: float, resolucion: int) -> None:
    if not (isinstance(t, (int, float)) and math.isfinite(t) and 0.0 <= t <= 1.0):
        raise ValueError("t debe estar entre 0 y 1")
    if not (isinstance(resolucion, int) and RESOLUCION_MIN <= resolucion <= RESOLUCION_MAX):
        raise ValueError(f"la resolución debe ser un entero entre {RESOLUCION_MIN} y {RESOLUCION_MAX}")


def filas_oreja(resolucion: int) -> int:
    """Filas u de la malla que forman la oreja (un cuarto); el resto es el cuerpo."""
    return max(2, resolucion // 4)


def _fraccion(j: int, resolucion: int) -> float:
    """j-ésimo de `resolucion` valores de 0 a 1, extremos incluidos (como linspace).

    Es la misma malla que dona.csv: 100 x 100 = 10,000 puntos, donde la
    costura (ángulo 0 y 2*pi) se repite.
    """
    return j / (resolucion - 1)


def _angulo_v(j: int, resolucion: int) -> float:
    return 2 * math.pi * _fraccion(j, resolucion)


@lru_cache(maxsize=16)
def dona(resolucion: int) -> tuple[tuple[float, float, float], ...]:
    """Toro: x = (R + r cos v) cos u, y = (R + r cos v) sin u, z = r sin v."""
    n_oreja = filas_oreja(resolucion)
    puntos = []
    for i in range(resolucion):
        # Las primeras filas (las que serán la oreja) quedan centradas en u = 0 (eje +X).
        # El desfase es entero para que la malla coincida con la de dona.csv.
        u = 2 * math.pi * _fraccion(i - n_oreja // 2, resolucion)
        for j in range(resolucion):
            v = _angulo_v(j, resolucion)
            radio = R_DONA + r_DONA * math.cos(v)
            puntos.append((radio * math.cos(u), radio * math.sin(u), r_DONA * math.sin(v)))
    return tuple(puntos)


def _punto_perfil(fraccion: float) -> tuple[float, float]:
    """Punto del perfil de la taza a una fracción [0, 1] de su perímetro."""
    tramos = list(pairwise(PERFIL_TAZA))
    largos = [math.dist(a, b) for a, b in tramos]
    objetivo = fraccion * sum(largos)
    for (a, b), largo in zip(tramos, largos):
        if objetivo <= largo:
            k = objetivo / largo
            return a[0] + k * (b[0] - a[0]), a[1] + k * (b[1] - a[1])
        objetivo -= largo
    return PERFIL_TAZA[-1]


def _punto_oreja(s: float, v: float) -> tuple[float, float, float]:
    """Tubo alrededor de una semielipse en el plano XZ, pegada a la pared en +X.

    s va de -pi/2 (abajo) a pi/2 (arriba); en esos extremos toca la pared.
    """
    cx = RADIO_EXT + OREJA_ANCHO * math.cos(s)
    cz = OREJA_CENTRO_Z + OREJA_ALTO * math.sin(s)
    # Normal a la curva dentro del plano XZ (perpendicular a la tangente)
    nx, nz = OREJA_ALTO * math.cos(s), OREJA_ANCHO * math.sin(s)
    norma = math.hypot(nx, nz)
    nx, nz = nx / norma, nz / norma
    return (
        cx + OREJA_GROSOR * math.cos(v) * nx,
        OREJA_GROSOR * math.sin(v),
        cz + OREJA_GROSOR * math.cos(v) * nz,
    )


@lru_cache(maxsize=16)
def taza(resolucion: int) -> tuple[tuple[float, float, float], ...]:
    n_oreja = filas_oreja(resolucion)
    n_cuerpo = resolucion - n_oreja
    puntos = []
    for i in range(resolucion):
        for j in range(resolucion):
            v = _angulo_v(j, resolucion)
            if i < n_oreja:
                s = -math.pi / 2 + math.pi * i / (n_oreja - 1)
                puntos.append(_punto_oreja(s, v))
            else:
                u = 2 * math.pi * _fraccion(i - n_oreja, n_cuerpo)
                r, z = _punto_perfil(_fraccion(j, resolucion))
                puntos.append((r * math.cos(u), r * math.sin(u), z))
    return tuple(puntos)


def nombre_figura(t: float) -> str:
    if t == 0:
        return "Dona"
    if t == 1:
        return "Taza"
    return f"Dona → Taza ({round(t * 100)}%)"


def morph(t: float, resolucion: int) -> list[list[float]]:
    """Vértices del morph: (1 - t) * D + t * T, redondeados a DECIMALES."""
    validar(t, resolucion)
    d = [list(p) for p in dona(resolucion)]
    m = [list(p) for p in taza(resolucion)]
    vertices = sumar(escalar(1 - t, d), escalar(t, m))
    return [[round(c, DECIMALES) + 0.0 for c in fila] for fila in vertices]
