"""Configuración del proyecto, leída de variables de entorno y del archivo ``.env``."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/src/vetrag/config.py → parents[3] = Proyecto/
RAIZ_PROYECTO = Path(__file__).resolve().parents[3]


class Configuracion(BaseSettings):
    """Valores configurables. Cada campo se puede sobrescribir con ``VETRAG_<CAMPO>``."""

    model_config = SettingsConfigDict(
        env_prefix="VETRAG_",
        env_file=RAIZ_PROYECTO / "backend" / ".env",
        extra="ignore",
    )

    ruta_assets: Path = RAIZ_PROYECTO / "assets"
    ruta_data: Path = RAIZ_PROYECTO / "data"

    @property
    def ruta_clasificacion(self) -> Path:
        """Carpeta de salida de la F1."""
        return self.ruta_data / "01_clasificacion"

    @property
    def ruta_piloto(self) -> Path:
        """Lista de documentos del piloto (fuera de git: contiene nombres de libros)."""
        return self.ruta_data / "piloto.txt"

    @property
    def ruta_ocr(self) -> Path:
        """Carpeta de salida del paso de OCR (F2)."""
        return self.ruta_data / "02_ocr"

    @property
    def ruta_markdown(self) -> Path:
        """Carpeta de salida del paso de conversión a Markdown (F2)."""
        return self.ruta_data / "03_markdown"

    @property
    def ruta_limpio(self) -> Path:
        """Carpeta de salida del paso de limpieza (F2)."""
        return self.ruta_data / "04_limpio"


@lru_cache
def obtener_configuracion() -> Configuracion:
    """Devuelve la configuración (se crea una sola vez)."""
    return Configuracion()
