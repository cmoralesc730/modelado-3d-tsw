import urllib.error
import urllib.request

import pytest
from playwright.sync_api import Page, expect


def calculadora_responde(url: str) -> bool:
    try:
        urllib.request.urlopen(url, timeout=2)
    except urllib.error.HTTPError:
        return True          # respondió, aunque sea con un error HTTP
    except OSError:
        return False
    return True


def test_visor_sin_calculadora_muestra_error_y_no_se_congela(
    page: Page, visor_url: str, calculadora_url: str
):
    # Precondición: la calculadora (calculadora-de-matrices) debe estar detenida
    if calculadora_responde(calculadora_url):
        pytest.skip("La calculadora está levantada: detenerla con 'docker compose stop' en calculadora-de-matrices")

    # Arrange: abrir el visor
    page.goto(f"{visor_url}/view")
    expect(page.locator("#ws-status")).to_have_text("Conectado", timeout=5000)

    # Assert: el visor informa que la calculadora no responde
    expect(page.get_by_text("calculadora no disponible")).to_be_visible(timeout=5000)

    # Assert: no se congela, el WebSocket sigue abierto y la interfaz responde
    expect(page.locator("#ws-status")).to_have_text("Conectado")
    with page.expect_response(lambda r: "/api/modelo-csv" in r.url and r.ok):
        page.locator("#modelo-select").select_option("cubo")
    expect(page.locator("#point-count")).not_to_have_text("0")
