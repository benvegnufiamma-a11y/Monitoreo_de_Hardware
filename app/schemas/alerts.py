"""Modelos y esquemas de alertas del sistema."""

from enum import Enum
from typing import Literal
from pydantic import BaseModel, Field


class AlertLevel(str, Enum):
    """Niveles de severidad y criticidad para eventos de salud del sistema."""

    NORMAL = "normal"      # Estado saludable dentro de parámetros óptimos
    WARNING = "warning"    # Estado de advertencia; recurso bajo carga elevada
    CRITICAL = "critical"  # Estado crítico; riesgo inminente de degradación o agotamiento


class AlertThresholds(BaseModel):
    """Umbrales porcentuales configurables para la activación de alertas tempranas.
    
    Permite parametrizar los límites en que el sistema pasa a estado WARNING o CRITICAL.
    """

    # Umbrales para CPU
    cpu_warning: float = Field(default=75.0, ge=0.0, le=100.0, description="Umbral de advertencia para CPU (%)")
    cpu_critical: float = Field(default=90.0, ge=0.0, le=100.0, description="Umbral crítico para CPU (%)")

    # Umbrales para Memoria RAM
    ram_warning: float = Field(default=80.0, ge=0.0, le=100.0, description="Umbral de advertencia para RAM (%)")
    ram_critical: float = Field(default=92.0, ge=0.0, le=100.0, description="Umbral crítico para RAM (%)")

    # Umbrales para Almacenamiento en Disco
    disk_warning: float = Field(default=85.0, ge=0.0, le=100.0, description="Umbral de advertencia para Disco (%)")
    disk_critical: float = Field(default=95.0, ge=0.0, le=100.0, description="Umbral crítico para Disco (%)")


class AlertEvent(BaseModel):
    """Representación formal de un evento de alerta disparado en tiempo real.
    
    Se serializa y envía junto a la instantánea por WebSocket para ser representada en la interfaz.
    """

    id: str = Field(..., description="Identificador único UUID v4 de la alerta generada")
    timestamp: str = Field(..., description="Marca de tiempo en que ocurrió la detección (ISO 8601 UTC)")
    metric: Literal["cpu", "ram", "disk", "network"] = Field(..., description="Subsistema de hardware afectado")
    level: AlertLevel = Field(..., description="Nivel de severidad asignado")
    message: str = Field(..., description="Descripción legible y comprensible para el usuario en español")
    current_value: float = Field(..., description="Valor numérico detectado al momento del disparo")
    threshold_value: float = Field(..., description="Valor del umbral que causó la activación")
