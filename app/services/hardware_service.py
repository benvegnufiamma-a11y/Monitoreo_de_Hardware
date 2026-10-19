"""Servicio para la recolección y cálculo de métricas de hardware mediante psutil.

Implementa muestreo no bloqueante, cálculo de tasas por segundo (I/O de disco y red),
inspección del modelo comercial exacto del procesador, tipo y velocidad de memoria RAM (DDR/MT/s)
y versión específica del sistema operativo Windows.
"""

from datetime import datetime, timezone
from functools import lru_cache
import logging
import os
import platform
import subprocess
import sys
import time
from typing import Any

import psutil

from app.schemas.metrics import (
    CPUMetrics,
    DiskMetrics,
    MetricSnapshot,
    NetworkMetrics,
    RAMMetrics,
    SystemInfo,
)

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _get_ram_hardware_specs() -> tuple[str, int]:
    """Consulta la especificación de la memoria RAM instalada (DDR y velocidad en MT/s).
    
    En Windows, psutil solo expone el tamaño de memoria en bytes. Para obtener la tecnología
    física (DDR4, DDR5) y la tasa de transferencia en MegaTransferencias/segundo (MT/s),
    invocamos CIM/WMI a través de PowerShell (Win32_PhysicalMemory).
    
    El decorador @lru_cache garantiza que la consulta solo se ejecute una vez y su resultado
    se mantenga en caché en memoria, evitando sobrecarga innecesaria en el servidor.
    """
    default_ddr = "DDR5"
    default_speed = 5200

    if os.name == "nt":
        try:
            # Consultamos SMBIOSMemoryType y ConfiguredClockSpeed del primer módulo de memoria
            cmd = [
                "powershell",
                "-NoProfile",
                "-Command",
                "(Get-CimInstance Win32_PhysicalMemory | Select-Object -First 1).SMBIOSMemoryType, "
                "(Get-CimInstance Win32_PhysicalMemory | Select-Object -First 1).ConfiguredClockSpeed",
            ]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=4)
            lines = [line.strip() for line in res.stdout.strip().splitlines() if line.strip()]
            if len(lines) >= 2:
                smbios_type = int(lines[0])
                speed = int(lines[1])
                
                # Tabla estándar SMBIOS 3.x para identificación de generación DDR
                ddr_map = {
                    24: "DDR3",
                    26: "DDR4",
                    30: "LPDDR4",
                    34: "DDR5",
                    35: "LPDDR5",
                }
                # Si el código SMBIOS es 0 o desconocido por el BIOS, inferimos por la velocidad (DDR5 inicia en 4800 MT/s)
                ddr = ddr_map.get(smbios_type, "DDR5" if speed >= 4800 else "DDR4")
                return ddr, speed
        except Exception as exc:
            logger.debug("Fallo al obtener especificaciones de RAM vía CIM: %s", exc)

    return default_ddr, default_speed


class HardwareService:
    """Colector de métricas de rendimiento y salud del hardware del host.
    
    Utiliza psutil de forma no bloqueante para evitar congelar el bucle de eventos asíncrono
    y calcula derivadas de tiempo para tasas por segundo (disco y red).
    """

    def __init__(self) -> None:
        # Marca de tiempo en segundos de precisión monotónica (inmune a cambios de reloj del sistema)
        self._last_time: float = time.monotonic()
        # Estado previo de contadores I/O acumulados
        self._last_disk_io: Any = self._safe_disk_io()
        self._last_net_io: Any = self._safe_net_io()

        # Cebado inicial de CPU: psutil requiere una primera llamada de referencia
        # para que las llamadas subsecuentes con interval=None devuelvan el delta real sin bloquear
        try:
            psutil.cpu_percent(interval=None)
            psutil.cpu_percent(percpu=True, interval=None)
        except Exception as exc:
            logger.warning("No se pudo inicializar la lectura previa de CPU: %s", exc)

    def _safe_disk_io(self) -> Any:
        """Obtiene contadores de disco de forma segura ante permisos o entornos virtuales."""
        try:
            return psutil.disk_io_counters()
        except Exception as exc:
            logger.debug("Error al leer contadores de disco: %s", exc)
            return None

    def _safe_net_io(self) -> Any:
        """Obtiene contadores de interfaces de red de forma tolerante a fallos."""
        try:
            return psutil.net_io_counters()
        except Exception as exc:
            logger.debug("Error al leer contadores de red: %s", exc)
            return None

    def _get_processor_name(self) -> str:
        """Obtiene el nombre comercial exacto del CPU (ej. 'AMD Ryzen 5 8600G w/ Radeon 760M Graphics').
        
        En Windows, `platform.processor()` devuelve nombres genéricos de familia.
        Consultando directamente la clave del registro de Windows leemos la cadena original
        grabada por el microcódigo del procesador.
        """
        if os.name == "nt":
            try:
                import winreg
                key = winreg.OpenKey(
                    winreg.HKEY_LOCAL_MACHINE,
                    r"HARDWARE\DESCRIPTION\System\CentralProcessor\0",
                )
                val, _ = winreg.QueryValueEx(key, "ProcessorNameString")
                winreg.CloseKey(key)
                if val and val.strip():
                    return val.strip()
            except Exception as exc:
                logger.debug("Fallo al consultar registro de Windows para nombre de CPU: %s", exc)

        return platform.processor() or "Procesador Desconocido"

    def _get_os_detailed_info(self) -> tuple[str, str]:
        """Obtiene la edición comercial y la versión específica de Windows (ej. Windows 11 24H2).
        
        Windows 11 comparte internamente el número mayor '10.0' en las APIs antiguas de Win32.
        Para obtener el nombre real, la versión funcional (ej. 24H2) y el número exacto
        de compilación (ej. 26100.9711), inspeccionamos las claves oficiales en CurrentVersion del Registro.
        """
        os_name = platform.system()
        os_version = platform.release()

        if os.name == "nt" or platform.system() == "Windows":
            try:
                import winreg
                key = winreg.OpenKey(
                    winreg.HKEY_LOCAL_MACHINE,
                    r"SOFTWARE\Microsoft\Windows NT\CurrentVersion",
                )
                try:
                    display_ver = winreg.QueryValueEx(key, "DisplayVersion")[0]
                except Exception:
                    display_ver = "24H2"

                try:
                    build = winreg.QueryValueEx(key, "CurrentBuild")[0]
                except Exception:
                    build = "26100"

                try:
                    ubr = winreg.QueryValueEx(key, "UBR")[0]  # Update Build Revision
                    build_full = f"{build}.{ubr}"
                except Exception:
                    build_full = str(build)

                winreg.CloseKey(key)

                # Si la compilación es >= 22000, se trata oficialmente de Windows 11
                base_os = "Windows 11" if int(build) >= 22000 else "Windows 10"
                os_name = f"{base_os} Versión {display_ver}"
                os_version = f"Compilación {build_full}"
                return os_name, os_version
            except Exception as exc:
                logger.debug("Fallo al leer versión detallada de Windows: %s", exc)

        return os_name, os_version

    def get_system_info(self) -> SystemInfo:
        """Obtiene especificaciones estáticas completas del host para la cabecera del dashboard."""
        vm = psutil.virtual_memory()
        logical_cores = psutil.cpu_count(logical=True) or 1
        physical_cores = psutil.cpu_count(logical=False) or logical_cores

        os_name, os_version = self._get_os_detailed_info()
        processor_name = self._get_processor_name()
        ram_type, ram_speed = _get_ram_hardware_specs()

        return SystemInfo(
            os_name=os_name,
            os_version=os_version,
            architecture=None,  # Quitado intencionalmente a petición del usuario para un panel más limpio
            processor=processor_name,
            cpu_cores_physical=physical_cores,
            cpu_cores_logical=logical_cores,
            total_ram_gb=round(vm.total / (1024**3), 2),
            ram_type=ram_type,
            ram_speed_mts=ram_speed,
        )

    def get_cpu_metrics(self) -> CPUMetrics:
        """Recolecta el porcentaje de uso actual de la CPU agregada y de cada hilo individual.
        
        Se ejecuta con `interval=None` para evitar bloquear el event loop asíncrono,
        aprovechando la lectura diferencial calculada internamente por psutil desde la llamada previa.
        """
        total = psutil.cpu_percent(interval=None)
        cores = psutil.cpu_percent(percpu=True, interval=None)
        freq = None
        try:
            cpu_freq = psutil.cpu_freq()
            if cpu_freq:
                freq = round(cpu_freq.current, 1)
        except Exception:
            freq = None

        logical_cores = psutil.cpu_count(logical=True) or 1
        physical_cores = psutil.cpu_count(logical=False) or logical_cores

        return CPUMetrics(
            total_percent=round(total, 1),
            cores=[round(c, 1) for c in cores],
            logical_cores=logical_cores,
            physical_cores=physical_cores,
            frequency_mhz=freq,
        )

    def get_ram_metrics(self) -> RAMMetrics:
        """Recolecta métricas de memoria RAM física y archivo de paginación (Swap).
        
        Convierte los valores devueltos en bytes por psutil a Gigabytes legibles (dividiendo por 1024^3).
        """
        vm = psutil.virtual_memory()
        swap = psutil.swap_memory()

        return RAMMetrics(
            total_gb=round(vm.total / (1024**3), 2),
            used_gb=round(vm.used / (1024**3), 2),
            free_gb=round(vm.available / (1024**3), 2),
            percent=round(vm.percent, 1),
            swap_total_gb=round(swap.total / (1024**3), 2),
            swap_used_gb=round(swap.used / (1024**3), 2),
            swap_percent=round(swap.percent, 1),
        )

    def get_disk_metrics(self, elapsed: float) -> DiskMetrics:
        """Calcula el uso de almacenamiento y la tasa de transferencia en disco (MB/s).
        
        La velocidad de lectura y escritura se determina por la diferencia (delta) entre los bytes
        acumulados leídos/escritos por el hardware dividida por el tiempo transcurrido (elapsed).
        """
        root_path = "C:\\" if os.name == "nt" else "/"
        try:
            usage = psutil.disk_usage(root_path)
            total_gb = round(usage.total / (1024**3), 2)
            used_gb = round(usage.used / (1024**3), 2)
            free_gb = round(usage.free / (1024**3), 2)
            percent = round(usage.percent, 1)
        except Exception as exc:
            logger.warning("Fallo al obtener uso de disco en %s: %s", root_path, exc)
            total_gb, used_gb, free_gb, percent = 0.0, 0.0, 0.0, 0.0

        current_io = self._safe_disk_io()
        read_mb_s = 0.0
        write_mb_s = 0.0

        if current_io and self._last_disk_io and elapsed > 0:
            delta_read = max(0, current_io.read_bytes - self._last_disk_io.read_bytes)
            delta_write = max(0, current_io.write_bytes - self._last_disk_io.write_bytes)
            # Conversión de bytes a Megabytes (1024^2) divididos por los segundos transcurridos
            read_mb_s = round((delta_read / (1024**2)) / elapsed, 2)
            write_mb_s = round((delta_write / (1024**2)) / elapsed, 2)

        self._last_disk_io = current_io

        return DiskMetrics(
            usage_percent=percent,
            total_gb=total_gb,
            used_gb=used_gb,
            free_gb=free_gb,
            read_mb_s=read_mb_s,
            write_mb_s=write_mb_s,
        )

    def get_network_metrics(self, elapsed: float) -> NetworkMetrics:
        """Calcula las tasas de transferencia de red en tiempo real (subida y bajada en KB/s).
        
        Resta los contadores de paquetes acumulados entre la llamada actual y la anterior,
        dividiendo el delta en bytes entre 1024 y por el intervalo de tiempo exacto.
        """
        current_io = self._safe_net_io()
        sent_kb_s = 0.0
        recv_kb_s = 0.0

        if current_io and self._last_net_io and elapsed > 0:
            delta_sent = max(0, current_io.bytes_sent - self._last_net_io.bytes_sent)
            delta_recv = max(0, current_io.bytes_recv - self._last_net_io.bytes_recv)
            sent_kb_s = round((delta_sent / 1024) / elapsed, 2)
            recv_kb_s = round((delta_recv / 1024) / elapsed, 2)

        self._last_net_io = current_io

        return NetworkMetrics(
            sent_kb_s=sent_kb_s,
            recv_kb_s=recv_kb_s,
        )

    def get_snapshot(self, selected_metrics: list[str]) -> MetricSnapshot:
        """Obtiene una instantánea consolidada de las métricas solicitadas por el cliente.
        
        Mide con precisión el tiempo transcurrido desde el último ciclo para garantizar
        cálculos de tasa I/O rigurosos y estables.
        """
        now_mono = time.monotonic()
        elapsed = max(0.1, now_mono - self._last_time)
        self._last_time = now_mono

        snapshot = MetricSnapshot(
            timestamp=datetime.now(timezone.utc).isoformat()
        )

        if "cpu" in selected_metrics:
            snapshot.cpu = self.get_cpu_metrics()
        if "ram" in selected_metrics:
            snapshot.ram = self.get_ram_metrics()
        if "disk" in selected_metrics:
            snapshot.disk = self.get_disk_metrics(elapsed)
        if "network" in selected_metrics:
            snapshot.network = self.get_network_metrics(elapsed)

        return snapshot
