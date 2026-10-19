"""Esquemas de validación y representación de métricas del hardware."""

from typing import Literal
from pydantic import BaseModel, Field
from app.schemas.alerts import AlertThresholds


class CPUMetrics(BaseModel):
    """Métricas de rendimiento y uso de la CPU.
    
    Incluye porcentaje de uso global, desglose por hilo lógico, conteo de núcleos
    y frecuencia de reloj actual si el sistema operativo la expone.
    """

    total_percent: float = Field(..., ge=0.0, le=100.0, description="Uso total agregado de la CPU en porcentaje")
    cores: list[float] = Field(default_factory=list, description="Porcentaje de uso individual para cada hilo lógico")
    logical_cores: int = Field(..., description="Cantidad total de hilos lógicos de ejecución (SMT/Hyper-Threading)")
    physical_cores: int = Field(..., description="Cantidad de núcleos físicos reales del procesador")
    frequency_mhz: float | None = Field(default=None, description="Frecuencia actual en MHz reportada por el kernel")


class RAMMetrics(BaseModel):
    """Métricas de memoria principal (RAM) y memoria de intercambio (Swap).
    
    Permite monitorear la ocupación física y virtual para prevenir cuellos de botella y desbordamientos.
    """

    total_gb: float = Field(..., ge=0.0, description="Capacidad total instalada de memoria RAM física en Gigabytes")
    used_gb: float = Field(..., ge=0.0, description="Memoria RAM física actualmente en uso por el SO y procesos")
    free_gb: float = Field(..., ge=0.0, description="Memoria RAM disponible de forma inmediata sin paginación")
    percent: float = Field(..., ge=0.0, le=100.0, description="Porcentaje de utilización de memoria RAM")
    swap_total_gb: float = Field(..., ge=0.0, description="Capacidad total del archivo de paginación o swap en GB")
    swap_used_gb: float = Field(..., ge=0.0, description="Memoria swap en uso por procesos inactivos")
    swap_percent: float = Field(..., ge=0.0, le=100.0, description="Porcentaje de ocupación del swap")


class DiskMetrics(BaseModel):
    """Métricas de almacenamiento en disco e indicadores de I/O por segundo.
    
    Calcula tanto el espacio estático como la tasa de transferencia en tiempo real.
    """

    usage_percent: float = Field(..., ge=0.0, le=100.0, description="Porcentaje de espacio ocupado en la partición raíz")
    total_gb: float = Field(..., ge=0.0, description="Capacidad total de la unidad de almacenamiento principal en GB")
    used_gb: float = Field(..., ge=0.0, description="Espacio actualmente ocupado en GB")
    free_gb: float = Field(..., ge=0.0, description="Espacio libre disponible para nuevos archivos en GB")
    read_mb_s: float = Field(default=0.0, ge=0.0, description="Tasa de lectura en tiempo real en Megabytes por segundo")
    write_mb_s: float = Field(default=0.0, ge=0.0, description="Tasa de escritura en tiempo real en Megabytes por segundo")


class NetworkMetrics(BaseModel):
    """Métricas de actividad de interfaces de red y velocidad de transferencia.
    
    Mide la velocidad diferencial entre muestreos para ofrecer KB/s en subida y bajada.
    """

    sent_kb_s: float = Field(default=0.0, ge=0.0, description="Tasa de transmisión o subida en Kilobytes por segundo")
    recv_kb_s: float = Field(default=0.0, ge=0.0, description="Tasa de recepción o bajada en Kilobytes por segundo")


class MetricSnapshot(BaseModel):
    """Instantánea holística de rendimiento del equipo en un instante temporal preciso.
    
    Estructura que se emite a través de WebSockets cada segundo y se almacena en grabaciones.
    """

    timestamp: str = Field(..., description="Marca temporal en formato estándar internacional ISO 8601 UTC")
    cpu: CPUMetrics | None = None
    ram: RAMMetrics | None = None
    disk: DiskMetrics | None = None
    network: NetworkMetrics | None = None


class SystemInfo(BaseModel):
    """Ficha técnica estática con las especificaciones principales del host.
    
    Proporciona información comercial verídica de CPU, Windows y RAM sin abreviaciones genéricas.
    """

    os_name: str = Field(..., description="Nombre comercial del SO (ej. 'Windows 11 Versión 24H2')")
    os_version: str = Field(..., description="Número de compilación específico del SO (ej. 'Compilación 26100.9711')")
    architecture: str | None = Field(default=None, description="Campo opcional reservado para compatibilidad")
    processor: str = Field(..., description="Nombre comercial exacto del procesador (leído desde registro/CIM)")
    cpu_cores_physical: int = Field(..., description="Conteo de núcleos físicos")
    cpu_cores_logical: int = Field(..., description="Conteo de hilos de ejecución")
    total_ram_gb: float = Field(..., description="Cantidad total de memoria RAM redondeada a 2 decimales")
    ram_type: str | None = Field(default=None, description="Generación tecnológica de la memoria (ej. 'DDR5' o 'DDR4')")
    ram_speed_mts: int | None = Field(default=None, description="Frecuencia configurada en MegaTransferencias por segundo (MT/s)")


class WebSocketCommand(BaseModel):
    """Comando de control entrante enviado por el cliente web a través de la conexión WebSocket."""

    action: Literal["start", "stop", "ping", "set_metrics", "set_thresholds"]
    metrics: list[str] = Field(
        default=["cpu", "ram", "disk", "network"],
        description="Lista de sensores o subsistemas autorizados para transmisión"
    )
    thresholds: AlertThresholds | None = None


class ExportRequest(BaseModel):
    """Carga útil recibida en el endpoint POST /api/export para generar archivos descargables."""

    format: Literal["json", "csv"]
    snapshots: list[MetricSnapshot] = Field(..., description="Lista de muestras históricas capturadas durante la sesión")
