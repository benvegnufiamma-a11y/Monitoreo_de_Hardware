"""Controladores de rutas HTTP de la API REST."""

from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import Response

from app.core.config import get_settings
from app.schemas.metrics import ExportRequest, SystemInfo
from app.services.export_service import ExportService
from app.services.hardware_service import HardwareService

api_router = APIRouter(prefix="/api", tags=["API"])
settings = get_settings()


@api_router.get("/health", summary="Verificación de estado de la API")
async def healthcheck() -> dict[str, str]:
    """Endpoint de comprobación de salud del servicio (Liveness probe).
    
    Permite verificar rápidamente si la API está respondiendo y devuelve la hora UTC del servidor.
    """
    return {
        "status": "healthy",
        "app_name": settings.APP_NAME,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@api_router.get("/system-info", response_model=SystemInfo, summary="Información estática del host")
async def get_system_info() -> SystemInfo:
    """Retorna las características estáticas del sistema operativo, CPU y memoria RAM.
    
    Se consulta una única vez al cargar el dashboard para poblar el panel de especificaciones superiores.
    """
    hardware_service = HardwareService()
    return hardware_service.get_system_info()


@api_router.post("/export", summary="Exportar datos de la sesión de monitoreo")
async def export_session(payload: ExportRequest) -> Response:
    """Genera y descarga un archivo estructurado con la sesión registrada.
    
    Valida que existan muestras capturadas y devuelve una respuesta binaria
    con cabeceras `Content-Disposition: attachment` para disparar la descarga directa en el navegador.
    """
    if not payload.snapshots:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No hay datos registrados en la sesión para exportar",
        )

    timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    if payload.format == "csv":
        content = ExportService.to_csv(payload.snapshots)
        media_type = "text/csv; charset=utf-8"
        filename = f"hardware_metrics_{timestamp_str}.csv"
    elif payload.format == "json":
        content = ExportService.to_json(payload.snapshots)
        media_type = "application/json; charset=utf-8"
        filename = f"hardware_metrics_{timestamp_str}.json"
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Formato de exportación no soportado. Use 'json' o 'csv'",
        )

    return Response(
        content=content,
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-cache",
        },
    )
