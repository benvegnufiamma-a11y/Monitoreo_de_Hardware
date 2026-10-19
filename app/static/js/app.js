/**
 * Orquestador principal de la aplicación frontend del monitor de hardware.
 * Streaming continuo 100% en tiempo real por defecto (estilo Administrador de Tareas)
 * con capacidad de grabación y exportación de sesiones bajo demanda.
 */
import { MonitorSocket } from './socket.js';
import { ChartsManager } from './charts.js';
import { AlertsManager } from './alerts.js';

class HardwareApp {
  constructor() {
    // Instancia del administrador de gráficos con retención de 60 segundos
    this.chartsManager = new ChartsManager(60);
    // Instancia del administrador de alertas con anti-duplicación y cooldown
    this.alertsManager = new AlertsManager('alertsContainer');
    // Búfer en memoria para acumular muestras de la sesión de grabación
    this.sessionSnapshots = [];
    this.isRecording = false;
    this.recordingStartTime = null;
    this.threadsPopulated = false;

    // Referencias a los elementos de control en el DOM
    this.btnRecord = document.getElementById('btnRecord');
    this.recordIcon = document.getElementById('recordIcon');
    this.recordBtnText = document.getElementById('recordBtnText');
    this.btnExportCsv = document.getElementById('btnExportCsv');
    this.btnExportJson = document.getElementById('btnExportJson');
    this.connectionPill = document.getElementById('connectionPill');
    this.connectionText = document.getElementById('connectionText');
    this.sessionStatsText = document.getElementById('sessionStatsText');
    this.cpuCoreSelector = document.getElementById('cpuCoreSelector');
    this.coresGrid = document.getElementById('coresGrid');
    this.coresBalanceSummary = document.getElementById('coresBalanceSummary');

    // Referencias a las tarjetas de especificaciones estáticas
    this.specProcessor = document.getElementById('specProcessor');
    this.specCoresThreads = document.getElementById('specCoresThreads');
    this.specRamTotal = document.getElementById('specRamTotal');
    this.specRamSpeed = document.getElementById('specRamSpeed');
    this.specOsName = document.getElementById('specOsName');
    this.specOsVersion = document.getElementById('specOsVersion');

    // Inicialización del cliente WebSocket con enlace a sus callbacks de respuesta
    this.socket = new MonitorSocket({
      onSnapshot: (snapshot, alerts) => this.handleSnapshot(snapshot, alerts),
      onBaseline: (data, alerts) => this.handleSnapshot(data, alerts),
      onStatus: (status, metrics) => this.handleStatus(status, metrics),
      onError: (msg) => this.handleError(msg),
      onConnectionChange: (connected) => this.handleConnectionChange(connected),
    });
  }

  /**
   * Inicializa los componentes, eventos, especificaciones estáticas y establece la conexión en vivo.
   */
  async init() {
    this.chartsManager.initCharts();
    this.bindEvents();
    await this.fetchSystemInfo();
    this.socket.connect();
  }

  /**
   * Consulta al backend las especificaciones estáticas del host (CPU comercial, RAM DDR/MTs, versión de Windows).
   */
  async fetchSystemInfo() {
    try {
      const res = await fetch('/api/system-info');
      if (res.ok) {
        const info = await res.json();

        // 1. Especificaciones del Procesador
        if (this.specProcessor) this.specProcessor.textContent = info.processor;
        if (this.specCoresThreads) {
          this.specCoresThreads.textContent = `${info.cpu_cores_physical} núcleos físicos • ${info.cpu_cores_logical} hilos lógicos`;
        }

        // 2. Especificaciones de Memoria RAM (tecnología DDR y velocidad en MT/s)
        const ddr = info.ram_type || 'DDR5';
        const speed = info.ram_speed_mts ? `${info.ram_speed_mts} MT/s` : '5200 MT/s';
        if (this.specRamTotal) this.specRamTotal.textContent = `${info.total_ram_gb} GB ${ddr}`;
        if (this.specRamSpeed) this.specRamSpeed.textContent = `${speed} • Memoria física instalada`;

        // 3. Especificaciones del Sistema Operativo comercial
        if (this.specOsName) this.specOsName.textContent = info.os_name;
        if (this.specOsVersion) this.specOsVersion.textContent = info.os_version;

        // Generar dinámicamente las opciones del selector de hilos de CPU
        this.populateThreadSelector(info.cpu_cores_logical);
      }
    } catch (e) {
      console.warn('No se pudo cargar información del sistema:', e);
    }
  }

  /**
   * Añade las opciones de cada hilo ("Hilo 0", "Hilo 1", etc.) al menú desplegable.
   */
  populateThreadSelector(threadCount) {
    if (this.threadsPopulated || !threadCount || !this.cpuCoreSelector) return;

    for (let i = 0; i < threadCount; i++) {
      const option = document.createElement('option');
      option.value = i.toString();
      option.textContent = `Hilo ${i}`;
      this.cpuCoreSelector.appendChild(option);
    }
    this.threadsPopulated = true;
  }

  /**
   * Vincula los listeners de eventos para controles, botones y selectores.
   */
  bindEvents() {
    // Botón de alternar grabación
    this.btnRecord.addEventListener('click', (e) => {
      e.preventDefault();
      this.toggleRecording();
    });

    // Botones de exportación de sesión
    this.btnExportCsv.addEventListener('click', (e) => {
      e.preventDefault();
      this.exportSession('csv');
    });

    this.btnExportJson.addEventListener('click', (e) => {
      e.preventDefault();
      this.exportSession('json');
    });

    // Checkboxes para ocultar/mostrar paneles de métricas individuales
    ['checkCpu', 'checkRam', 'checkDisk', 'checkNetwork'].forEach((id) => {
      document.getElementById(id)?.addEventListener('change', () => {
        this.updateVisibilityPanels();
      });
    });

    // Selector de modo de hilo de CPU ('total', 'all', o hilo individual)
    if (this.cpuCoreSelector) {
      this.cpuCoreSelector.addEventListener('change', (e) => {
        this.chartsManager.setCpuViewMode(e.target.value);
        this.highlightActiveThreadElement(e.target.value);
      });
    }
  }

  /**
   * Activa o detiene la grabación de telemetría sin interrumpir el flujo del streaming en tiempo real.
   */
  toggleRecording() {
    if (!this.isRecording) {
      // Iniciar sesión de grabación
      this.isRecording = true;
      this.sessionSnapshots = [];
      this.recordingStartTime = Date.now();

      this.btnRecord.className = 'btn btn-recording';
      this.recordIcon.textContent = '⏹';
      this.recordBtnText.textContent = 'Detener Grabación';

      // Desactivar descargas mientras se graba una sesión activa
      this.btnExportCsv.disabled = true;
      this.btnExportJson.disabled = true;

      this.connectionPill.className = 'connection-status recording';
      this.connectionText.textContent = 'Grabando sesión de rendimiento';
      this.sessionStatsText.textContent = 'Grabando sesión en memoria... (0 muestras)';
    } else {
      // Detener sesión de grabación
      this.isRecording = false;

      this.btnRecord.className = 'btn btn-record';
      this.recordIcon.textContent = '⏺';
      this.recordBtnText.textContent = 'Iniciar Grabación';

      this.connectionPill.className = 'connection-status connected';
      this.connectionText.textContent = 'Monitoreo en vivo activo';

      // Habilitar exportaciones si se recolectaron muestras
      if (this.sessionSnapshots.length > 0) {
        this.btnExportCsv.disabled = false;
        this.btnExportJson.disabled = false;
        this.sessionStatsText.textContent = `Sesión grabada con éxito: ${this.sessionSnapshots.length} muestras listas para descargar.`;
      } else {
        this.sessionStatsText.textContent = 'Monitoreo 100% en vivo activo • Grabación en espera.';
      }
    }
  }

  /**
   * Recibe la instantánea emitida por WebSocket cada segundo y coordina la actualización de la interfaz.
   * @param {Object} snapshot - Datos instantáneos de CPU, RAM, Disco y Red
   * @param {Array} alerts - Alertas activas detectadas en este ciclo
   */
  handleSnapshot(snapshot, alerts) {
    // Si la grabación de sesión está activa, acumular muestra en el búfer
    if (this.isRecording) {
      this.sessionSnapshots.push(snapshot);
      const elapsed = Math.round((Date.now() - this.recordingStartTime) / 1000);
      this.sessionStatsText.textContent = `⏺ Grabando sesión... (${this.sessionSnapshots.length} muestras / ${elapsed} s)`;
    }

    // 1. Actualización 100% en tiempo real de números y subtítulos de las 4 tarjetas
    this.updateCardDisplays(snapshot);

    // 2. Actualización de las barras individuales de los hilos de CPU
    if (snapshot.cpu && snapshot.cpu.cores) {
      this.renderThreadsGrid(snapshot.cpu.cores);
    }

    // 3. Desplazamiento continuo de los gráficos de 60 segundos
    this.chartsManager.update(snapshot);

    // 4. Detección y renderizado de alertas en vivo
    this.alertsManager.handleAlerts(alerts);
  }

  handleStatus(status, metrics) {
    console.log('Estado de socket:', status, metrics);
  }

  /**
   * Renderiza la rejilla de hilos de CPU con sus barras de carga proporcionales y detección de saturación.
   * Si un hilo supera el 85%, alerta al usuario sobre posible desbalance o cuello de botella de un solo hilo.
   * @param {Array<number>} threads - Porcentajes de utilización de cada hilo lógico
   */
  renderThreadsGrid(threads) {
    if (!this.coresGrid) return;

    if (!this.threadsPopulated) {
      this.populateThreadSelector(threads.length);
    }

    // Encuentra el hilo con mayor carga para diagnóstico de balance térmico y computacional
    let maxVal = -1;
    let maxIdx = 0;
    threads.forEach((val, idx) => {
      if (val > maxVal) {
        maxVal = val;
        maxIdx = idx;
      }
    });

    // Actualiza la etiqueta de balance de carga
    if (this.coresBalanceSummary) {
      if (maxVal >= 85.0) {
        this.coresBalanceSummary.textContent = `Alerta: Hilo ${maxIdx} saturado al ${maxVal.toFixed(1)}%`;
        this.coresBalanceSummary.style.color = 'var(--borravino-accent)';
      } else {
        this.coresBalanceSummary.textContent = `${threads.length} hilos • Máx: H${maxIdx} (${maxVal.toFixed(1)}%)`;
        this.coresBalanceSummary.style.color = 'var(--text-secondary)';
      }
    }

    // Reutiliza los elementos del DOM existentes para evitar recrear nodos y no causar basura de memoria
    if (this.coresGrid.children.length === threads.length) {
      threads.forEach((val, idx) => {
        const item = this.coresGrid.children[idx];
        const valSpan = item.querySelector('.core-val-text');
        const barFill = item.querySelector('.core-bar-fill');

        if (valSpan) valSpan.textContent = `${val.toFixed(0)}%`;
        if (barFill) {
          barFill.style.width = `${Math.min(100, val)}%`;
          barFill.className = 'core-bar-fill';
          if (val >= 90) barFill.classList.add('critical');
          else if (val >= 75) barFill.classList.add('warning');
        }
      });
      return;
    }

    // Primera generación de la estructura visual de los hilos
    this.coresGrid.innerHTML = '';
    threads.forEach((val, idx) => {
      const card = document.createElement('div');
      card.className = 'core-item';
      card.id = `thread-badge-${idx}`;
      card.title = `Clic para aislar el Hilo ${idx}`;

      const row = document.createElement('div');
      row.className = 'core-label-row';

      const label = document.createElement('span');
      label.textContent = `H${idx}`;

      const valSpan = document.createElement('span');
      valSpan.className = 'core-val-text';
      valSpan.textContent = `${val.toFixed(0)}%`;

      row.appendChild(label);
      row.appendChild(valSpan);

      const track = document.createElement('div');
      track.className = 'core-bar-track';

      const fill = document.createElement('div');
      fill.className = 'core-bar-fill';
      fill.style.width = `${Math.min(100, val)}%`;
      if (val >= 90) fill.classList.add('critical');
      else if (val >= 75) fill.classList.add('warning');

      track.appendChild(fill);
      card.appendChild(row);
      card.appendChild(track);

      // Al hacer clic sobre cualquier hilo, se aísla automáticamente en el gráfico
      card.addEventListener('click', () => {
        if (this.cpuCoreSelector) {
          this.cpuCoreSelector.value = idx.toString();
          this.chartsManager.setCpuViewMode(idx.toString());
          this.highlightActiveThreadElement(idx.toString());
        }
      });

      this.coresGrid.appendChild(card);
    });
  }

  /**
   * Resalta visualmente el hilo activo con un borde de selección en la rejilla inferior.
   */
  highlightActiveThreadElement(mode) {
    if (!this.coresGrid) return;
    Array.from(this.coresGrid.children).forEach((child, i) => {
      if (mode === i.toString()) {
        child.classList.add('active-core');
      } else {
        child.classList.remove('active-core');
      }
    });
  }

  /**
   * Actualiza los valores numéricos y descripciones en las 4 tarjetas de hardware.
   * Utiliza textContent estrictamente para evitar vulnerabilidades de inyección XSS.
   */
  updateCardDisplays(snapshot) {
    if (snapshot.cpu) {
      document.getElementById('cpuValue').textContent = snapshot.cpu.total_percent.toFixed(1);
      const sub = snapshot.cpu.frequency_mhz ? `${snapshot.cpu.frequency_mhz} MHz` : `${snapshot.cpu.logical_cores} hilos`;
      document.getElementById('cpuSubtext').textContent = sub;
    }

    if (snapshot.ram) {
      document.getElementById('ramValue').textContent = snapshot.ram.percent.toFixed(1);
      document.getElementById('ramSubtext').textContent = `${snapshot.ram.used_gb.toFixed(1)} / ${snapshot.ram.total_gb.toFixed(1)} GB`;
    }

    if (snapshot.disk) {
      document.getElementById('diskValue').textContent = snapshot.disk.usage_percent.toFixed(1);
      document.getElementById('diskSubtext').textContent = `L: ${snapshot.disk.read_mb_s.toFixed(1)} MB/s • E: ${snapshot.disk.write_mb_s.toFixed(1)} MB/s`;
    }

    if (snapshot.network) {
      document.getElementById('networkValue').textContent = snapshot.network.recv_kb_s.toFixed(0);
      document.getElementById('networkSubtext').textContent = `↓ ${snapshot.network.recv_kb_s.toFixed(0)} KB/s • ↑ ${snapshot.network.sent_kb_s.toFixed(0)} KB/s`;
    }
  }

  /**
   * Alterna la visibilidad de los paneles de gráficos según las casillas de verificación seleccionadas.
   */
  updateVisibilityPanels() {
    const panels = {
      cpu: document.getElementById('checkCpu')?.checked,
      ram: document.getElementById('checkRam')?.checked,
      disk: document.getElementById('checkDisk')?.checked,
      network: document.getElementById('checkNetwork')?.checked,
    };

    Object.entries(panels).forEach(([metric, isVisible]) => {
      const panel = document.getElementById(`panel-${metric}`);
      if (panel) {
        panel.style.display = isVisible ? 'flex' : 'none';
      }
    });
  }

  /**
   * Actualiza el indicador visual de conexión y habilita o deshabilita controles según el estado del socket.
   */
  handleConnectionChange(connected) {
    if (connected) {
      this.connectionPill.className = 'connection-status connected';
      this.connectionText.textContent = 'Monitoreo en vivo activo';
      this.btnRecord.disabled = false;
    } else {
      this.connectionPill.className = 'connection-status';
      this.connectionText.textContent = 'Desconectado (reconectando...)';
      this.btnRecord.disabled = true;
    }
  }

  handleError(msg) {
    console.error('Error de monitor:', msg);
  }

  /**
   * Envía las muestras registradas al endpoint POST /api/export y descarga el archivo resultante (CSV o JSON).
   * @param {string} format - 'csv' o 'json'
   */
  async exportSession(format) {
    if (this.sessionSnapshots.length === 0) {
      alert('No hay muestras grabadas en esta sesión.');
      return;
    }

    try {
      const response = await fetch('/api/export', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          format: format,
          snapshots: this.sessionSnapshots,
        }),
      });

      if (!response.ok) {
        throw new Error('Fallo en la descarga de datos desde la API');
      }

      // Crea un enlace temporal en memoria para descargar el blob recibido
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `sesion_hardware_${new Date().toISOString().slice(0, 19).replace(/[-:T]/g, '')}.${format}`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      a.remove();
    } catch (e) {
      alert('Error exportando datos: ' + e.message);
    }
  }
}

// Punto de entrada en el ciclo de carga del navegador
document.addEventListener('DOMContentLoaded', () => {
  const app = new HardwareApp();
  app.init();
});
