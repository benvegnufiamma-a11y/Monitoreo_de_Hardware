@echo off
setlocal EnableExtensions
cd /d "%~dp0"

:: ============================================================================
:: Script de Arranque 1-Clic para "Monitoreo de salud del hardware"
:: 
:: Automatizaciones realizadas:
:: 1. Comprueba la presencia de Python 3.10+ en el PATH.
:: 2. Crea de forma desatendida el entorno virtual (.venv) si no existe.
:: 3. Inicializa las variables de entorno (.env) a partir de .env.example.
:: 4. Instala y actualiza dependencias listadas en requirements.txt.
:: 5. Extrae el host y puerto configurados directamente desde Pydantic Settings.
:: 6. Abre el navegador predeterminado tras 2 segundos de gracia.
:: 7. Lanza el servidor ASGI Uvicorn con recarga en caliente (--reload).
:: ============================================================================

echo.
echo  ======================================================
echo   Monitoreo de salud del hardware - Arranque 1-Clic
echo  ======================================================
echo.

:: 1. Comprobación de Python en el PATH
where python >nul 2>&1
if errorlevel 1 (
  echo [ERROR] No se encontro Python en el PATH del sistema.
  echo Asegurate de tener instalado Python 3.11+ y marcar "Add python.exe to PATH".
  pause
  exit /b 1
)

:: 2. Detección y creación del entorno virtual (.venv o env)
if exist ".venv\Scripts\python.exe" (
  set "VENV_DIR=.venv"
) else if exist "env\Scripts\python.exe" (
  set "VENV_DIR=env"
) else (
  set "VENV_DIR=.venv"
)

set "PY_EXE=%VENV_DIR%\Scripts\python.exe"

if not exist "%PY_EXE%" (
  echo [1/5] Creando entorno virtual en \%VENV_DIR% ...
  python -m venv %VENV_DIR%
  if errorlevel 1 (
    echo [ERROR] No se pudo crear el entorno virtual.
    pause
    exit /b 1
  )
) else (
  echo [1/5] Entorno virtual encontrado en \%VENV_DIR%.
)

:: 3. Inicialización del archivo de configuración de entorno (.env)
if not exist ".env" (
  if exist ".env.example" (
    echo [2/5] Creando .env a partir de .env.example ...
    copy /Y ".env.example" ".env" >nul
  ) else (
    echo [2/5] Generando .env con configuracion predeterminada ...
    echo APP_NAME="Monitoreo de salud del hardware" > .env
    echo HOST=127.0.0.1 >> .env
    echo PORT=8000 >> .env
    echo DEBUG=True >> .env
  )
) else (
  echo [2/5] Archivo de configuracion .env encontrado.
)

:: 4. Instalación / Actualización de dependencias
echo [3/5] Verificando e instalando dependencias (requirements.txt) ...
"%PY_EXE%" -m pip install -r requirements.txt
if errorlevel 1 (
  echo [ERROR] Fallo la instalacion de dependencias.
  pause
  exit /b 1
)

:: 5. Detección de puerto y host configurados
for /f "usebackq delims=" %%P in (`"%PY_EXE%" -c "from app.core.config import get_settings; print(get_settings().PORT)" 2^>nul`) do set PORT=%%P
if "%PORT%"=="" set PORT=8000

for /f "usebackq delims=" %%H in (`"%PY_EXE%" -c "from app.core.config import get_settings; print(get_settings().HOST)" 2^>nul`) do set HOST=%%H
if "%HOST%"=="" set HOST=127.0.0.1

for /f "usebackq delims=" %%I in (`"%PY_EXE%" -c "import socket; s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.connect(('8.8.8.8', 80)); print(s.getsockname()[0]); s.close()" 2^>nul`) do set LOCAL_IP=%%I

echo.
echo  =======================================================
echo    Servidor activo y monitoreando en tiempo real:
echo     - Localhost:       http://localhost:%PORT%
echo     - URL Directa:     http://%HOST%:%PORT%
if not "%LOCAL_IP%"=="" if not "%HOST%"=="127.0.0.1" echo     - Red local [LAN]: http://%LOCAL_IP%:%PORT%
echo  =======================================================
echo.

:: 6. Abrir automáticamente en el navegador web
echo [4/5] Abriendo el navegador en http://localhost:%PORT% ...
start "" cmd /c "timeout /t 2 /nobreak >nul && start http://localhost:%PORT%"

:: 7. Iniciar el servidor Uvicorn
echo [5/5] Iniciando servidor FastAPI con Uvicorn (Presiona Ctrl+C para detener) ...
echo.
"%PY_EXE%" -m uvicorn app.main:app --host %HOST% --port %PORT% --reload

set EXITCODE=%ERRORLEVEL%
echo.
if not %EXITCODE%==0 (
  echo El servidor se detuvo con codigo %EXITCODE%.
  pause
)
exit /b %EXITCODE%
