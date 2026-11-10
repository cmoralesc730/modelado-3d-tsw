"""E2E del morph dona -> taza en el visor (requiere el sistema levantado con Docker)."""
import json
import urllib.parse
import urllib.request
import uuid

import pytest
from playwright.sync_api import Page, expect


def abrir_visor(page: Page, visor_url: str) -> None:
    page.goto(f"{visor_url}/view")
    expect(page.locator("#ws-status")).to_have_text("Conectado", timeout=5000)


def mover_slider(page: Page, t: str) -> None:
    page.locator("#morph-slider").fill(t)


@pytest.fixture
def nombre_figura(calculadora_url: str):
    """Nombre único para la prueba; la figura se borra al terminar."""
    nombre = f"e2e {uuid.uuid4().hex[:8]}"
    yield nombre
    pedido = urllib.request.Request(
        f"{calculadora_url}/figuras/{urllib.parse.quote(nombre)}", method="DELETE")
    try:
        urllib.request.urlopen(pedido, timeout=5)
    except OSError:
        pass


def test_slider_limitado_de_0_a_1(page: Page, visor_url: str):
    abrir_visor(page, visor_url)
    slider = page.locator("#morph-slider")
    expect(slider).to_have_attribute("min", "0")
    expect(slider).to_have_attribute("max", "1")

    # El navegador recorta los valores fuera de rango al límite
    slider.evaluate("el => { el.value = '5'; el.dispatchEvent(new Event('input')); }")
    expect(page.locator("#morph-t")).to_have_text("1.00")
    expect(page.locator("#figura-nombre")).to_have_text("Taza")
    slider.evaluate("el => { el.value = '-3'; el.dispatchEvent(new Event('input')); }")
    expect(page.locator("#morph-t")).to_have_text("0.00")
    expect(page.locator("#figura-nombre")).to_have_text("Dona")


def test_slider_de_dona_a_taza_con_10000_puntos(page: Page, visor_url: str):
    # Arrange
    abrir_visor(page, visor_url)
    expect(page.locator("#figura-nombre")).to_have_text("Dona")   # modelo CSV inicial

    # Act / Assert: los extremos y un punto intermedio
    mover_slider(page, "1")
    expect(page.locator("#figura-nombre")).to_have_text("Taza")
    expect(page.locator("#point-count")).to_have_text("10000")

    mover_slider(page, "0.5")
    expect(page.locator("#figura-nombre")).to_have_text("Dona → Taza (50%)")
    expect(page.locator("#morph-t")).to_have_text("0.50")

    mover_slider(page, "0")
    expect(page.locator("#figura-nombre")).to_have_text("Dona")
    expect(page.locator("#point-count")).to_have_text("10000")
    expect(page.locator("#calc-status")).to_have_text("Conectada")


def test_mover_rapido_termina_en_el_ultimo_valor(page: Page, visor_url: str):
    abrir_visor(page, visor_url)
    for t in ("0.1", "0.2", "0.3", "0.4", "0.5", "0.6", "0.73"):
        mover_slider(page, t)
    expect(page.locator("#figura-nombre")).to_have_text("Dona → Taza (73%)")


def test_guardar_y_cargar_figura_con_nombre(page: Page, visor_url: str, calculadora_url: str, nombre_figura: str):
    # Arrange
    abrir_visor(page, visor_url)
    mover_slider(page, "0.73")
    expect(page.locator("#figura-nombre")).to_have_text("Dona → Taza (73%)")

    # Act: guardar
    page.get_by_label("Nombre de la figura").fill(nombre_figura)
    page.get_by_role("button", name="Guardar").click()

    # Assert: la etiqueta muestra el nombre y la calculadora la tiene guardada
    expect(page.locator("#morph-msg")).to_have_text(f'Figura "{nombre_figura}" guardada')
    expect(page.locator("#figura-nombre")).to_have_text(nombre_figura)
    with urllib.request.urlopen(f"{calculadora_url}/figuras/{urllib.parse.quote(nombre_figura)}") as r:
        guardada = json.load(r)
    assert guardada["t"] == 0.73
    assert guardada["total_vertices"] == 10_000

    # Act: volver a la dona y cargar la figura guardada
    mover_slider(page, "0")
    expect(page.locator("#figura-nombre")).to_have_text("Dona")
    page.get_by_label("Figuras guardadas").select_option(nombre_figura)
    page.get_by_role("button", name="Cargar").click()

    # Assert: vuelve la figura y el slider se mueve a su t
    expect(page.locator("#figura-nombre")).to_have_text(nombre_figura)
    expect(page.locator("#morph-t")).to_have_text("0.73")
    expect(page.locator("#morph-slider")).to_have_value("0.73")


def test_nombre_repetido_se_rechaza(page: Page, visor_url: str, nombre_figura: str):
    abrir_visor(page, visor_url)
    nombre = page.get_by_label("Nombre de la figura")
    guardar = page.get_by_role("button", name="Guardar")

    nombre.fill(nombre_figura)
    guardar.click()
    # Esperar la confirmación: al llegar, el visor limpia el campo de nombre
    expect(page.locator("#morph-msg")).to_have_text(f'Figura "{nombre_figura}" guardada')
    expect(nombre).to_have_value("")

    nombre.fill(nombre_figura.upper())
    guardar.click()
    expect(page.locator("#morph-msg")).to_contain_text("ya existe")
