"""Genera los CSV (x,y,z) de los modelos de prueba: esfera y cubo.

Escala similar a la dona (dona.csv), que ocupa de -3 a 3 en X/Y.
Uso: python generar_modelos.py
"""
import csv
import math
from pathlib import Path

# Decimales con que se guardan las coordenadas
DECIMALES = 6


def esfera(radio: float = 2.5, n: int = 10000) -> list[tuple[float, float, float]]:
    """Puntos repartidos uniformemente sobre la superficie (espiral de Fibonacci)."""
    angulo_aureo = math.pi * (3 - math.sqrt(5))
    puntos = []
    for i in range(n):
        y = 1 - 2 * (i + 0.5) / n          # de 1 a -1
        r = math.sqrt(1 - y * y)
        theta = angulo_aureo * i
        puntos.append((radio * r * math.cos(theta), radio * y, radio * r * math.sin(theta)))
    return puntos


def cubo(mitad: float = 1.75, divisiones: int = 40) -> list[tuple[float, float, float]]:
    """Malla de puntos sobre las 6 caras, sin repetir los de aristas y vértices."""
    paso = 2 * mitad / divisiones
    valores = [-mitad + i * paso for i in range(divisiones + 1)]
    puntos = set()
    for eje in range(3):
        for lado in (-mitad, mitad):
            for a in valores:
                for b in valores:
                    p = [a, b]
                    p.insert(eje, lado)
                    puntos.add(tuple(round(c, DECIMALES) for c in p))
    return sorted(puntos)


def guardar(path: Path, puntos) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["x", "y", "z"])
        writer.writerows([round(c, DECIMALES) for c in p] for p in puntos)
    print(f"{path}: {len(puntos)} puntos")


if __name__ == "__main__":
    carpeta = Path(__file__).parent
    guardar(carpeta / "esfera.csv", esfera())
    guardar(carpeta / "cubo.csv", cubo())
