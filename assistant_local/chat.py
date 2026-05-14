"""Orquestación principal de conversación."""

from __future__ import annotations

from memory import MemoryStore
from model_router import ModelRouter


class ChatAssistant:
    def __init__(self, memory: MemoryStore, router: ModelRouter) -> None:
        self.memory = memory
        self.router = router

    def process(self, user_message: str) -> str:
        normalized = user_message.strip()

        if normalized == "/memoria":
            facts = self.memory.list_facts()
            if not facts:
                return "No hay datos guardados en memoria." 
            return "\n".join([f"- {item['key']}={item['value']}" for item in facts])

        if normalized.startswith("/recordar "):
            body = normalized.replace("/recordar ", "", 1)
            if "=" not in body:
                return "Formato inválido. Usá: /recordar clave=valor"
            key, value = body.split("=", 1)
            key = key.strip()
            value = value.strip()
            if not key or not value:
                return "Formato inválido. La clave y el valor no pueden estar vacíos."
            self.memory.save_fact(key, value)
            return f"Dato guardado: {key}={value}"

        if normalized == "/historial":
            items = self.memory.get_recent_interactions(limit=10)
            if not items:
                return "Todavía no hay historial." 
            lines = []
            for item in items:
                lines.append(f"[{item['timestamp']}] Tú: {item['user_message']}")
                lines.append(f"[{item['timestamp']}] Asistente: {item['assistant_response']}")
            return "\n".join(lines)

        prompt = self._build_prompt(normalized)
        assistant_response = self.router.generate(prompt)
        self.memory.save_interaction(normalized, assistant_response)
        return assistant_response

    def _build_prompt(self, user_message: str) -> str:
        history = self.memory.get_recent_interactions(limit=5)
        history_lines = []
        for item in reversed(history):
            history_lines.append(f"Usuario: {item['user_message']}")
            history_lines.append(f"Asistente: {item['assistant_response']}")

        context = "\n".join(history_lines) if history_lines else "(sin historial previo)"

        return (
            "Sos un asistente personal local, útil, claro y breve. "
            "No ejecutes comandos del sistema ni acciones riesgosas.\n\n"
            f"Historial reciente:\n{context}\n\n"
            f"Mensaje actual del usuario: {user_message}\n"
            "Respuesta del asistente:"
        )
