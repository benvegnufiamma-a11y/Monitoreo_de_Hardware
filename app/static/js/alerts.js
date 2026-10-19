/**
 * Gestor de alertas visuales y banners para condiciones críticas de hardware.
 * 
 * Implementa tres reglas de negocio clave:
 * 1. Persistencia: Las alertas se mantienen en pantalla fijas mientras la condición exista.
 * 2. Anti-duplicación: No se repite la misma alerta si ya está siendo mostrada al usuario.
 * 3. Enfriamiento (Cooldown) de 1 minuto: Si el usuario descarta manualmente una alerta haciendo clic
 *    en '✕', esa alerta en específico queda silenciada exactamente durante 60 segundos antes de volver a saltar.
 */
export class AlertsManager {
  /**
   * @param {string} containerId - ID del contenedor DOM donde se insertan los banners flotantes
   */
  constructor(containerId = 'alertsContainer') {
    this.container = document.getElementById(containerId);
    this.activeAlerts = new Map(); // alertKey -> HTMLElement del banner activo en pantalla
    this.dismissCooldowns = new Map(); // alertKey -> timestamp epoch en ms hasta el cual está silenciada
    this.cooldownMs = 60 * 1000; // 1 minuto (60.000 ms)
  }

  /**
   * Procesa la lista de alertas enviada por el servidor en cada ciclo de streaming.
   * @param {Array} alerts - Lista de objetos de alerta recibidos
   */
  handleAlerts(alerts) {
    // 1. Resaltado perimetral con borde pulsante en las tarjetas de hardware
    this._updateCardHighlights(alerts);

    if (!alerts || alerts.length === 0) {
      return;
    }

    const now = Date.now();

    alerts.forEach((alert) => {
      // Clave identificadora única por subsistema y nivel (ej: 'cpu_critical', 'ram_warning')
      const alertKey = `${alert.metric}_${alert.level}`;

      // Regla 1: Si ya está en pantalla, no duplicar ni generar parpadeos
      if (this.activeAlerts.has(alertKey)) {
        return;
      }

      // Regla 2: Si el usuario la cerró manualmente, verificar si expiró el minuto de gracia
      const cooldownUntil = this.dismissCooldowns.get(alertKey);
      if (cooldownUntil && now < cooldownUntil) {
        return;
      }

      // Mostrar el banner persistente en la esquina superior derecha
      this._showBanner(alertKey, alert);
    });
  }

  /**
   * Crea e inserta el elemento DOM del banner de alerta.
   * @private
   */
  _showBanner(alertKey, alert) {
    if (!this.container) return;

    const banner = document.createElement('div');
    banner.className = `alert-banner ${alert.level}`;

    const textSpan = document.createElement('span');
    textSpan.textContent = `[${alert.level.toUpperCase()}] ${alert.message}`;
    banner.appendChild(textSpan);

    // Botón de descarte manual ('✕')
    const closeBtn = document.createElement('button');
    closeBtn.type = 'button';
    closeBtn.textContent = '✕';
    closeBtn.title = 'Descartar alerta (silenciar por 1 minuto)';
    closeBtn.style.background = 'none';
    closeBtn.style.border = 'none';
    closeBtn.style.cursor = 'pointer';
    closeBtn.style.color = 'inherit';
    closeBtn.style.fontSize = '1.1rem';
    closeBtn.style.padding = '0 0.5rem';
    closeBtn.style.lineHeight = '1';

    closeBtn.onclick = (e) => {
      e.stopPropagation();
      this._userDismiss(alertKey, banner);
    };
    banner.appendChild(closeBtn);

    // Se inserta al inicio del contenedor para mostrar la más reciente arriba
    this.container.prepend(banner);
    this.activeAlerts.set(alertKey, banner);
  }

  /**
   * Maneja el clic de cierre por parte del usuario:
   * Activa el período de enfriamiento de 60 segundos y elimina el banner del DOM.
   * @private
   */
  _userDismiss(alertKey, bannerElement) {
    // Registra el timestamp futuro en que expirará el silencio
    this.dismissCooldowns.set(alertKey, Date.now() + this.cooldownMs);

    // Remueve el elemento del árbol DOM de forma segura
    if (bannerElement && bannerElement.parentNode) {
      bannerElement.parentNode.removeChild(bannerElement);
    }
    this.activeAlerts.delete(alertKey);
  }

  /**
   * Aplica estilos visuales de advertencia (amarillo) o peligro (rojo/borravino) a las 4 tarjetas principales.
   * @private
   */
  _updateCardHighlights(alerts) {
    // Restablece todas las tarjetas al estado neutro por defecto
    ['cpu', 'ram', 'disk', 'network'].forEach((metric) => {
      const card = document.getElementById(`card-${metric}`);
      if (card) {
        card.classList.remove('is-warning', 'is-critical');
      }
    });

    // Aplica las clases CSS correspondientes a las tarjetas con problemas activos
    if (alerts) {
      alerts.forEach((alert) => {
        const card = document.getElementById(`card-${alert.metric}`);
        if (card) {
          card.classList.remove('is-warning', 'is-critical');
          if (alert.level === 'critical') {
            card.classList.add('is-critical');
          } else if (alert.level === 'warning') {
            card.classList.add('is-warning');
          }
        }
      });
    }
  }

  /**
   * Limpia todos los banners visibles y restablece el estado.
   */
  clearAll() {
    if (this.container) {
      this.container.innerHTML = '';
    }
    this.activeAlerts.clear();
    this._updateCardHighlights([]);
  }
}
