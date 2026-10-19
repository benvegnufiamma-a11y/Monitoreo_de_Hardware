"""Middleware de seguridad y cabeceras HTTP defensivas.

Protege contra clickjacking (X-Frame-Options), MIME sniffing (X-Content-Type-Options),
y define una Content-Security-Policy restrictiva.
"""

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Agrega cabeceras de seguridad HTTP a todas las respuestas del servidor.
    
    Implementa directivas recomendadas por OWASP para evitar ataques comunes en entornos web.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)

        # 1. Anti-Clickjacking:
        # Deniega terminantemente que la página sea embebida dentro de elementos <iframe> o <frame>
        # de sitios web externos, impidiendo ataques de clickjacking.
        response.headers["X-Frame-Options"] = "DENY"

        # 2. Anti-MIME-Sniffing:
        # Fuerza al navegador a respetar estrictamente los Content-Type declarados por el servidor,
        # impidiendo que interprete archivos de texto o datos como código ejecutable.
        response.headers["X-Content-Type-Options"] = "nosniff"

        # 3. Política de Referrer:
        # Envía la URL completa solo dentro del mismo origen y únicamente el origen seguro en peticiones HTTPS cruzadas.
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # 4. Política de Permisos del Navegador (Permissions-Policy):
        # Desactiva el acceso a APIs de hardware sensibles que la aplicación no requiere (cámara, micrófono, geolocalización).
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"

        # 5. Content Security Policy (CSP):
        # Política restrictiva que limita de dónde se pueden descargar scripts, estilos y fuentes:
        # - default-src 'self': recursos propios locales.
        # - script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net: permite Chart.js desde CDN oficial.
        # - style-src / font-src: permite fuentes de Google Fonts (Cinzel y Plus Jakarta Sans).
        # - connect-src: autoriza conexiones WebSocket seguras e inseguras locales (ws: wss:).
        csp = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "img-src 'self' data:; "
            "connect-src 'self' ws: wss:;"
        )
        response.headers["Content-Security-Policy"] = csp

        return response
