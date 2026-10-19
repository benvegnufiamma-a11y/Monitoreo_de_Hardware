"""Configuración global de la aplicación mediante Pydantic Settings.

Permite cargar configuraciones desde variables de entorno y archivo .env,
con valores por defecto seguros para desarrollo local.
"""

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Esquema centralizado de configuración de la aplicación.
    
    Utiliza Pydantic Settings para cargar variables desde el archivo .env o del entorno del sistema.
    Si una variable no está definida, se aplican valores por defecto seguros para ejecución local.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # Ignora variables adicionales que no estén declaradas en este esquema
    )

    # Identidad y metadatos de la aplicación
    APP_NAME: str = "Monitoreo de salud del hardware"
    
    # Parámetros de red para el servidor Uvicorn
    HOST: str = "127.0.0.1"  # Vinculación por defecto a localhost para máxima seguridad
    PORT: int = 8000
    DEBUG: bool = False  # En modo debug se habilita la documentación interactiva Swagger (/docs)

    # Parámetros de recolección y renderizado de métricas
    DEFAULT_SAMPLING_INTERVAL_SECONDS: float = 1.0  # Intervalo de muestreo continuo en segundos
    SLIDING_WINDOW_SECONDS: int = 60  # Ventana temporal de retención en gráficos frontend (1 minuto)
    
    # Lista de dominios/orígenes autorizados para peticiones CORS
    ALLOWED_HOSTS: list[str] = ["127.0.0.1", "localhost"]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Devuelve una instancia única (singleton) en caché de la configuración.
    
    El decorador @lru_cache asegura que el archivo .env solo se lea y parseé
    una única vez durante el ciclo de vida del servidor, optimizando el rendimiento.
    """
    return Settings()
