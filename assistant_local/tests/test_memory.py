from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))

from memory import MemoryStore


def test_save_and_get_interaction(tmp_path):
    db_path = tmp_path / "test_memory.sqlite3"
    store = MemoryStore(str(db_path))

    store.save_interaction("hola", "hola, ¿cómo estás?")
    items = store.get_recent_interactions(limit=5)

    assert len(items) == 1
    assert items[0]["user_message"] == "hola"
    assert "hola" in items[0]["assistant_response"]


def test_save_and_get_fact(tmp_path):
    db_path = tmp_path / "test_facts.sqlite3"
    store = MemoryStore(str(db_path))

    store.save_fact("ciudad", "Buenos Aires")
    fact = store.get_fact("ciudad")

    assert fact is not None
    assert fact["key"] == "ciudad"
    assert fact["value"] == "Buenos Aires"
