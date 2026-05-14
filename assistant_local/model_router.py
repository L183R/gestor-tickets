"""Router de modelos. Actualmente soporta Ollama local."""

from __future__ import annotations

from dataclasses import dataclass

import requests


@dataclass(slots=True)
class ModelRouter:
    ollama_url: str
    model_name: str
    timeout_seconds: int = 30

    def generate(self, prompt: str) -> str:
        """Genera respuesta usando backend local configurado."""
        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": False,
        }
        try:
            response = requests.post(self.ollama_url, json=payload, timeout=self.timeout_seconds)
            response.raise_for_status()
            data = response.json()
            return (data.get("response") or "").strip() or "No hubo respuesta del modelo."
        except requests.exceptions.ConnectionError:
            return "Error: no se pudo conectar con Ollama. Verificá que esté corriendo localmente."
        except requests.exceptions.Timeout:
            return "Error: tiempo de espera agotado al consultar Ollama."
        except requests.exceptions.RequestException as exc:
            return f"Error al consultar el modelo local: {exc}"
        except ValueError:
            return "Error: la respuesta del modelo no tiene formato JSON válido."
