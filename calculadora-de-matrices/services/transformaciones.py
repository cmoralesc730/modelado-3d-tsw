# transformaciones.py
"""Matrices homogéneas 4x4 para transformaciones 3D (traslación y rotaciones)."""
import math

from services.services import multiplicar_cadena, transponer


def rotacion_x(grados: float) -> list[list[float]]:
    a = math.radians(grados)
    return [
        [1, 0, 0, 0],
        [0, math.cos(a), -math.sin(a), 0],
        [0, math.sin(a), math.cos(a), 0],
        [0, 0, 0, 1],
    ]


def rotacion_y(grados: float) -> list[list[float]]:
    a = math.radians(grados)
    return [
        [math.cos(a), 0, math.sin(a), 0],
        [0, 1, 0, 0],
        [-math.sin(a), 0, math.cos(a), 0],
        [0, 0, 0, 1],
    ]


def rotacion_z(grados: float) -> list[list[float]]:
    a = math.radians(grados)
    return [
        [math.cos(a), -math.sin(a), 0, 0],
        [math.sin(a), math.cos(a), 0, 0],
        [0, 0, 1, 0],
        [0, 0, 0, 1],
    ]


def traslacion(tx: float, ty: float, tz: float) -> list[list[float]]:
    return [
        [1, 0, 0, tx],
        [0, 1, 0, ty],
        [0, 0, 1, tz],
        [0, 0, 0, 1],
    ]


def matriz_transformacion(tx: float, ty: float, tz: float, rx: float, ry: float, rz: float) -> list[list[float]]:
    """Transformación compuesta M = T @ Rz @ Ry @ Rx (ángulos en grados)."""
    return multiplicar_cadena(traslacion(tx, ty, tz), rotacion_z(rz), rotacion_y(ry), rotacion_x(rx))


def column_major(m: list[list[float]]) -> list[float]:
    """Aplana la matriz por columnas (orden que usan OpenGL/Three.js)."""
    return [valor for fila in transponer(m) for valor in fila]
