"""Req. 4 — el visor trae el slider dona -> taza (0 a 1) y la etiqueta de la figura."""
import re

import pytest


@pytest.fixture
def html(cliente_modelado) -> str:
    r = cliente_modelado.get("/view")
    assert r.status_code == 200
    return r.text


def atributo(html: str, id_: str, nombre: str) -> str | None:
    etiqueta = re.search(rf'<[^>]*\bid="{id_}"[^>]*>', html, re.DOTALL)
    assert etiqueta, f"no se encontró #{id_}"
    valor = re.search(rf'\b{nombre}="([^"]*)"', etiqueta.group(0))
    return valor.group(1) if valor else None


def test_slider_va_de_0_a_1(html):
    assert atributo(html, "morph-slider", "type") == "range"
    assert atributo(html, "morph-slider", "min") == "0"
    assert atributo(html, "morph-slider", "max") == "1"
    assert atributo(html, "morph-slider", "value") == "0"
    assert float(atributo(html, "morph-slider", "step")) == 0.01


def test_hay_etiqueta_con_el_nombre_de_la_figura(html):
    assert 'id="figura-nombre"' in html
    assert re.search(r"Figura:\s*<strong id=\"figura-nombre\"", html)


def test_controles_para_guardar_y_cargar(html):
    assert atributo(html, "figura-input", "maxlength") == "50"
    assert 'id="guardar-figura"' in html
    assert 'id="figuras-select"' in html
    assert 'id="cargar-figura"' in html


def test_viewer_js_usa_10000_puntos_y_acota_t(cliente_modelado):
    js = cliente_modelado.get("/static/viewer.js").text
    assert "const RESOLUCION_MORPH = 100;" in js
    assert "Math.min(1, Math.max(0, t))" in js
    assert "tipo: 'morph'" in js


def test_csp_sigue_sin_estilos_ni_scripts_en_linea(cliente_modelado, html):
    assert "style=" not in html
    assert re.search(r"<script>(?!</script>)", html) is None
    csp = cliente_modelado.get("/view").headers["content-security-policy"]
    assert "script-src 'self'" in csp
    assert "unsafe-inline" not in csp
