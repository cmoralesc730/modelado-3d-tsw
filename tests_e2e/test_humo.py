from playwright.sync_api import Page, expect


def test_visor_se_conecta(page: Page, visor_url: str):   # pytest inyecta la página y la URL
    # Arrange: abrir la aplicación
    page.goto(f"{visor_url}/view")
 
    # Assert: esperar el estado (reintenta hasta 5 s)
    expect(page.get_by_text("Conectado", exact=True)).to_be_visible(timeout=5000)