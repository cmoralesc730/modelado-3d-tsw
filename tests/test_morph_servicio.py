"""Req. 1 — cálculo del morph dona -> taza (services.morph de la calculadora)."""
import csv
import math

import pytest
from conftest import MODELADO

TOL = 1e-6


def iguales(a, b, tol=TOL) -> bool:
    return len(a) == len(b) and all(
        math.isclose(x, y, abs_tol=tol) for p, q in zip(a, b, strict=True) for x, y in zip(p, q, strict=True)
    )


# ---------------------------------------------------------------- tamaño

@pytest.mark.parametrize("resolucion", [4, 5, 10, 37, 100, 150])
def test_devuelve_resolucion_al_cuadrado_vertices(morph, resolucion):
    vertices = morph.morph(0.5, resolucion)
    assert len(vertices) == resolucion ** 2
    assert all(len(v) == 3 for v in vertices)


def test_resolucion_por_defecto_da_10000_puntos_en_dona_y_taza(morph):
    assert morph.RESOLUCION_DEFECTO == 100
    assert len(morph.morph(0, morph.RESOLUCION_DEFECTO)) == 10_000
    assert len(morph.morph(1, morph.RESOLUCION_DEFECTO)) == 10_000


def test_la_dona_coincide_con_dona_csv(morph):
    """t = 0 con resolución 100 reproduce los mismos 10,000 puntos de dona.csv."""
    with open(MODELADO / "dona.csv", encoding="utf-8") as f:
        csv_puntos = [tuple(float(fila[k]) for k in "xyz") for fila in csv.DictReader(f)]
    dona = morph.morph(0, 100)
    assert len(dona) == len(csv_puntos) == 10_000

    # Cada punto de un lado tiene su gemelo en el otro (a menos de 1e-6)
    assert distancia_maxima(dona, csv_puntos) <= TOL
    assert distancia_maxima(csv_puntos, dona) <= TOL


def distancia_maxima(origen, destino) -> float:
    """Mayor distancia (norma infinito) de un punto de `origen` a su vecino más cercano en `destino`."""
    celdas: dict[tuple, list] = {}
    for p in destino:
        celdas.setdefault(tuple(round(c * 1000) for c in p), []).append(p)
    vecinas = [(a, b, c) for a in (-1, 0, 1) for b in (-1, 0, 1) for c in (-1, 0, 1)]
    peor = 0.0
    for p in origen:
        base = tuple(round(c * 1000) for c in p)
        candidatos = [q for d in vecinas for q in celdas.get(tuple(x + y for x, y in zip(base, d, strict=True)), [])]
        peor = max(peor, min((max(abs(x - y) for x, y in zip(p, q, strict=True)) for q in candidatos), default=math.inf))
    return peor


# ---------------------------------------------------------------- extremos

def test_t0_es_la_dona(morph):
    assert iguales(morph.morph(0, 20), morph.dona(20))


def test_t1_es_la_taza(morph):
    assert iguales(morph.morph(1, 20), morph.taza(20))


def test_dona_es_un_toro_de_radios_2_y_1(morph):
    for x, y, z in morph.dona(30):
        # (sqrt(x² + y²) - R)² + z² = r²
        assert math.isclose((math.hypot(x, y) - 2) ** 2 + z ** 2, 1, abs_tol=1e-9)


def _en_cuerpo_de_taza(morph, x, y, z) -> bool:
    """El punto está sobre la pared, el borde o el fondo de la taza."""
    r = math.hypot(x, y)
    cerca = lambda a, b: math.isclose(a, b, abs_tol=1e-9)
    dentro = lambda v, a, b: a - 1e-9 <= v <= b + 1e-9
    return (
        (cerca(r, morph.RADIO_EXT) and dentro(z, morph.Z_FONDO_EXT, morph.Z_BORDE))
        or (cerca(r, morph.RADIO_INT) and dentro(z, morph.Z_FONDO_INT, morph.Z_BORDE))
        or (cerca(z, morph.Z_BORDE) and dentro(r, morph.RADIO_INT, morph.RADIO_EXT))
        or (cerca(z, morph.Z_FONDO_INT) and dentro(r, 0, morph.RADIO_INT))
        or (cerca(z, morph.Z_FONDO_EXT) and dentro(r, 0, morph.RADIO_EXT))
        or (cerca(r, 0) and dentro(z, morph.Z_FONDO_EXT, morph.Z_FONDO_INT))
    )


def test_taza_cuerpo_sobre_el_perfil_y_oreja_tubular(morph):
    n = 40
    n_oreja = morph.filas_oreja(n)
    taza = morph.taza(n)
    cuerpo, oreja = taza[n_oreja * n:], taza[:n_oreja * n]

    assert all(_en_cuerpo_de_taza(morph, *p) for p in cuerpo)
    # La oreja sale de la pared hacia +X, es angosta en Y y no pasa del borde
    for x, y, z in oreja:
        assert morph.RADIO_EXT - morph.OREJA_GROSOR - TOL <= x
        assert x <= morph.RADIO_EXT + morph.OREJA_ANCHO + morph.OREJA_GROSOR + TOL
        assert abs(y) <= morph.OREJA_GROSOR + TOL
        assert morph.Z_FONDO_EXT <= z <= morph.Z_BORDE


# ---------------------------------------------------------------- interpolación

@pytest.mark.parametrize("t", [0.0, 0.25, 0.5, 0.73, 1.0])
def test_es_combinacion_lineal_de_dona_y_taza(morph, t):
    n = 12
    esperado = [
        [(1 - t) * d + t * m for d, m in zip(pd, pm, strict=True)]
        for pd, pm in zip(morph.dona(n), morph.taza(n), strict=True)
    ]
    assert iguales(morph.morph(t, n), esperado)


def test_mitad_del_morph_es_el_punto_medio(morph):
    n = 10
    medio = morph.morph(0.5, n)
    for v, d, m in zip(medio, morph.dona(n), morph.taza(n), strict=True):
        for c, a, b in zip(v, d, m, strict=True):
            assert math.isclose(c, (a + b) / 2, abs_tol=TOL)


def test_es_deterministico(morph):
    assert morph.morph(0.42, 30) == morph.morph(0.42, 30)


def test_redondea_a_6_decimales_y_sin_menos_cero(morph):
    for v in morph.morph(0.333, 15):
        for c in v:
            assert c == round(c, 6)
            assert math.copysign(1, c) == 1 or c != 0


# ---------------------------------------------------------------- validación

@pytest.mark.parametrize("t", [-0.01, 1.01, -1, 2, math.nan, math.inf, -math.inf])
def test_rechaza_t_fuera_de_0_a_1(morph, t):
    with pytest.raises(ValueError, match="t debe estar entre 0 y 1"):
        morph.morph(t, 10)


@pytest.mark.parametrize("resolucion", [3, 0, -5, 151, 1000, 10.0, "10"])
def test_rechaza_resolucion_invalida(morph, resolucion):
    with pytest.raises(ValueError, match="resolución"):
        morph.morph(0.5, resolucion)


# ---------------------------------------------------------------- nombre y escalar

@pytest.mark.parametrize(("t", "nombre"), [
    (0, "Dona"), (1, "Taza"), (0.5, "Dona → Taza (50%)"), (0.004, "Dona → Taza (0%)"), (0.999, "Dona → Taza (100%)"),
])
def test_nombre_de_la_figura(morph, t, nombre):
    assert morph.nombre_figura(t) == nombre


def test_escalar_por_matriz(calc):
    escalar = calc.modulos["services.services"].escalar
    assert escalar(2, [[1, -2], [0.5, 3]]) == [[2, -4], [1, 6]]
    assert escalar(0, [[1, 2]]) == [[0, 0]]
