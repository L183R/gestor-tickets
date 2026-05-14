# Assistant Local (base inicial)

Asistente personal local en Python con arquitectura modular. Permite conversar por CLI, guardar memoria simple en SQLite, consultar un modelo local vía Ollama y registrar logs.

## Qué hace

- Interfaz CLI para conversar (`Tú >`).
- Persistencia de memoria en SQLite:
  - `interactions`: historial de conversación.
  - `facts`: datos clave-valor recordables.
- Backend de modelo local con Ollama (`/api/generate`).
- Configuración por variables de entorno.
- Logging en consola y en `assistant.log`.
- Tests básicos con `pytest`.

## Requisitos

- Python 3.11+
- Ollama instalado y ejecutándose en local.
- Un modelo descargado en Ollama (ej: `mistral`).

## Instalación

```bash
cd assistant_local
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Ejecutar Ollama

Ejemplo con `mistral`:

```bash
ollama pull mistral
ollama run mistral
```

El endpoint por defecto utilizado por el asistente es:

`http://localhost:11434/api/generate`

## Configuración

Valores por defecto en `config.py`:

- `OLLAMA_URL=http://localhost:11434/api/generate`
- `MODEL_NAME=mistral`
- `DB_PATH=assistant_memory.sqlite3`
- `OLLAMA_TIMEOUT=30`

Podés sobrescribirlos con variables de entorno:

```bash
export MODEL_NAME=llama3
export DB_PATH=mi_memoria.sqlite3
python main.py
```

## Uso

```bash
cd assistant_local
python main.py
```

Comandos especiales:

- `/salir`, `/exit`, `/quit`: salir.
- `/memoria`: listar facts guardados.
- `/recordar clave=valor`: guardar/actualizar un dato.
- `/historial`: mostrar interacciones recientes.

## Tests

```bash
cd assistant_local
pytest -q
```

## Qué NO hace todavía

- No se auto-modifica ni reescribe su código.
- No realiza commits automáticos ni merges automáticos.
- No ejecuta comandos del sistema por pedido del usuario.
- No envía datos a servicios externos (solo consulta Ollama local).
- No incluye evaluación automática avanzada ni pipelines CI/CD aún.
