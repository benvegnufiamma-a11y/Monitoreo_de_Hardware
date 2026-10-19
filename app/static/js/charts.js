/**
 * Gestor de gráficos temporales en tiempo real con ventana deslizante de 60 segundos
 * y soporte para desglose, aislamiento y selección de hilos de CPU individuales.
 * 
 * Utiliza Chart.js v4 con animaciones desactivadas (`animation: false`) para maximizar la fluidez
 * a 60 FPS y garantizar un uso mínimo de procesador en el navegador.
 */
export class ChartsManager {
  /**
   * @param {number} windowSize - Cantidad de muestras históricas conservadas en el eje X (por defecto 60 segundos)
   */
  constructor(windowSize = 60) {
    this.windowSize = windowSize;
    this.charts = {};
    // Etiquetas de tiempo regresivo para el eje X: "60s", "59s", ... "1s"
    this.labels = Array.from({ length: windowSize }, (_, i) => `${windowSize - i}s`);

    // Modo de visualización de CPU:
    // 'total' = Promedio agregado de toda la CPU
    // 'all' = Todos los hilos superpuestos simultáneamente con colores diferenciados
    // '0', '1', '2'... = Vista aislada y enfocada en un único hilo
    this.cpuMode = 'total';
    this.cpuHistory = {
      total: Array(windowSize).fill(0),
      cores: [], // Matriz bidimensional: [indice_hilo][muestra_temporal]
    };

    // Paleta cromática coordinada para diferenciar hasta 12 hilos sin saturación visual
    this.coreColors = [
      '#6B7A3A', // Oliva
      '#6D2433', // Borravino
      '#8B6F55', // Marrón suave
      '#C67D28', // Ámbar
      '#3E6F7D', // Petróleo
      '#7D3E6F', // Ciruela
      '#4A7D3E', // Verde bosque
      '#7D5E3E', // Caramelo
      '#3E4E7D', // Índigo cálido
      '#7D3E4E', // Rubí
      '#5E6F3E', // Musgo
      '#8B556F', // Malva
    ];
  }

  /**
   * Inicializa las 4 instancias de gráficos de Chart.js:
   * CPU, RAM, Disco (Lectura/Escritura) y Red (Bajada/Subida).
   */
  initCharts() {
    // Configuración compartida de rejillas y ejes
    const commonScales = (yMax = 100, yUnit = '%') => ({
      x: {
        grid: { color: 'rgba(226, 215, 200, 0.4)', drawBorder: false },
        ticks: { color: '#8B6F55', font: { family: 'Plus Jakarta Sans', size: 10 }, maxTicksLimit: 6 },
      },
      y: {
        min: 0,
        max: yMax,
        grid: { color: 'rgba(226, 215, 200, 0.4)', drawBorder: false },
        ticks: {
          color: '#8B6F55',
          font: { family: 'Plus Jakarta Sans', size: 10 },
          callback: (value) => `${value}${yUnit ? ' ' + yUnit : ''}`,
        },
      },
    });

    // Opciones generales optimizadas para alta frecuencia de actualización
    const commonOptions = (yMax, yUnit, showLegend = false) => ({
      responsive: true,
      maintainAspectRatio: false,
      animation: false, // Vital para evitar bucles de renderizado y consumo excesivo
      plugins: {
        legend: {
          display: showLegend,
          labels: {
            font: { family: 'Plus Jakarta Sans', size: 10 },
            color: '#3E2F25',
            boxWidth: 12,
            boxHeight: 12,
          },
        },
        tooltip: {
          backgroundColor: '#3E2F25',
          titleFont: { family: 'Plus Jakarta Sans', size: 11 },
          bodyFont: { family: 'Plus Jakarta Sans', size: 11 },
          padding: 8,
          cornerRadius: 6,
        },
      },
      scales: commonScales(yMax, yUnit),
    });

    // 1. Gráfico de CPU
    const cpuCtx = document.getElementById('cpuChart')?.getContext('2d');
    if (cpuCtx) {
      this.charts.cpu = new Chart(cpuCtx, {
        type: 'line',
        data: {
          labels: [...this.labels],
          datasets: [{
            label: 'Uso Total CPU %',
            data: [...this.cpuHistory.total],
            borderColor: '#6B7A3A',
            backgroundColor: 'rgba(107, 122, 58, 0.15)',
            borderWidth: 2,
            pointRadius: 0,
            fill: true,
            tension: 0.25,
          }],
        },
        options: commonOptions(100, '%', false),
      });
    }

    // 2. Gráfico de Memoria RAM
    const ramCtx = document.getElementById('ramChart')?.getContext('2d');
    if (ramCtx) {
      this.charts.ram = new Chart(ramCtx, {
        type: 'line',
        data: {
          labels: [...this.labels],
          datasets: [{
            label: 'Uso RAM %',
            data: Array(this.windowSize).fill(0),
            borderColor: '#8B6F55',
            backgroundColor: 'rgba(139, 111, 85, 0.15)',
            borderWidth: 2,
            pointRadius: 0,
            fill: true,
            tension: 0.25,
          }],
        },
        options: commonOptions(100, '%'),
      });
    }

    // 3. Gráfico de Almacenamiento en Disco (Lectura vs Escritura)
    const diskCtx = document.getElementById('diskChart')?.getContext('2d');
    if (diskCtx) {
      this.charts.disk = new Chart(diskCtx, {
        type: 'line',
        data: {
          labels: [...this.labels],
          datasets: [
            {
              label: 'Lectura (MB/s)',
              data: Array(this.windowSize).fill(0),
              borderColor: '#6B7A3A',
              borderWidth: 1.8,
              pointRadius: 0,
              tension: 0.2,
            },
            {
              label: 'Escritura (MB/s)',
              data: Array(this.windowSize).fill(0),
              borderColor: '#6D2433',
              borderWidth: 1.8,
              pointRadius: 0,
              tension: 0.2,
            },
          ],
        },
        options: commonOptions(null, 'MB/s', true),
      });
    }

    // 4. Gráfico de Tráfico de Red (Bajada vs Subida)
    const netCtx = document.getElementById('networkChart')?.getContext('2d');
    if (netCtx) {
      this.charts.network = new Chart(netCtx, {
        type: 'line',
        data: {
          labels: [...this.labels],
          datasets: [
            {
              label: 'Bajada (KB/s)',
              data: Array(this.windowSize).fill(0),
              borderColor: '#6B7A3A',
              borderWidth: 1.8,
              pointRadius: 0,
              tension: 0.2,
            },
            {
              label: 'Subida (KB/s)',
              data: Array(this.windowSize).fill(0),
              borderColor: '#8B6F55',
              borderWidth: 1.8,
              pointRadius: 0,
              tension: 0.2,
            },
          ],
        },
        options: commonOptions(null, 'KB/s', true),
      });
    }
  }

  /**
   * Cambia el modo de visualización del gráfico de CPU.
   * @param {string} mode - 'total' | 'all' | índice del hilo ('0', '1', etc.)
   */
  setCpuViewMode(mode) {
    this.cpuMode = mode;
    this._rebuildCpuDatasets();
  }

  /**
   * Reconstruye la serie de datos del gráfico de CPU según el modo seleccionado.
   * - Si es 'total': muestra una única curva con el promedio del procesador.
   * - Si es 'all': despliega N curvas simultáneas correspondientes a cada hilo.
   * - Si es numérico: aísla y resalta exclusivamente el hilo indicado con su color.
   * @private
   */
  _rebuildCpuDatasets() {
    if (!this.charts.cpu) return;

    if (this.cpuMode === 'total') {
      this.charts.cpu.data.datasets = [{
        label: 'Uso Total CPU %',
        data: [...this.cpuHistory.total],
        borderColor: '#6B7A3A',
        backgroundColor: 'rgba(107, 122, 58, 0.15)',
        borderWidth: 2,
        pointRadius: 0,
        fill: true,
        tension: 0.25,
      }];
      this.charts.cpu.options.plugins.legend.display = false;
    } else if (this.cpuMode === 'all') {
      const coreCount = this.cpuHistory.cores.length;
      this.charts.cpu.data.datasets = Array.from({ length: coreCount }, (_, i) => ({
        label: `Hilo ${i}`,
        data: [...(this.cpuHistory.cores[i] || Array(this.windowSize).fill(0))],
        borderColor: this.coreColors[i % this.coreColors.length],
        borderWidth: 1.5,
        pointRadius: 0,
        fill: false,
        tension: 0.2,
      }));
      this.charts.cpu.options.plugins.legend.display = true;
    } else {
      const coreIdx = parseInt(this.cpuMode, 10);
      const color = this.coreColors[coreIdx % this.coreColors.length] || '#6B7A3A';
      const coreData = this.cpuHistory.cores[coreIdx] || Array(this.windowSize).fill(0);

      this.charts.cpu.data.datasets = [{
        label: `Uso Hilo ${coreIdx} %`,
        data: [...coreData],
        borderColor: color,
        backgroundColor: `${color}25`,
        borderWidth: 2,
        pointRadius: 0,
        fill: true,
        tension: 0.25,
      }];
      this.charts.cpu.options.plugins.legend.display = true;
    }

    // Actualiza sin disparar animaciones intrusivas
    this.charts.cpu.update('none');
  }

  /**
   * Desplaza la ventana temporal agregando los datos más recientes y eliminando los más antiguos (FIFO).
   * @param {Object} snapshot - Instantánea de hardware recibida por WebSocket
   */
  update(snapshot) {
    // 1. Desplazamiento y actualización de CPU
    if (snapshot.cpu && this.charts.cpu) {
      this.cpuHistory.total.push(snapshot.cpu.total_percent);
      if (this.cpuHistory.total.length > this.windowSize) {
        this.cpuHistory.total.shift();
      }

      const cores = snapshot.cpu.cores || [];
      if (this.cpuHistory.cores.length !== cores.length) {
        this.cpuHistory.cores = cores.map(() => Array(this.windowSize).fill(0));
      }

      cores.forEach((coreVal, i) => {
        this.cpuHistory.cores[i].push(coreVal);
        if (this.cpuHistory.cores[i].length > this.windowSize) {
          this.cpuHistory.cores[i].shift();
        }
      });

      if (this.cpuMode === 'total') {
        this.charts.cpu.data.datasets[0].data = [...this.cpuHistory.total];
      } else if (this.cpuMode === 'all') {
        this.charts.cpu.data.datasets.forEach((ds, idx) => {
          if (this.cpuHistory.cores[idx]) {
            ds.data = [...this.cpuHistory.cores[idx]];
          }
        });
      } else {
        const coreIdx = parseInt(this.cpuMode, 10);
        if (this.cpuHistory.cores[coreIdx]) {
          this.charts.cpu.data.datasets[0].data = [...this.cpuHistory.cores[coreIdx]];
        }
      }

      this.charts.cpu.update('none');
    }

    // 2. Desplazamiento y actualización de RAM
    if (snapshot.ram && this.charts.ram) {
      const data = this.charts.ram.data.datasets[0].data;
      data.push(snapshot.ram.percent);
      if (data.length > this.windowSize) data.shift();
      this.charts.ram.update('none');
    }

    // 3. Desplazamiento y auto-escalado de Disco
    if (snapshot.disk && this.charts.disk) {
      const rData = this.charts.disk.data.datasets[0].data;
      const wData = this.charts.disk.data.datasets[1].data;
      rData.push(snapshot.disk.read_mb_s);
      wData.push(snapshot.disk.write_mb_s);
      if (rData.length > this.windowSize) rData.shift();
      if (wData.length > this.windowSize) wData.shift();

      // Ajuste dinámico de escala en el eje Y para evitar que picos altos queden cortados
      const maxVal = Math.max(...rData, ...wData, 10);
      this.charts.disk.options.scales.y.max = Math.ceil(maxVal * 1.2);
      this.charts.disk.update('none');
    }

    // 4. Desplazamiento y auto-escalado de Red
    if (snapshot.network && this.charts.network) {
      const recvData = this.charts.network.data.datasets[0].data;
      const sentData = this.charts.network.data.datasets[1].data;
      recvData.push(snapshot.network.recv_kb_s);
      sentData.push(snapshot.network.sent_kb_s);
      if (recvData.length > this.windowSize) recvData.shift();
      if (sentData.length > this.windowSize) sentData.shift();

      const maxNet = Math.max(...recvData, ...sentData, 50);
      this.charts.network.options.scales.y.max = Math.ceil(maxNet * 1.2);
      this.charts.network.update('none');
    }
  }

  /**
   * Restablece todos los búferes históricos y limpia las series temporales de los 4 gráficos.
   */
  reset() {
    this.cpuHistory.total = Array(this.windowSize).fill(0);
    this.cpuHistory.cores = this.cpuHistory.cores.map(() => Array(this.windowSize).fill(0));

    Object.values(this.charts).forEach((chart) => {
      chart.data.datasets.forEach((ds) => {
        ds.data = Array(this.windowSize).fill(0);
      });
      chart.update('none');
    });
  }
}
