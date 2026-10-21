# services.py
def sumar(m1: list[list[float]], m2: list[list[float]]) -> list[list[float]]:
    if len(m1) != len(m2) or len(m1[0]) != len(m2[0]):
        raise ValueError("las matrices deben tener la misma dimensión")
    return [[a + b for a, b in zip(fila1, fila2)] for fila1, fila2 in zip(m1, m2)]

def multiplicar(m1: list[list[float]], m2: list[list[float]]) -> list[list[float]]:
    if len(m1[0]) != len(m2):
        raise ValueError("el número de columnas de la primera matriz debe ser igual al número de filas de la segunda")
    return [[sum(a * b for a, b in zip(fila1, col2)) for col2 in zip(*m2)] for fila1 in m1]

def multiplicar_cadena(*matrices: list[list[float]]) -> list[list[float]]:
    """Multiplica de izquierda a derecha: M1 @ M2 @ ... @ Mn."""
    if len(matrices) < 2:
        raise ValueError("se necesitan al menos dos matrices")
    resultado = matrices[0]
    for m in matrices[1:]:
        resultado = multiplicar(resultado, m)
    return resultado

def transponer(m: list[list[float]]) -> list[list[float]]:
    return [list(fila) for fila in zip(*m)]

def determinante(m: list[list[float]]) -> float:
    if len(m) != len(m[0]):
        raise ValueError("la matriz debe ser cuadrada")
    if len(m) == 1:
        return m[0][0]
    if len(m) == 2:
        return m[0][0] * m[1][1] - m[0][1] * m[1][0]
    det = 0
    for c in range(len(m)):
        det += ((-1) ** c) * m[0][c] * determinante([fila[:c] + fila[c + 1:] for fila in m[1:]])
    return det