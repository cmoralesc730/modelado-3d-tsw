"""Cabeceras de seguridad y control de caché.

Atiende los hallazgos de ZAP/Burp: CSP, anti-clickjacking, nosniff, HSTS,
Cache-Control, y la validación de Origin del WebSocket.
"""
import os

from fastapi import FastAPI, Request

CSP = "; ".join([
    "default-src 'self'",
    "script-src 'self'",
    "style-src 'self'",
    "img-src 'self' data:",
    # 'self' también cubre ws:// y wss:// al mismo host en navegadores actuales
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
}

# Librerías de terceros con la versión en el nombre: su contenido nunca cambia.
PREFIJO_INMUTABLE = "/static/vendor/"

ORIGENES_PERMITIDOS = {
    o.strip()
    for o in os.getenv("ORIGENES_PERMITIDOS", "http://localhost:8001,http://127.0.0.1:8001").split(",")
    if o.strip()
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


def origen_permitido(origen: str | None) -> bool:
    return origen in ORIGENES_PERMITIDOS


def configurar(app: FastAPI) -> None:
    @app.middleware("http")
    async def seguridad(request: Request, call_next):
        response = await call_next(request)
        for nombre, valor in CABECERAS.items():
            response.headers[nombre] = valor
        if request.url.path in RUTAS_DOCS and docs_habilitadas():
            response.headers["Content-Security-Policy"] = CSP_DOCS
        if request.url.path.startswith(PREFIJO_INMUTABLE):
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        else:
            response.headers["Cache-Control"] = "no-store, max-age=0"
            response.headers["Pragma"] = "no-cache"
        return response
