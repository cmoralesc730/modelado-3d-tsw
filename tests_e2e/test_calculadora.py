import re

from playwright.sync_api import Page, expect


def abrir_calculadora(page: Page, calculadora_url: str) -> None:
    page.goto(calculadora_url)
    expect(page.locator("#estado")).to_contain_text("API conectada")


def crear_matriz(page: Page, nombre: str, datos: list[list[float]]) -> int:
    """Crea una matriz desde el editor y devuelve el id que le asignó la API."""
    page.get_by_role("button", name="Nueva", exact=True).click()

    # El editor arranca en 2x2: ajustar filas y columnas con los botones − / +
    for dim, objetivo in (("filas", len(datos)), ("cols", len(datos[0]))):
        paso = 1 if objetivo > 2 else -1
        for _ in range(abs(objetivo - 2)):
            page.locator(f'[data-dim="{dim}"][data-paso="{paso}"]').click()

    page.get_by_role("textbox", name="Nombre").fill(nombre)
    for i, fila in enumerate(datos, start=1):
        for j, valor in enumerate(fila, start=1):
            page.get_by_role("spinbutton", name=f"fila {i}, columna {j}").fill(str(valor))
    page.get_by_role("button", name="Guardar nueva").click()

    # Al guardar, el editor pasa a "editando #<id>" con la matriz recién creada
    modo = page.locator("#modoEditor")
    expect(modo).to_have_text(re.compile(r"editando #\d+"))
    return int(modo.inner_text().split("#")[1])


def test_guardar_matriz(page: Page, calculadora_url: str):
    # Arrange
    abrir_calculadora(page, calculadora_url)

    # Act
    id_a = crear_matriz(page, "A", [[1, 2], [3, 4]])

    # Assert: aparece en la lista de matrices guardadas
    tarjeta = page.locator(f'#lista .card[data-id="{id_a}"]')
    expect(tarjeta).to_contain_text("A")
    expect(tarjeta.locator(".dim")).to_have_text("2×2")


def test_sumar_matrices(page: Page, calculadora_url: str):
    # Arrange
    abrir_calculadora(page, calculadora_url)
    id_a = crear_matriz(page, "A", [[1, 2], [3, 4]])
    id_b = crear_matriz(page, "B", [[4, 3], [2, 1]])

    # Act
    page.get_by_label("Matriz A").select_option(str(id_a))
    page.get_by_label("Matriz B").select_option(str(id_b))
    page.get_by_role("button", name="A + B").click()

    # Assert
    expect(page.locator("#tagResultado")).to_have_text(f"#{id_a} + #{id_b}")
    expect(page.locator("#resultado .celda")).to_have_text(["5", "5", "5", "5"])


def test_sumar_dimensiones_distintas_es_rechazado(page: Page, calculadora_url: str):
    # Arrange
    abrir_calculadora(page, calculadora_url)
    id_a = crear_matriz(page, "A", [[1, 2], [3, 4]])
    id_d = crear_matriz(page, "D", [[4, 3], [2, 1], [1, 2]])

    # Act
    page.get_by_label("Matriz A").select_option(str(id_a))
    page.get_by_label("Matriz B").select_option(str(id_d))
    page.get_by_role("button", name="A + B").click()

    # Assert
    toasts = page.locator("#toasts")
    expect(toasts).to_contain_text("Operación rechazada")
    expect(toasts).to_contain_text("las matrices deben tener la misma dimensión")
    expect(page.locator("#resultado")).to_contain_text("La última operación falló")


def test_determinante(page: Page, calculadora_url: str):
    # Arrange
    abrir_calculadora(page, calculadora_url)
    id_a = crear_matriz(page, "A", [[1, 2], [3, 4]])

    # Act
    page.get_by_label("Matriz A").select_option(str(id_a))
    page.get_by_role("button", name="det(A)").click()

    # Assert: det([[1, 2], [3, 4]]) = 1·4 − 2·3 = −2
    expect(page.locator("#tagResultado")).to_have_text(f"det(#{id_a})")
    expect(page.locator("#resultado .escalar")).to_have_text("-2")
