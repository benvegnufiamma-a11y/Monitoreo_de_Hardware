/**
 * Cliente WebSocket para comunicación bidireccional y streaming en vivo.
 * 
 * Gestiona el ciclo de vida del socket, reconexión automática con retroceso exponencial
 * (exponential backoff) y despacho de eventos al orquestador de la aplicación.
 */
export class MonitorSocket {
  /**
   * @param {Object} callbacks - Manejadores de eventos de la conexión
   * @param {Function} callbacks.onSnapshot - Invocado al recibir una instantánea en tiempo real
   * @param {Function} callbacks.onBaseline - Invocado al recibir datos iniciales o comprobación
   * @param {Function} callbacks.onStatus - Invocado al cambiar el estado del servidor
   * @param {Function} callbacks.onError - Invocado ante anomalías o errores
   * @param {Function} callbacks.onConnectionChange - Invocado al conectar o desconectar (true/false)
   */
  constructor({ onSnapshot, onBaseline, onStatus, onError, onConnectionChange }) {
    this.onSnapshot = onSnapshot;
    this.onBaseline = onBaseline;
    this.onStatus = onStatus;
    this.onError = onError;
    this.onConnectionChange = onConnectionChange;

    this.socket = null;
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = 5;
    this.reconnectTimeout = null;
  }

  /**
   * Abre la conexión WebSocket con el servidor backend.
   * Determina automáticamente si corresponde 'ws:' o 'wss:' según el protocolo HTTP actual.
   */
  connect() {
    // Si ya existe una conexión abierta o en proceso de enlace, no duplicar
    if (this.socket && (this.socket.readyState === WebSocket.OPEN || this.socket.readyState === WebSocket.CONNECTING)) {
      return;
    }

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/monitor`;

    this.socket = new WebSocket(wsUrl);

    // Evento de apertura exitosa: reinicia contadores de reintento
    this.socket.onopen = () => {
      this.reconnectAttempts = 0;
      if (this.onConnectionChange) this.onConnectionChange(true);
    };

    // Evento de cierre: notifica a la UI e inicia ciclo de reconexión
    this.socket.onclose = () => {
      if (this.onConnectionChange) this.onConnectionChange(false);
      this._attemptReconnect();
    };

    // Evento de error
    this.socket.onerror = () => {
      if (this.onError) this.onError('Error en la conexión WebSocket');
    };

    // Recepción y procesamiento de paquetes JSON entrantes
    this.socket.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data);
        if (payload.type === 'snapshot' && this.onSnapshot) {
          this.onSnapshot(payload.data, payload.alerts || []);
        } else if ((payload.type === 'baseline' || payload.type === 'health_check') && this.onBaseline) {
          this.onBaseline(payload.data, payload.alerts || []);
        } else if (payload.type === 'status' && this.onStatus) {
          this.onStatus(payload.status, payload.metrics || []);
        } else if (payload.type === 'error' && this.onError) {
          this.onError(payload.message || 'Error recibido del servidor');
        }
      } catch (e) {
        console.error('Error parseando mensaje WebSocket:', e);
      }
    };
  }

  /**
   * Intenta reconectar progresivamente duplicando el tiempo de espera (1s, 2s, 4s, 8s, hasta 10s máx).
   * @private
   */
  _attemptReconnect() {
    if (this.reconnectAttempts < this.maxReconnectAttempts) {
      this.reconnectAttempts++;
      const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts), 10000);
      clearTimeout(this.reconnectTimeout);
      this.reconnectTimeout = setTimeout(() => this.connect(), delay);
    }
  }

  /**
   * Envía comando para activar o reconfigurar las métricas y umbrales monitoreados.
   */
  start(metrics, thresholds) {
    if (!this.socket || this.socket.readyState !== WebSocket.OPEN) {
      this.connect();
      setTimeout(() => this.start(metrics, thresholds), 500);
      return;
    }

    const message = {
      action: 'start',
      metrics: metrics,
      thresholds: thresholds,
    };
    this.socket.send(JSON.stringify(message));
  }

  /**
   * Envía comando de pausa o detención.
   */
  stop() {
    if (this.socket && this.socket.readyState === WebSocket.OPEN) {
      this.socket.send(JSON.stringify({ action: 'stop' }));
    }
  }
}
