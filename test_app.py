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
            "/soporte/login",
            data={"username": "soporte", "password": "clave-anterior"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/soporte/admin/pending")

    def test_wrong_password_is_rejected(self):
        ticket_app.init_db()

        response = ticket_app.app.test_client().post(
            "/soporte/login",
            data={"username": "soporte", "password": "incorrecta"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("Credenciales inválidas".encode(), response.data)


class InterfaceCopyTests(unittest.TestCase):
    def setUp(self):
        ticket_app.app.config.update(TESTING=True, SECRET_KEY="test-secret")

    def test_public_pages_use_original_support_copy(self):
        client = ticket_app.app.test_client()

        home_response = client.get("/soporte/")
        self.assertIn("Panel de Problemas Comunes".encode(), home_response.data)
        self.assertIn("Crear ticket".encode(), home_response.data)
        self.assertNotIn("MISIÓN".encode(), home_response.data)
        self.assertNotIn("SECTOR".encode(), home_response.data)

        login_response = client.get("/soporte/login")
        self.assertIn("Ingreso Soporte".encode(), login_response.data)
        self.assertIn(">Ingresar<".encode(), login_response.data)
        self.assertNotIn("OPERADOR".encode(), login_response.data)

    def test_application_and_assets_use_support_base_path(self):
        client = ticket_app.app.test_client()

        response = client.get("/soporte/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(client.get("/").status_code, 404)
        self.assertIn(b'href="/soporte/login"', response.data)
        self.assertIn(b'href="/soporte/static/styles.css"', response.data)
        self.assertIn(b'src="/soporte/static/Imagenes/conexion.png"', response.data)


class TicketFieldsTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.temp_dir.name) / "tickets.db")
        self.db_patch = patch.object(ticket_app, "DB_PATH", self.db_path)
        self.db_patch.start()
        ticket_app.app.config.update(TESTING=True, SECRET_KEY="test-secret")
        ticket_app.init_db()

    def tearDown(self):
        self.db_patch.stop()
        self.temp_dir.cleanup()

    def test_form_only_asks_for_grade_name_ip_and_description(self):
        response = ticket_app.app.test_client().get(
            "/soporte/ticket/new/conectividad", environ_base={"REMOTE_ADDR": "192.0.2.10"}
        )

        self.assertIn("Grado / Nombre".encode(), response.data)
        self.assertIn(b'value="192.0.2.10" readonly', response.data)
        self.assertIn("Descripción del problema".encode(), response.data)
        self.assertNotIn(b'name="department"', response.data)
        self.assertNotIn(b'name="phone_internal"', response.data)

    def test_ticket_uses_request_ip_instead_of_submitted_ip(self):
        response = ticket_app.app.test_client().post(
            "/soporte/ticket/new/conectividad",
            data={
                "requester_name": "Cabo Ana Pérez",
                "local_ip": "203.0.113.99",
                "description": "No hay conexión",
            },
            environ_base={"REMOTE_ADDR": "192.0.2.10"},
        )

        self.assertEqual(response.status_code, 302)
        with sqlite3.connect(self.db_path) as connection:
            ticket = connection.execute(
                "SELECT requester_name, department, phone_internal, description, local_ip FROM tickets"
            ).fetchone()
        self.assertEqual(
            ticket,
            ("Cabo Ana Pérez", "", "", "No hay conexión", "192.0.2.10"),
        )


class PendingTicketVisibilityTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.temp_dir.name) / "tickets.db")
        self.db_patch = patch.object(ticket_app, "DB_PATH", self.db_path)
        self.db_patch.start()
        ticket_app.app.config.update(TESTING=True, SECRET_KEY="test-secret")
        ticket_app.init_db()
        with sqlite3.connect(self.db_path) as connection:
            tickets = (
                ("Ticket local", "192.0.2.10"),
                ("Ticket ajeno", "198.51.100.20"),
            )
            for requester, local_ip in tickets:
                connection.execute(
                    """
                    INSERT INTO tickets (
                        requester_name, department, phone_internal, problem_key,
                        problem_title, description, local_ip, created_at
                    ) VALUES (?, '', '', 'conectividad', 'Conectividad', 'Sin red', ?, '2026-08-06 10:00:00')
                    """,
                    (requester, local_ip),
                )

    def tearDown(self):
        self.db_patch.stop()
        self.temp_dir.cleanup()

    def test_anonymous_user_only_sees_pending_tickets_from_request_ip(self):
        client = ticket_app.app.test_client()
        response = client.get(
            "/soporte/admin/pending/data", environ_base={"REMOTE_ADDR": "192.0.2.10"}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["unresolved_count"], 1)
        self.assertEqual(
            [ticket["requester_name"] for ticket in response.json["tickets"]],
            ["Ticket local"],
        )
        self.assertEqual(response.json["users"], [])

    def test_authenticated_user_sees_all_pending_tickets(self):
        client = ticket_app.app.test_client()
        login_response = client.post(
            "/soporte/login", data={"username": "soporte", "password": "soporte123"}
        )
        self.assertEqual(login_response.status_code, 302)

        response = client.get(
            "/soporte/admin/pending/data", environ_base={"REMOTE_ADDR": "192.0.2.10"}
        )

        self.assertEqual(response.json["unresolved_count"], 2)
        self.assertCountEqual(
            [ticket["requester_name"] for ticket in response.json["tickets"]],
            ["Ticket local", "Ticket ajeno"],
        )
        self.assertGreater(len(response.json["users"]), 0)

    def test_anonymous_dashboard_hides_management_controls(self):
        response = ticket_app.app.test_client().get(
            "/soporte/admin/pending", environ_base={"REMOTE_ADDR": "192.0.2.10"}
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            "Mostrando únicamente los tickets creados desde tu IP".encode(),
            response.data,
        )
        self.assertIn(b"const isAuthenticated = false", response.data)


if __name__ == "__main__":
    unittest.main()
