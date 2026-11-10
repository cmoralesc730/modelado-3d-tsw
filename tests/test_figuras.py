"""Req. 2 — guardar una figura con nombre en la calculadora y consultarla después."""
import pytest


def guardar(cliente, nombre="mi taza", t=1.0, resolucion=10):
    return cliente.post("/figuras", json={"nombre": nombre, "t": t, "resolucion": resolucion})


def test_guardar_figura_devuelve_201_con_vertices(cliente_calc, figuras, morph):
    r = guardar(cliente_calc, "mi taza", t=0.6, resolucion=12)
    assert r.status_code == 201
    data = r.json()
    assert data["nombre"] == "mi taza"
    assert data["t"] == 0.6
    assert data["resolucion"] == 12
    assert data["figura"] == "Dona → Taza (60%)"
    assert data["total_vertices"] == 144
    assert data["vertices"] == morph.morph(0.6, 12)
    assert data["creado_en"]


def test_resolucion_por_defecto_guarda_10000_puntos(cliente_calc, figuras):
    r = cliente_calc.post("/figuras", json={"nombre": "taza completa", "t": 1})
    assert r.status_code == 201
    assert r.json()["total_vertices"] == 10_000


def test_consultar_figura_guardada(cliente_calc, figuras):
    guardado = guardar(cliente_calc, "Taza Azul", t=0.8).json()
    r = cliente_calc.get("/figuras/Taza Azul")
    assert r.status_code == 200
    assert r.json() == guardado


def test_consulta_sin_distinguir_mayusculas_ni_espacios(cliente_calc, figuras):
    guardar(cliente_calc, "  Taza   Azul ")
    r = cliente_calc.get("/figuras/taza azul")
    assert r.status_code == 200
    assert r.json()["nombre"] == "Taza Azul"   # se guarda sin espacios sobrantes


def test_nombre_repetido_da_409(cliente_calc, figuras):
    assert guardar(cliente_calc, "Dona rica").status_code == 201
    r = guardar(cliente_calc, "DONA RICA", t=0.2)
    assert r.status_code == 409
    assert "ya existe" in r.json()["detail"]
    # la original no cambió
    assert cliente_calc.get("/figuras/dona rica").json()["t"] == 1.0


def test_listar_figuras_sin_vertices_mas_nuevas_primero(cliente_calc, figuras):
    guardar(cliente_calc, "primera", t=0.1)
    guardar(cliente_calc, "segunda", t=0.9)
    r = cliente_calc.get("/figuras")
    assert r.status_code == 200
    lista = r.json()
    assert [f["nombre"] for f in lista] == ["segunda", "primera"]
    assert all("vertices" not in f for f in lista)
    assert lista[0]["total_vertices"] == 100


def test_listar_vacio(cliente_calc, figuras):
    assert cliente_calc.get("/figuras").json() == []


def test_figura_inexistente_da_404(cliente_calc, figuras):
    r = cliente_calc.get("/figuras/no-existe")
    assert r.status_code == 404
    assert r.json()["detail"] == "figura no encontrada"


def test_eliminar_figura(cliente_calc, figuras):
    guardar(cliente_calc, "temporal")
    assert cliente_calc.delete("/figuras/temporal").status_code == 200
    assert cliente_calc.get("/figuras/temporal").status_code == 404
    assert cliente_calc.delete("/figuras/temporal").status_code == 404


@pytest.mark.parametrize("nombre", ["Taza de café", "ñandú_2", "v1.0-final", "A"])
def test_nombres_validos(cliente_calc, figuras, nombre):
    assert guardar(cliente_calc, nombre).status_code == 201
    assert cliente_calc.get(f"/figuras/{nombre}").status_code == 200


@pytest.mark.parametrize("nombre", ["", "   ", "<script>", "../x", ".oculto", "a/b", "x" * 51, None, 123])
def test_nombres_invalidos_dan_422(cliente_calc, figuras, nombre):
    assert guardar(cliente_calc, nombre).status_code == 422
    assert cliente_calc.get("/figuras").json() == []


@pytest.mark.parametrize(("t", "resolucion"), [(-0.1, 10), (1.5, 10), (0.5, 3), (0.5, 151)])
def test_parametros_invalidos_no_guardan(cliente_calc, figuras, t, resolucion):
    assert guardar(cliente_calc, "mala", t=t, resolucion=resolucion).status_code == 422
    assert cliente_calc.get("/figuras").json() == []


# ------------------------------------------------- MongoDB caído (repo real)

def test_sin_mongo_responde_503(cliente_calc):
    """Sin el fixture `figuras` se usa FiguraRepository contra un Mongo inalcanzable."""
    assert guardar(cliente_calc).status_code == 503
    assert cliente_calc.get("/figuras").status_code == 503
    assert cliente_calc.get("/figuras/x").status_code == 503
    r = cliente_calc.delete("/figuras/x")
    assert r.status_code == 503
    assert "MongoDB no disponible" in r.json()["detail"]


def test_sin_mongo_el_morph_sigue_funcionando(cliente_calc):
    assert cliente_calc.post("/operaciones/morph", json={"t": 0.5, "resolucion": 8}).status_code == 200


@pytest.mark.parametrize(("nombre", "clave"), [
    ("Mi Taza", "mi taza"), ("  mi   taza  ", "mi taza"), ("ÑANDÚ", "ñandú"),
])
def test_clave_normaliza_el_nombre(calc, nombre, clave):
    assert calc.modulos["repository.figura_repository"].clave(nombre) == clave
