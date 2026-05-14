"""Configuración central para el asistente local."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(slots=True)
class Settings:
    """Configuraciones base del asistente."""

    ollama_url: str = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
    model_name: str = os.getenv("MODEL_NAME", "mistral")
    db_path: str = os.getenv("DB_PATH", "assistant_memory.sqlite3")
    timeout_seconds: int = int(os.getenv("OLLAMA_TIMEOUT", "30"))


def get_settings() -> Settings:
    """Retorna una instancia de configuración, fácilmente extensible en el futuro."""
    return Settings()
