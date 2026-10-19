"""Controlador WebSocket para streaming continuo 100% en tiempo real."""

import asyncio
import json
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from app.core.config import get_settings
from app.schemas.alerts import AlertThresholds
from app.schemas.metrics import WebSocketCommand
from app.services.alert_service import AlertService
from app.services.hardware_service import HardwareService

logger = logging.getLogger(__name__)
ws_router = APIRouter()
settings = get_settings()


@ws_router.websocket("/ws/monitor")
async def websocket_monitor_endpoint(websocket: WebSocket) -> None:
    """Maneja el streaming continuo e ininterrumpido en tiempo real (estilo Administrador de Tareas).
    
    Acepta la conexión del cliente e inmediatamente inicia una tarea en segundo plano (asyncio task)
    que emite muestras cada 1 segundo. Al mismo tiempo, el bucle principal escucha comandos
    del cliente (start/stop de grabación, actualización de umbrales, ping).
    """
    await websocket.accept()

    hardware_service = HardwareService()
    active_metrics: list[str] = ["cpu", "ram", "disk", "network"]
    thresholds = AlertThresholds()
    is_streaming = True

    async def stream_loop() -> None:
        """Bucle de emisión continua en vivo:
        
        Recolecta la instantánea del hardware, evalúa las alertas con los umbrales vigentes
        y transmite el paquete JSON al cliente a través del socket.
        """
        try:
            while is_streaming:
                snapshot = hardware_service.get_snapshot(active_metrics)
                alerts = AlertService.evaluate(snapshot, thresholds)

                payload = {
                    "type": "snapshot",
                    "data": snapshot.model_dump(),
                    "alerts": [alert.model_dump() for alert in alerts],
                }

                await websocket.send_text(json.dumps(payload))
                await asyncio.sleep(settings.DEFAULT_SAMPLING_INTERVAL_SECONDS)
        except asyncio.CancelledError:
            # Tarea cancelada normalmente cuando el cliente se desconecta
            pass
        except Exception as exc:
            logger.error("Error durante el streaming continuo: %s", exc)

    # Inicia la tarea asíncrona de emisión concurrente
    stream_task = asyncio.create_task(stream_loop())

    try:
        # Bucle de recepción de mensajes y comandos del cliente web
        while True:
            raw_data = await websocket.receive_text()

            # Validación de sintaxis JSON y esquema Pydantic
            try:
                data = json.loads(raw_data)
                command = WebSocketCommand.model_validate(data)
            except (json.JSONDecodeError, ValidationError) as val_err:
                await websocket.send_text(
                    json.dumps({
                        "type": "error",
                        "message": "Comando inválido o malformado",
                        "detail": str(val_err),
                    })
                )
                continue

            # Actualización dinámica de umbrales de alerta sin reiniciar la conexión
            if command.thresholds:
                thresholds = command.thresholds

            # Acciones admitidas
            if command.action in ("start", "set_metrics"):
                if command.metrics:
                    active_metrics = command.metrics
                await websocket.send_text(
                    json.dumps({
                        "type": "status",
                        "status": "capturing",
                        "metrics": active_metrics,
                    })
                )

            elif command.action == "stop":
                await websocket.send_text(
                    json.dumps({
                        "type": "status",
                        "status": "stopped",
                    })
                )

            elif command.action == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))

    except WebSocketDisconnect:
        logger.info("Cliente WebSocket desconectado")
    except Exception as exc:
        logger.warning("Error no esperado en socket: %s", exc)
    finally:
        # Limpieza ordenada de recursos al desconectar
        is_streaming = False
        if stream_task and not stream_task.done():
            stream_task.cancel()
