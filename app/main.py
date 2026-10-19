"""Punto de entrada principal de la aplicación FastAPI.

Configura middlewares de seguridad, rutas de la API, endpoints de WebSockets
y el servicio de archivos estáticos y plantillas del frontend.
"""

from contextlib import asynccontextmanager
import logging
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.api.routes import api_router
from app.api.websockets import ws_router
from app.core.config import get_settings
from app.core.security import SecurityHeadersMiddleware

# Configuración de logging estructurado
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("hardware_monitor")

# Instancia de configuración global y resolución del directorio base del proyecto
settings = get_settings()
BASE_DIR = Path(__file__).resolve().parent


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Gestiona el ciclo de vida de arranque y apagado de la aplicación FastAPI.
    
    Permite inicializar recursos antes de recibir solicitudes y liberarlos limpiamente al detenerse.
    """
    logger.info("Iniciando %s en http://%s:%d", settings.APP_NAME, settings.HOST, settings.PORT)
    yield
    logger.info("Deteniendo %s...", settings.APP_NAME)


# Definición de la aplicación principal
app = FastAPI(
    title=settings.APP_NAME,
    description="Monitor de salud de hardware en tiempo real con interfaz web minimalista.",
    version="1.0.0",
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url=None,
    lifespan=lifespan,
)

# 1. Middleware de seguridad: Inyecta cabeceras defensivas (CSP, X-Frame-Options, etc.)
app.add_middleware(SecurityHeadersMiddleware)

# 2. CORS restrictivo: Autoriza únicamente localhost y los hosts configurados en ALLOWED_HOSTS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[f"http://{host}:{settings.PORT}" for host in settings.ALLOWED_HOSTS] + ["http://127.0.0.1:8000", "http://localhost:8000"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# Montaje de archivos estáticos (CSS, JS, iconos) y plantillas Jinja2
static_dir = BASE_DIR / "static"
templates_dir = BASE_DIR / "templates"

app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
templates = Jinja2Templates(directory=str(templates_dir))

# Inclusión de enrutadores modulares de la API REST y WebSockets
app.include_router(api_router)
app.include_router(ws_router)


@app.get("/", response_class=HTMLResponse, summary="Página principal del dashboard")
async def render_dashboard(request: Request) -> HTMLResponse:
    """Renderiza la interfaz web del dashboard principal con Jinja2.
    
    Pasa el título de la aplicación configurado para inyección dinámica en el HTML.
    """
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"app_name": settings.APP_NAME},
    )
