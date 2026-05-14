from pathlib import Path
import sys
from unittest.mock import Mock, patch

sys.path.append(str(Path(__file__).resolve().parents[1]))

import requests

from model_router import ModelRouter


def test_generate_success():
    router = ModelRouter("http://localhost:11434/api/generate", "mistral", timeout_seconds=5)

    mock_response = Mock()
    mock_response.json.return_value = {"response": "Respuesta de prueba"}
    mock_response.raise_for_status.return_value = None

    with patch("model_router.requests.post", return_value=mock_response) as mock_post:
        output = router.generate("Hola")

    assert output == "Respuesta de prueba"
    mock_post.assert_called_once()


def test_generate_connection_error():
    router = ModelRouter("http://localhost:11434/api/generate", "mistral", timeout_seconds=5)

    with patch("model_router.requests.post", side_effect=requests.exceptions.ConnectionError):
        output = router.generate("Hola")

    assert "no se pudo conectar" in output.lower()
