# log_service.py
"""Arma el documento del log de ejecución que se guarda en MongoDB."""
from datetime import UTC, datetime

import security

SESION_ANONIMA = "sin-sesion"


def session_id_de(request) -> str:
    """Id de sesión público de la petición.

    Los servicios de confianza (modelado-3d, con X-Servicio-Token válido) se
    nombran con el header X-Session-Id. Para el navegador es el hash de la
    cookie HttpOnly que pone el middleware de security.py; un navegador no
    puede elegir su sesión con el header.
    """
    if security.es_servicio(request):
        cabecera = (request.headers.get("X-Session-Id") or "").strip()[:64]
        if cabecera:
            return cabecera
    return getattr(request.state, "session_id", "") or SESION_ANONIMA


def construir_log(
    session_id: str,
    tipo: str,
    metodo: str,
    endpoint: str,
    parametros: dict,
    entradas: dict,
    exitoso: bool,
    resultado=None,
    error: str | None = None,
    duracion_ms: float = 0.0,
) -> dict:
    ahora = datetime.now(UTC)
    return {
        "session_id": session_id,
        "fecha_uso": ahora.strftime("%Y-%m-%d"),
        "datetime": ahora,
        "operacion": {
            "tipo": tipo,
            "metodo": metodo,
            "endpoint": endpoint,
            "parametros": parametros,
            "entradas": entradas,
        },
        "resultado": {
            "exitoso": exitoso,
            "datos": resultado,
            "error": error,
        },
        "duracion_ms": round(duracion_ms, 3),
    }
