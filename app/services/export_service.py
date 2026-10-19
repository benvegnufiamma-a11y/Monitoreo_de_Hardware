"""Servicio para serialización y exportación de sesiones de monitoreo a JSON y CSV."""

import csv
import io
import json
from app.schemas.metrics import MetricSnapshot


class ExportService:
    """Convierte listas de instantáneas de métricas en formatos estructurados estándar (JSON y CSV).
    
    Permite a los usuarios descargar y analizar sesiones históricas de telemetría de hardware
    en herramientas como Microsoft Excel, Google Sheets, Pandas o Jupyter Notebooks.
    """

    @staticmethod
    def to_json(snapshots: list[MetricSnapshot]) -> str:
        """Serializa las instantáneas a una cadena JSON estructurada con sangría estética.
        
        Preserva la anidación completa de objetos, incluyendo listas de hilos individuales.
        """
        data = [s.model_dump() for s in snapshots]
        return json.dumps(data, indent=2, ensure_ascii=False)

    @staticmethod
    def to_csv(snapshots: list[MetricSnapshot]) -> str:
        """Aplana la jerarquía de instantáneas en formato tabular bidimensional CSV.
        
        Mapea campos anidados (CPU, RAM, Disco, Red) a columnas homogéneas con saltos de línea LF.
        """
        output = io.StringIO()
        fieldnames = [
            "timestamp",
            "cpu_total_percent",
            "cpu_frequency_mhz",
            "ram_used_gb",
            "ram_free_gb",
            "ram_percent",
            "swap_used_gb",
            "swap_percent",
            "disk_usage_percent",
            "disk_used_gb",
            "disk_free_gb",
            "disk_read_mb_s",
            "disk_write_mb_s",
            "net_sent_kb_s",
            "net_recv_kb_s",
        ]

        writer = csv.DictWriter(output, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()

        for s in snapshots:
            row = {
                "timestamp": s.timestamp,
                "cpu_total_percent": s.cpu.total_percent if s.cpu else "",
                "cpu_frequency_mhz": s.cpu.frequency_mhz if s.cpu and s.cpu.frequency_mhz else "",
                "ram_used_gb": s.ram.used_gb if s.ram else "",
                "ram_free_gb": s.ram.free_gb if s.ram else "",
                "ram_percent": s.ram.percent if s.ram else "",
                "swap_used_gb": s.ram.swap_used_gb if s.ram else "",
                "swap_percent": s.ram.swap_percent if s.ram else "",
                "disk_usage_percent": s.disk.usage_percent if s.disk else "",
                "disk_used_gb": s.disk.used_gb if s.disk else "",
                "disk_free_gb": s.disk.free_gb if s.disk else "",
                "disk_read_mb_s": s.disk.read_mb_s if s.disk else "",
                "disk_write_mb_s": s.disk.write_mb_s if s.disk else "",
                "net_sent_kb_s": s.network.sent_kb_s if s.network else "",
                "net_recv_kb_s": s.network.recv_kb_s if s.network else "",
            }
            writer.writerow(row)

        return output.getvalue()
