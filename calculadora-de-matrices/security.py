# security.py
"""Cabeceras de seguridad, control de caché y cookie de sesión.

Atiende los hallazgos de ZAP/Burp: CSP, anti-clickjacking, nosniff, HSTS,
Cache-Control, y la sesión fuera de localStorage y de la URL.
"""
import hashlib
import hmac
import os
import re
import uuid

from fastapi import FastAPI, Request

COOKIE_SESION = "sid"
_SID_VALIDO = re.compile(r"^[0-9a-f-]{36}$")

# Token compartido con los servicios de confianza (modelado-3d) que pueden
# nombrar su propia sesión con el header X-Session-Id. Sin token, el header
# se ignora.
TOKEN_SERVICIO = os.getenv("SERVICIO_TOKEN", "")


def id_publico(sid: str) -> str:
    """Id de sesión que se guarda en los logs y se muestra en el front.

    Es un hash de la cookie: identifica la sesión pero no permite
    reconstruir la cookie, que nunca sale del servidor.
    """
    return hashlib.sha256(sid.encode()).hexdigest()[:32]


def es_servicio(request: Request) -> bool:
    token = request.headers.get("X-Servicio-Token", "")
    return bool(TOKEN_SERVICIO) and hmac.compare_digest(token, TOKEN_SERVICIO)

CSP = "; ".join([
    "default-src 'self'",
    "script-src 'self'",
    "style-src 'self'",
    "img-src 'self' data:",
    "connect-src 'self'",
    "font-src 'self'",
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
])

CABECERAS = {
    "Content-Security-Policy": CSP,
    "X-Frame-Options": "DENY",
    "X-Content-Type-Options": "nosniff",
    # Solo surte efecto cuando la app se sirve por HTTPS.
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cache-Control": "no-store, max-age=0",
    "Pragma": "no-cache",
}


# CSP para /docs y /redoc (Swagger/ReDoc se cargan de cdn.jsdelivr con script
# en línea). Solo se usa si HABILITAR_DOCS=1, es decir, en desarrollo.
RUTAS_DOCS = ("/docs", "/redoc")
CSP_DOCS = "; ".join([
    "default-src 'self'",
    "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net",
    "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com",
    "img-src 'self' data: https://fastapi.tiangolo.com https://cdn.redoc.ly",
    "font-src 'self' https://fonts.gstatic.com",
    "worker-src 'self' blob:",
    "frame-ancestors 'none'",
])


def docs_habilitadas() -> bool:
    """/docs, /redoc y /openapi.json solo se exponen con HABILITAR_DOCS=1."""
    return os.getenv("HABILITAR_DOCS", "0") == "1"


def configurar(app: FastAPI) -> None:
    @app.middleware("http")
    async def seguridad(request: Request, call_next):
        sid = request.cookies.get(COOKIE_SESION, "")
        nueva = not _SID_VALIDO.match(sid)
        if nueva:
            sid = str(uuid.uuid4())
        request.state.session_id = id_publico(sid)

        response = await call_next(request)

        for nombre, valor in CABECERAS.items():
            response.headers[nombre] = valor
        if request.url.path in RUTAS_DOCS and docs_habilitadas():
            response.headers["Content-Security-Policy"] = CSP_DOCS
        if nueva:
            response.set_cookie(
                COOKIE_SESION, sid,
                httponly=True, samesite="strict", path="/",
                secure=request.url.scheme == "https",
            )
        return response
