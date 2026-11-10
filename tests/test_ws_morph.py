"""Req. 3 — relevo del morph por el WebSocket de modelado-3d hacia el visor.

modelado-3d habla con la calculadora real (cargada en memoria), así que
estas pruebas cubren el camino completo visor -> WebSocket -> calculadora.
"""
import pytest
from starlette.websockets import WebSocketDisconnect


def pedir(ws, mensaje):
    ws.send_json(mensaje)
    return ws.receive_json()


# ---------------------------------------------------------------- morph

def test_morph_t0_relevado_es_la_dona_de_10000_puntos(ws, morph):
    r = pedir(ws, {"tipo": "morph", "t": 0})
    assert r["tipo"] == "morph"
    assert r["status"] == "ok"
    assert r["figura"] == "Dona"
    assert r["resolucion"] == 100
    assert r["total_vertices"] == len(r["vertices"]) == 10_000
    assert r["vertices"] == morph.morph(0, 100)


def test_morph_t1_relevado_es_la_taza(ws, morph):
    r = pedir(ws, {"tipo": "morph", "t": 1, "resolucion": 100})
    assert r["figura"] == "Taza"
    assert r["vertices"] == morph.morph(1, 100)


def test_morph_intermedio_con_resolucion(ws, morph):
    r = pedir(ws, {"tipo": "morph", "t": 0.42, "resolucion": 30})
    assert r["figura"] == "Dona → Taza (42%)"
    assert r["total_vertices"] == 900
    assert r["vertices"] == morph.morph(0.42, 30)


def test_varios_morph_seguidos_en_orden(ws):
    for t in (0.1, 0.2, 0.3):
        ws.send_json({"tipo": "morph", "t": t, "resolucion": 8})
    assert [ws.receive_json()["t"] for _ in range(3)] == [0.1, 0.2, 0.3]


@pytest.mark.parametrize("t", [1.2, -0.01, "0.5", None, True, [0.5]])
def test_t_invalido_responde_error_y_no_corta(ws, t):
    r = pedir(ws, {"tipo": "morph", "t": t})
    assert r == {"tipo": "morph", "status": "error", "error": "t debe ser un número entre 0 y 1"}
    assert pedir(ws, {"tipo": "morph", "t": 0.5, "resolucion": 4})["status"] == "ok"


@pytest.mark.parametrize("resolucion", [3, 151, 50.5, "100", True])
def test_resolucion_invalida_responde_error(ws, resolucion):
    r = pedir(ws, {"tipo": "morph", "t": 0.5, "resolucion": resolucion})
    assert r["status"] == "error"
    assert "resolución" in r["error"]


# ---------------------------------------------------------------- transformación (compatibilidad)

def test_mensaje_sin_tipo_sigue_siendo_transformacion(ws):
    r = pedir(ws, {"tx": 0, "ty": 0, "tz": 0, "rx": 0, "ry": 0, "rz": 0})
    assert r["tipo"] == "transform"
    assert r["status"] == "ok"
    identidad = [1.0 if i % 5 == 0 else 0.0 for i in range(16)]
    assert r["matrix"] == pytest.approx(identidad)


def test_traslacion_en_column_major(ws):
    r = pedir(ws, {"tipo": "transform", "tx": 1, "ty": 2, "tz": 3})
    assert r["matrix"][12:15] == pytest.approx([1, 2, 3])


def test_transformacion_con_valores_no_numericos(ws):
    r = pedir(ws, {"tx": "abc"})
    assert r["tipo"] == "transform"
    assert r["status"] == "error"


# ---------------------------------------------------------------- figuras guardadas

def test_guardar_listar_y_cargar_figura(ws, morph):
    guardada = pedir(ws, {"tipo": "guardar_figura", "nombre": "mi taza", "t": 0.75, "resolucion": 20})
    assert guardada["tipo"] == "figura_guardada"
    assert guardada["status"] == "ok"
    assert guardada["nombre"] == "mi taza"
    assert guardada["total_vertices"] == 400
    assert "vertices" not in guardada        # el visor ya los tiene

    lista = pedir(ws, {"tipo": "listar_figuras"})
    assert lista["tipo"] == "figuras"
    assert [f["nombre"] for f in lista["figuras"]] == ["mi taza"]

    cargada = pedir(ws, {"tipo": "cargar_figura", "nombre": "MI TAZA"})
    assert cargada["tipo"] == "morph"
    assert cargada["nombre"] == "mi taza"
    assert cargada["t"] == 0.75
    assert cargada["vertices"] == morph.morph(0.75, 20)


def test_guardar_nombre_repetido(ws):
    pedir(ws, {"tipo": "guardar_figura", "nombre": "Dona", "t": 0})
    r = pedir(ws, {"tipo": "guardar_figura", "nombre": "dona", "t": 1})
    assert r["status"] == "error"
    assert "ya existe" in r["error"]


def test_cargar_figura_inexistente(ws):
    r = pedir(ws, {"tipo": "cargar_figura", "nombre": "nada"})
    assert r == {"tipo": "cargar_figura", "status": "error", "error": "figura no encontrada"}


@pytest.mark.parametrize("nombre", ["", "  ", "<b>", "../x", "x" * 51, None])
def test_guardar_con_nombre_invalido(ws, figuras, nombre):
    r = pedir(ws, {"tipo": "guardar_figura", "nombre": nombre, "t": 0.5})
    assert r["status"] == "error"
    assert "nombre" in r["error"]
    assert figuras.listar() == []


def test_nombre_con_caracteres_de_url_se_codifica(ws):
    pedir(ws, {"tipo": "guardar_figura", "nombre": "taza 50%", "t": 0.5, "resolucion": 4})
    # '%' no es válido como nombre: no se guardó y la consulta tampoco rompe la URL
    r = pedir(ws, {"tipo": "cargar_figura", "nombre": "a b"})
    assert r["error"] == "figura no encontrada"


# ---------------------------------------------------------------- mensajes malformados

def test_json_invalido(ws):
    ws.send_text("no es json{")
    assert ws.receive_json() == {"tipo": "desconocido", "status": "error", "error": "el mensaje no es JSON válido"}
    assert pedir(ws, {"tipo": "morph", "t": 0, "resolucion": 4})["status"] == "ok"


def test_mensaje_que_no_es_objeto(ws):
    assert pedir(ws, [1, 2])["error"] == "el mensaje debe ser un objeto JSON"


def test_tipo_desconocido(ws):
    r = pedir(ws, {"tipo": "borrar_todo"})
    assert r["status"] == "error"
    assert r["error"].startswith("tipo de mensaje desconocido")


# ---------------------------------------------------------------- fallas

def test_calculadora_caida_avisa_y_no_corta(ws_sin_calculadora):
    for mensaje in ({"tipo": "morph", "t": 0.5}, {"tipo": "listar_figuras"}, {"rx": 10}):
        r = pedir(ws_sin_calculadora, mensaje)
        assert r["status"] == "error"
        assert r["error"] == "Calculadora no disponible"


def test_mongo_caido_se_informa_al_guardar(cliente_modelado, modelado, calc):
    """Con el repositorio real (Mongo inalcanzable) el motivo 503 llega al visor."""
    import httpx
    modelado.main.calculadora = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=calc.main.app), base_url="http://calculadora")
    with cliente_modelado.websocket_connect("/ws/transform", headers={"origin": "http://localhost:8001"}) as ws:
        r = pedir(ws, {"tipo": "guardar_figura", "nombre": "x", "t": 0.5})
        assert r["status"] == "error"
        assert "MongoDB no disponible" in r["error"]
        # el morph no depende de Mongo
        assert pedir(ws, {"tipo": "morph", "t": 0.5, "resolucion": 4})["status"] == "ok"


def test_origen_no_permitido_es_rechazado(cliente_modelado):
    with pytest.raises(WebSocketDisconnect) as e, \
            cliente_modelado.websocket_connect("/ws/transform", headers={"origin": "http://evil.example"}) as ws:
        ws.receive_json()
    assert e.value.code == 1008
