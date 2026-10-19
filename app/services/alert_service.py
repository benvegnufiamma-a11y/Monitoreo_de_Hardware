"""Servicio para la evaluación de métricas y detección de alertas críticas."""

from datetime import datetime, timezone
import uuid

from app.schemas.alerts import AlertEvent, AlertLevel, AlertThresholds
from app.schemas.metrics import MetricSnapshot


class AlertService:
    """Evalúa métricas del hardware contra umbrales dinámicos de alerta.
    
    Analiza instantáneas periódicas y genera eventos de alerta tipados cuando los valores
    superan los límites de advertencia (WARNING) o críticos (CRITICAL).
    """

    @staticmethod
    def evaluate(snapshot: MetricSnapshot, thresholds: AlertThresholds) -> list[AlertEvent]:
        """Compara la instantánea actual contra los umbrales configurados.
        
        Args:
            snapshot: Instantánea actual con métricas de CPU, RAM, Disco y Red.
            thresholds: Umbrales numéricos de advertencia y crítico configurados.
            
        Returns:
            Lista de eventos de alerta detectados (vacía si el sistema está normal).
        """
        alerts: list[AlertEvent] = []
        now_iso = datetime.now(timezone.utc).isoformat()

        # 1. Evaluación de CPU: Prioridad crítica sobre advertencia
        if snapshot.cpu:
            cpu_val = snapshot.cpu.total_percent
            if cpu_val >= thresholds.cpu_critical:
                alerts.append(
                    AlertEvent(
                        id=str(uuid.uuid4()),
                        timestamp=now_iso,
                        metric="cpu",
                        level=AlertLevel.CRITICAL,
                        message=f"Uso crítico de CPU al {cpu_val:.1f}% (Umbral: {thresholds.cpu_critical}%)",
                        current_value=cpu_val,
                        threshold_value=thresholds.cpu_critical,
                    )
                )
            elif cpu_val >= thresholds.cpu_warning:
                alerts.append(
                    AlertEvent(
                        id=str(uuid.uuid4()),
                        timestamp=now_iso,
                        metric="cpu",
                        level=AlertLevel.WARNING,
                        message=f"Alto uso de CPU al {cpu_val:.1f}% (Umbral: {thresholds.cpu_warning}%)",
                        current_value=cpu_val,
                        threshold_value=thresholds.cpu_warning,
                    )
                )

        # 2. Evaluación de Memoria RAM: Evalúa porcentaje y reporta GB libres
        if snapshot.ram:
            ram_val = snapshot.ram.percent
            if ram_val >= thresholds.ram_critical:
                alerts.append(
                    AlertEvent(
                        id=str(uuid.uuid4()),
                        timestamp=now_iso,
                        metric="ram",
                        level=AlertLevel.CRITICAL,
                        message=f"Uso crítico de memoria RAM al {ram_val:.1f}% (Libre: {snapshot.ram.free_gb:.2f} GB)",
                        current_value=ram_val,
                        threshold_value=thresholds.ram_critical,
                    )
                )
            elif ram_val >= thresholds.ram_warning:
                alerts.append(
                    AlertEvent(
                        id=str(uuid.uuid4()),
                        timestamp=now_iso,
                        metric="ram",
                        level=AlertLevel.WARNING,
                        message=f"Alto uso de memoria RAM al {ram_val:.1f}% (Umbral: {thresholds.ram_warning}%)",
                        current_value=ram_val,
                        threshold_value=thresholds.ram_warning,
                    )
                )

        # 3. Evaluación de Almacenamiento en Disco: Alerta sobre partición principal
        if snapshot.disk:
            disk_val = snapshot.disk.usage_percent
            if disk_val >= thresholds.disk_critical:
                alerts.append(
                    AlertEvent(
                        id=str(uuid.uuid4()),
                        timestamp=now_iso,
                        metric="disk",
                        level=AlertLevel.CRITICAL,
                        message=f"Espacio de almacenamiento crítico al {disk_val:.1f}% (Libre: {snapshot.disk.free_gb:.2f} GB)",
                        current_value=disk_val,
                        threshold_value=thresholds.disk_critical,
                    )
                )
            elif disk_val >= thresholds.disk_warning:
                alerts.append(
                    AlertEvent(
                        id=str(uuid.uuid4()),
                        timestamp=now_iso,
                        metric="disk",
                        level=AlertLevel.WARNING,
                        message=f"Almacenamiento casi lleno al {disk_val:.1f}% (Umbral: {thresholds.disk_warning}%)",
                        current_value=disk_val,
                        threshold_value=thresholds.disk_warning,
                    )
                )

        return alerts
