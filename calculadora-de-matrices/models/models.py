# models.py
from pydantic import BaseModel, field_validator


class MatrixCreate(BaseModel):
    nombre: str
    datos: list[list[float]]

    @field_validator("datos")
    @classmethod
    def filas_parejas(cls, v):
        largos = {len(fila) for fila in v}
        if len(largos) != 1:
            raise ValueError("todas las filas deben tener el mismo largo")
        return v

class MatrixOut(MatrixCreate):
    id: int

class CadenaMatrices(BaseModel):
    """Matrices enviadas directamente (sin guardarlas) para multiplicarlas en orden."""
    matrices: list[list[list[float]]]

    @field_validator("matrices")
    @classmethod
    def validar(cls, v):
        if len(v) < 2:
            raise ValueError("se necesitan al menos dos matrices")
        for m in v:
            if not m or len({len(fila) for fila in m}) != 1:
                raise ValueError("todas las filas deben tener el mismo largo")
        return v

class Transformacion(BaseModel):
    """Traslación y rotaciones (en grados) para armar una matriz homogénea 4x4."""
    tx: float = 0.0
    ty: float = 0.0
    tz: float = 0.0
    rx: float = 0.0
    ry: float = 0.0
    rz: float = 0.0

class OperacionLog(BaseModel):
    tipo: str
    metodo: str
    endpoint: str
    parametros: dict
    entradas: dict

class ResultadoLog(BaseModel):
    exitoso: bool
    datos: float | list[list[float]] | None = None
    error: str | None = None

class LogOut(BaseModel):
    id: str
    session_id: str
    fecha_uso: str
    datetime: str
    operacion: OperacionLog
    resultado: ResultadoLog
    duracion_ms: float