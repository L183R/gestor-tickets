import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import app as ticket_app
from werkzeug.security import check_password_hash


class PasswordSecurityTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.temp_dir.name) / "tickets.db")
        self.db_patch = patch.object(ticket_app, "DB_PATH", self.db_path)
        self.db_patch.start()
        ticket_app.app.config.update(TESTING=True, SECRET_KEY="test-secret")

    def tearDown(self):
        self.db_patch.stop()
        self.temp_dir.cleanup()

    def test_initial_users_are_stored_with_password_hashes(self):
        ticket_app.init_db()

        with sqlite3.connect(self.db_path) as connection:
            stored_password = connection.execute(
                "SELECT password FROM users WHERE username = 'soporte'"
            ).fetchone()[0]

        self.assertNotEqual(stored_password, "soporte123")
        self.assertTrue(check_password_hash(stored_password, "soporte123"))

    def test_plaintext_passwords_are_migrated_and_login_still_works(self):
        ticket_app.init_db()
        with sqlite3.connect(self.db_path) as connection:
            connection.execute(
                "UPDATE users SET password = ? WHERE username = ?",
                ("clave-anterior", "soporte"),
            )
        ticket_app.init_db()

        with sqlite3.connect(self.db_path) as connection:
            stored_password = connection.execute(
                "SELECT password FROM users WHERE username = 'soporte'"
            ).fetchone()[0]

        self.assertTrue(check_password_hash(stored_password, "clave-anterior"))
        response = ticket_app.app.test_client().post(
            "/login",
            data={"username": "soporte", "password": "clave-anterior"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/admin/pending")

    def test_wrong_password_is_rejected(self):
        ticket_app.init_db()

        response = ticket_app.app.test_client().post(
            "/login",
            data={"username": "soporte", "password": "incorrecta"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("Credenciales inválidas".encode(), response.data)


class InterfaceCopyTests(unittest.TestCase):
    def setUp(self):
        ticket_app.app.config.update(TESTING=True, SECRET_KEY="test-secret")

    def test_public_pages_use_original_support_copy(self):
        client = ticket_app.app.test_client()

        home_response = client.get("/")
        self.assertIn("Panel de Problemas Comunes".encode(), home_response.data)
        self.assertIn("Crear ticket".encode(), home_response.data)
        self.assertNotIn("MISIÓN".encode(), home_response.data)
        self.assertNotIn("SECTOR".encode(), home_response.data)

        login_response = client.get("/login")
        self.assertIn("Ingreso Soporte".encode(), login_response.data)
        self.assertIn(">Ingresar<".encode(), login_response.data)
        self.assertNotIn("OPERADOR".encode(), login_response.data)


if __name__ == "__main__":
    unittest.main()
