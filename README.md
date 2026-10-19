# Monitoreo de salud del hardware

Aplicación web moderna y minimalista para el monitoreo de hardware en tiempo real, inspirada en la pestaña de rendimiento del Administrador de Tareas. Desarrollada en **Python 3.11+ (FastAPI)** con frontend reactivo en **HTML5, CSS3, ES Modules y Chart.js**.

---

## Características Principales

* **Monitoreo en tiempo real bajo demanda:** Inicio y pausa de captura con un solo clic para evitar consumo innecesario de recursos en reposo.
* **Métricas modulares seleccionables:**
  * **CPU:** Porcentaje de uso total, núcleos/hilos y frecuencia actual en MHz.
  * **Memoria RAM:** Porcentaje de ocupación, GB usados, disponibles y uso de swap.
  * **Disco (I/O):** Espacio total/usado y tasas de lectura y escritura en MB/s.
  * **Red (Tráfico):** Velocidades de subida y bajada en KB/s.
* **Ventana deslizante de 60 segundos:** Gráficos continuos actualizados cada 1 segundo con ajuste dinámico de escala.
* **Sistema de alertas visuales:** Detección en vivo de umbrales configurables (*Advertencia* y *Crítico*), banners flotantes y marcado perimetral de tarjetas.
* **Exportación de sesión:** Descarga de las muestras recopiladas en formatos estructurados **CSV** o **JSON**.

---

## Arquitectura del Proyecto

```text
hardware_monitor/
├── .env                     # Variables de entorno locales activas
├── .env.example             # Plantilla segura sin secretos expuestos
├── .gitignore               # Filtro de seguridad (excluye .venv, .env, __pycache__)
├── requirements.txt         # Dependencias fijadas para producción y pruebas
├── README.md                # Guía integral de instalación, uso y arquitectura
├── app/
│   ├── __init__.py
│   ├── main.py              # Ensamblado FastAPI, middlewares y ciclo de vida
│   ├── core/
│   │   ├── config.py        # Configuración tipada con Pydantic Settings
│   │   └── security.py      # Middleware con cabeceras HTTP (CSP, nosniff, anti-clickjacking)
│   ├── schemas/
│   │   ├── alerts.py        # Modelos de umbrales y eventos de alerta
│   │   └── metrics.py       # Modelos de métricas, snapshots y comandos de entrada
│   ├── services/
│   │   ├── hardware_service.py # Recolección psutil no bloqueante y deltas de I/O
│   │   ├── alert_service.py # Evaluación de reglas y severidad en tiempo real
│   │   └── export_service.py# Serialización aplanada a CSV y JSON
│   ├── api/
│   │   ├── routes.py        # Controladores REST (/api/health, /api/system-info, /api/export)
│   │   └── websockets.py    # Streaming bidireccional en vivo (/ws/monitor)
│   ├── static/
│   │   ├── css/
│   │   │   └── styles.css   # Variables CSS, paleta beige/oliva/borravino, responsive
│   │   └── js/
│   │       ├── alerts.js    # Banners de alerta con sanitización DOM anti-XSS
│   │       ├── app.js       # Orquestador del frontend y gestión de descargas
│   │       ├── charts.js    # 4 gráficos Chart.js con ventana temporal de 60s
│   │       └── socket.js    # Cliente WebSocket resiliente con reconexión
│   └── templates/
│       └── index.html       # Interfaz accesible y semántica
└── tests/
    └── test_backend.py      # 12 pruebas unitarias y de integración (pytest)
```

---

## Requisitos Previos

* **Python 3.11 o superior** (probado y verificado en Python 3.14).
* Sistema operativo: **Windows 10/11**, **Linux** o **macOS**.

---

## Instalación y Configuración

1. **Clonar o ubicarse en la carpeta del proyecto:**
   ```powershell
   # 1. Clonar el repositorio y entrar a la carpeta del proyecto:
   git clone https://github.com/benvegnufiamma-a11y/Monitoreo_de_Hardware.git
   cd Monitoreo_de_Hardware
   ```

2. **Crear y activar el entorno virtual:**
   * En Windows (PowerShell):
     ```powershell
     python -m venv .venv
     .\.venv\Scripts\Activate.ps1
     ```
   * En Linux / macOS (Bash):
     ```bash
     python3 -m venv .venv
     source .venv/bin/activate
     ```

3. **Instalar dependencias fijadas:**
   ```powershell
   pip install -r requirements.txt
   ```

4. **Configurar el archivo de entorno:**
   Si no existe `.env`, copiarlo desde la plantilla:
   ```powershell
   copy .env.example .env
   ```

---

## Ejecución del Servidor

### Opción Rápida (1 solo clic en Windows)
Hacé doble clic sobre el archivo **`iniciar.bat`** en la carpeta del proyecto.
El script se encarga de:
1. Verificar Python en el sistema.
2. Crear y detectar el entorno virtual (`.venv`).
3. Generar el archivo `.env` automáticamente si no existe.
4. Instalar o actualizar las dependencias (`requirements.txt`).
5. Abrir el navegador en `http://localhost:8000` e iniciar el servidor en tiempo real.

---

### Modo Manual (PowerShell / CMD)
```powershell
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### Modo Producción
```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1 --no-access-log
```

Abrir en el navegador: **[http://127.0.0.1:8000](http://127.0.0.1:8000)**

---

## Ejecución de Pruebas Automatizadas

La suite incluye 12 pruebas que cubren:
* Endpoints REST (`/api/health`, `/api/system-info`, `/api/export`).
* Renderizado de la plantilla HTML principal (`/`).
* Streaming y comandos WebSocket (`ping`, `start`, `stop`, manejo de comandos malformados).
* Detección de umbrales críticos de hardware.
* Cabeceras de seguridad HTTP activas.

Para ejecutar los tests:
```powershell
.\.venv\Scripts\pytest -v
```

---

## Decisiones de Seguridad Implementadas

1. **Host Binding Restringido:** El servidor escucha por defecto en `127.0.0.1`, evitando exposición a la red local sin autorización previa.
2. **Cabeceras HTTP Defensivas:**
   * `Content-Security-Policy`: Limita la carga de scripts únicamente al propio origen y CDNs autorizados para Chart.js y Google Fonts.
   * `X-Frame-Options: DENY`: Evita ataques de clickjacking.
   * `X-Content-Type-Options: nosniff`: Previene ataques basados en confusión de tipos MIME.
3. **Validación Estricta con Pydantic:** Todo comando enviado a través del WebSocket o de la API REST es parseado y validado contra modelos fuertemente tipados. Los datos malformados son rechazados de forma segura con mensajes genéricos.
4. **Prevención de XSS:** La renderización de alertas y mensajes dinámicos en el frontend se realiza mediante asignación de `textContent` o nodos seguros del DOM, nunca concatenando HTML sin sanitizar.
