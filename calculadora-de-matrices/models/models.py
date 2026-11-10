# models.py
from pydantic import BaseModel, Field, field_validator
from services.morph import RESOLUCION_DEFECTO, RESOLUCION_MAX, RESOLUCION_MIN


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

class Morph(BaseModel):
    """Parámetros del morph dona -> taza."""
    t: float = Field(ge=0.0, le=1.0, allow_inf_nan=False,
                     description="0 = dona, 1 = taza")
    resolucion: int = Field(RESOLUCION_DEFECTO, ge=RESOLUCION_MIN, le=RESOLUCION_MAX, strict=True,
                            description="puntos por lado de la malla (resolucion² vértices); "
                                        "100 = 10,000 puntos como dona.csv")

class FiguraCreate(Morph):
    """Figura del morph que se guarda con nombre para consultarla después."""
    nombre: str = Field(min_length=1, max_length=50, pattern=r"^\w[\w .\-]*$",
                        description="letras, números, espacios, '.', '-' y '_'; empieza con letra o número")

    @field_validator("nombre", mode="before")
    @classmethod
    def limpiar_nombre(cls, v):
        return " ".join(v.split()) if isinstance(v, str) else v

class FiguraResumen(BaseModel):
    nombre: str
    t: float
    resolucion: int
    figura: str
    total_vertices: int
    creado_en: str

class FiguraOut(FiguraResumen):
    vertices: list[list[float]]

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