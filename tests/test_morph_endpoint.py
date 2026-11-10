"""Req. 1 — endpoint POST /operaciones/morph de la calculadora."""
import pytest

URL = "/operaciones/morph"


def test_morph_responde_vertices(cliente_calc):
    r = cliente_calc.post(URL, json={"t": 0.5, "resolucion": 20})
    assert r.status_code == 200
    data = r.json()
    assert data["t"] == 0.5
    assert data["resolucion"] == 20
    assert data["figura"] == "Dona → Taza (50%)"
    assert data["total_vertices"] == 400
    assert len(data["vertices"]) == 400
    assert all(len(v) == 3 and all(isinstance(c, float) for c in v) for v in data["vertices"])


def test_resolucion_por_defecto_es_100_con_10000_puntos(cliente_calc):
    data = cliente_calc.post(URL, json={"t": 1}).json()
    assert data["resolucion"] == 100
    assert data["total_vertices"] == len(data["vertices"]) == 10_000
    assert data["figura"] == "Taza"


@pytest.mark.parametrize(("t", "figura", "fuente"), [(0, "Dona", "dona"), (1, "Taza", "taza")])
def test_extremos_devuelven_dona_y_taza(cliente_calc, morph, t, figura, fuente):
    data = cliente_calc.post(URL, json={"t": t, "resolucion": 10}).json()
    assert data["figura"] == figura
    esperado = [[round(c, 6) + 0.0 for c in p] for p in getattr(morph, fuente)(10)]
    assert data["vertices"] == esperado


def test_coincide_con_el_servicio(cliente_calc, morph):
    data = cliente_calc.post(URL, json={"t": 0.37, "resolucion": 16}).json()
    assert data["vertices"] == morph.morph(0.37, 16)


@pytest.mark.parametrize("cuerpo", [
    {"t": 0, "resolucion": 4},
    {"t": 1, "resolucion": 150},
    {"t": 0.0001, "resolucion": 4},
    {"t": 0.9999, "resolucion": 150},
])
def test_acepta_los_limites(cliente_calc, cuerpo):
    assert cliente_calc.post(URL, json=cuerpo).status_code == 200


@pytest.mark.parametrize("cuerpo", [
    {"t": -0.01, "resolucion": 10},
    {"t": 1.01, "resolucion": 10},
    {"t": "abc", "resolucion": 10},
    {"t": None, "resolucion": 10},
    {"resolucion": 10},
    {"t": 0.5, "resolucion": 3},
    {"t": 0.5, "resolucion": 151},
    {"t": 0.5, "resolucion": 10.5},
    {"t": 0.5, "resolucion": "10"},
    {"t": 0.5, "resolucion": True},
])
def test_rechaza_parametros_invalidos_con_422(cliente_calc, cuerpo):
    r = cliente_calc.post(URL, json=cuerpo)
    assert r.status_code == 422

