"""Configuración de logging para consola y archivo."""

from __future__ import annotations

import logging
from pathlib import Path


def setup_logger(name: str = "assistant_local", level: int = logging.INFO) -> logging.Logger:
    """Crea y retorna un logger con salida a consola y archivo.

    Evita handlers duplicados si se llama más de una vez.
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    if logger.handlers:
        return logger

    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    file_handler = logging.FileHandler(Path("assistant.log"), encoding="utf-8")
    file_handler.setFormatter(formatter)

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return logger
