"""Pruebas unitarias y de integración para los servicios y endpoints del backend."""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.alerts import AlertLevel, AlertThresholds
from app.schemas.metrics import CPUMetrics, MetricSnapshot, RAMMetrics
from app.services.alert_service import AlertService
from app.services.export_service import ExportService
from app.services.hardware_service import HardwareService

client = TestClient(app)


def test_healthcheck() -> None:
    """Verifica que el endpoint de salud responda 200 OK con el estado correcto."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "app_name" in data


def test_render_dashboard() -> None:
    """Verifica que la página principal HTML cargue correctamente con status 200."""
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Monitoreo de salud del hardware" in response.text


def test_system_info() -> None:
    """Verifica la obtención de metadatos estáticos del host."""
    response = client.get("/api/system-info")
    assert response.status_code == 200
    data = response.json()
    assert "os_name" in data
    assert "Windows 11" in data["os_name"]
    assert "cpu_cores_logical" in data
    assert data["cpu_cores_logical"] >= 1
    assert data["total_ram_gb"] > 0
    assert data.get("ram_type") in ("DDR4", "DDR5")
    assert data.get("ram_speed_mts") is not None


def test_hardware_service_snapshot() -> None:
    """Verifica que HardwareService genere snapshots consistentes."""
    service = HardwareService()
    snapshot = service.get_snapshot(["cpu", "ram", "disk", "network"])

    assert snapshot.timestamp is not None
    assert snapshot.cpu is not None
    assert 0.0 <= snapshot.cpu.total_percent <= 100.0
    assert snapshot.ram is not None
    assert snapshot.ram.total_gb > 0.0
    assert snapshot.disk is not None
    assert snapshot.network is not None


def test_alert_service_triggers_correctly() -> None:
    """Verifica la lógica de detección de alertas en umbrales de advertencia y crítico."""
    thresholds = AlertThresholds(
        cpu_warning=70.0,
        cpu_critical=90.0,
        ram_warning=80.0,
        ram_critical=95.0,
    )

    # Caso 1: Normal
    normal_snapshot = MetricSnapshot(
        timestamp="2026-10-16T12:00:00Z",
        cpu=CPUMetrics(
            total_percent=45.0,
            cores=[45.0],
            logical_cores=4,
            physical_cores=4,
        ),
        ram=RAMMetrics(
            total_gb=16.0,
            used_gb=8.0,
            free_gb=8.0,
            percent=50.0,
            swap_total_gb=4.0,
            swap_used_gb=0.0,
            swap_percent=0.0,
        ),
    )
    alerts = AlertService.evaluate(normal_snapshot, thresholds)
    assert len(alerts) == 0

    # Caso 2: CPU Crítica
    critical_snapshot = MetricSnapshot(
        timestamp="2026-10-16T12:00:01Z",
        cpu=CPUMetrics(
            total_percent=94.5,
            cores=[94.5],
            logical_cores=4,
            physical_cores=4,
        ),
    )
    alerts = AlertService.evaluate(critical_snapshot, thresholds)
    assert len(alerts) == 1
    assert alerts[0].metric == "cpu"
    assert alerts[0].level == AlertLevel.CRITICAL


def test_export_service() -> None:
    """Verifica la serialización a JSON y CSV de los datos capturados."""
    snapshots = [
        MetricSnapshot(
            timestamp="2026-10-16T12:00:00Z",
            cpu=CPUMetrics(
                total_percent=55.0,
                cores=[55.0],
                logical_cores=4,
                physical_cores=4,
                frequency_mhz=2400.0,
            ),
        )
    ]

    # JSON export
    json_out = ExportService.to_json(snapshots)
    assert "cpu" in json_out
    assert "55.0" in json_out

    # CSV export
    csv_out = ExportService.to_csv(snapshots)
    assert "timestamp" in csv_out
    assert "cpu_total_percent" in csv_out
    assert "55.0" in csv_out


def test_api_export_endpoint() -> None:
    """Verifica la descarga HTTP de exportaciones en JSON y CSV."""
    payload = {
        "format": "csv",
        "snapshots": [
            {
                "timestamp": "2026-10-16T12:00:00Z",
                "cpu": {
                    "total_percent": 30.0,
                    "cores": [30.0],
                    "logical_cores": 2,
                    "physical_cores": 2,
                },
            }
        ],
    }

    response = client.post("/api/export", json=payload)
    assert response.status_code == 200
    assert "text/csv" in response.headers["content-type"]
    assert "attachment; filename=" in response.headers["content-disposition"]


def test_security_headers_present() -> None:
    """Verifica que las cabeceras de seguridad estén activas en las respuestas."""
    response = client.get("/api/health")
    assert response.headers.get("X-Frame-Options") == "DENY"
    assert response.headers.get("X-Content-Type-Options") == "nosniff"
    assert "Content-Security-Policy" in response.headers


def test_websocket_ping_pong() -> None:
    """Verifica que el WebSocket emita snapshot continuo y responda a ping."""
    with client.websocket_connect("/ws/monitor") as websocket:
        # Primer mensaje en tiempo real inmediato
        init_msg = websocket.receive_json()
        assert init_msg["type"] == "snapshot"
        assert "data" in init_msg
        assert "alerts" in init_msg

        # Comando ping
        websocket.send_text('{"action": "ping"}')
        data = websocket.receive_json()
        assert data == {"type": "pong"}


def test_websocket_start_and_stop_lifecycle() -> None:
    """Verifica el control de sesión en tiempo real a través de WebSocket."""
    with client.websocket_connect("/ws/monitor") as websocket:
        # Primer snapshot en vivo inmediato
        init_msg = websocket.receive_json()
        assert init_msg["type"] == "snapshot"

        # 1. Establecer métricas de sesión
        websocket.send_text(
            '{"action": "start", "metrics": ["cpu", "ram"], "thresholds": {"cpu_warning": 80.0, "cpu_critical": 95.0}}'
        )
        status_msg = websocket.receive_json()
        assert status_msg["type"] == "status"
        assert status_msg["status"] == "capturing"
        assert status_msg["metrics"] == ["cpu", "ram"]

        # 2. Recibir siguiente snapshot en vivo
        snapshot_msg = websocket.receive_json()
        assert snapshot_msg["type"] == "snapshot"
        assert "data" in snapshot_msg
        assert "cpu" in snapshot_msg["data"]
        assert "ram" in snapshot_msg["data"]

        # 3. Detener sesión de captura
        websocket.send_text('{"action": "stop"}')
        stop_msg = websocket.receive_json()
        assert stop_msg["type"] == "status"
        assert stop_msg["status"] == "stopped"


def test_websocket_malformed_command_handling() -> None:
    """Verifica que el WebSocket rechace comandos malformados sin desconectarse."""
    with client.websocket_connect("/ws/monitor") as websocket:
        # Descartar baseline inicial
        _ = websocket.receive_json()

        websocket.send_text('{"invalid_field": 123}')
        error_msg = websocket.receive_json()
        assert error_msg["type"] == "error"
        assert "Comando inválido" in error_msg["message"]


def test_export_validation_errors() -> None:
    """Verifica que /api/export rechace listas vacías o formatos no soportados."""
    # Lista vacía
    res_empty = client.post("/api/export", json={"format": "csv", "snapshots": []})
    assert res_empty.status_code == 400

    # Formato inválido
    res_invalid_format = client.post(
        "/api/export",
        json={"format": "xml", "snapshots": [{"timestamp": "2026-10-16T00:00:00Z"}]},
    )
    assert res_invalid_format.status_code == 422  # Validación Pydantic
