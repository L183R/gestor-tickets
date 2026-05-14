"""Entrada CLI del asistente local."""

from __future__ import annotations

from chat import ChatAssistant
from config import get_settings
from logger_setup import setup_logger
from memory import MemoryStore
from model_router import ModelRouter

EXIT_COMMANDS = {"/salir", "/exit", "/quit"}


def run() -> None:
    settings = get_settings()
    logger = setup_logger()

    memory = MemoryStore(settings.db_path)
    router = ModelRouter(
        ollama_url=settings.ollama_url,
        model_name=settings.model_name,
        timeout_seconds=settings.timeout_seconds,
    )
    assistant = ChatAssistant(memory=memory, router=router)

    print("Asistente local iniciado. Escribí /salir para terminar.")

    while True:
        try:
            user_input = input("Tú > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nSaliendo...")
            logger.info("Sesión finalizada por interrupción del usuario")
            break

        if not user_input:
            continue

        if user_input.lower() in EXIT_COMMANDS:
            logger.info("Sesión finalizada por comando de salida")
            print("Hasta luego.")
            break

        response = assistant.process(user_input)
        logger.info("Usuario: %s | Asistente: %s", user_input, response)
        print(f"Asistente > {response}")


if __name__ == "__main__":
    run()
