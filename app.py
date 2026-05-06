from __future__ import annotations

import json
import os
import sqlite3
import time
from datetime import datetime
from functools import wraps
from typing import Any

from flask import Flask, Response, flash, g, jsonify, redirect, render_template, request, session, stream_with_context, url_for

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "tickets.db")

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-change-me")

COMMON_PROBLEMS = [
    {
        "id": "conectividad",
        "title": "Conectividad",
        "description": "Fallas de red, cortes de internet, Wi‑Fi inestable o sin acceso a servicios internos.",
        "image": "https://images.unsplash.com/photo-1558494949-ef010cbdcc31?auto=format&fit=crop&w=600&q=60",
    },
    {
        "id": "equipo-lentos",
        "title": "Equipo lentos",
        "description": "Computadores con bajo rendimiento, lentitud general o bloqueos frecuentes.",
        "image": "https://images.unsplash.com/photo-1518770660439-4636190af475?auto=format&fit=crop&w=600&q=60",
    },
    {
        "id": "correo-electronico",
        "title": "Correo electrónico",
        "description": "Errores al enviar o recibir correos, problemas de sincronización o acceso al buzón.",
        "image": "https://images.unsplash.com/photo-1516321318423-f06f85e504b3?auto=format&fit=crop&w=600&q=60",
    },
    {
        "id": "inicio-sesion",
        "title": "Inicio de sesión",
        "description": "Dificultades para autenticarse, contraseñas inválidas o cuentas bloqueadas.",
        "image": "https://images.unsplash.com/photo-1488229297570-58520851e868?auto=format&fit=crop&w=600&q=60",
    },
    {
        "id": "impresora",
        "title": "Impresora",
        "description": "Documentos atascados en cola, fallas de conexión o errores durante la impresión.",
        "image": "https://images.unsplash.com/photo-1563986768609-322da13575f3?auto=format&fit=crop&w=600&q=60",
    },
    {
        "id": "programas",
        "title": "Programas",
        "description": "Aplicaciones que no abren, se cierran solas o presentan mensajes de error.",
        "image": "https://images.unsplash.com/photo-1461749280684-dccba630e2f6?auto=format&fit=crop&w=600&q=60",
    },
    {
        "id": "acceso-recursos",
        "title": "Acceso a recursos",
        "description": "Sin permisos o acceso a carpetas compartidas, sistemas corporativos o herramientas internas.",
        "image": "https://images.unsplash.com/photo-1451187580459-43490279c0fa?auto=format&fit=crop&w=600&q=60",
    },
    {
        "id": "otros",
        "title": "Otros",
        "description": "Incidentes no clasificados en categorías anteriores y solicitudes especiales de soporte.",
        "image": "https://images.unsplash.com/photo-1451187863213-d1bcbaae3fa3?auto=format&fit=crop&w=600&q=60",
    },
]


def db() -> sqlite3.Connection:
    if "db" not in g:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        g.db = conn
    return g.db


@app.teardown_appcontext
def close_db(_: Any) -> None:
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


def init_db() -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            full_name TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            requester_name TEXT NOT NULL,
            department TEXT NOT NULL,
            phone_internal TEXT NOT NULL,
            problem_key TEXT NOT NULL,
            problem_title TEXT NOT NULL,
            description TEXT NOT NULL,
            local_ip TEXT NOT NULL,
            created_at TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pendiente',
            assigned_to_user_id INTEGER,
            canceled_by_requester INTEGER NOT NULL DEFAULT 0,
            closed_by_user_id INTEGER,
            closed_at TEXT,
            close_note TEXT,
            FOREIGN KEY (assigned_to_user_id) REFERENCES users(id),
            FOREIGN KEY (closed_by_user_id) REFERENCES users(id)
        );
        """
    )
    cur.execute("SELECT COUNT(*) as total FROM users")
    if cur.fetchone()["total"] == 0:
        cur.execute(
            "INSERT INTO users (username, password, full_name) VALUES (?, ?, ?)",
            ("soporte", "soporte123", "Mesa de Ayuda"),
        )
        cur.execute(
            "INSERT INTO users (username, password, full_name) VALUES (?, ?, ?)",
            ("tecnico2", "tecnico123", "Técnico Secundario"),
        )
    conn.commit()
    conn.close()


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            flash("Debes iniciar sesión.", "warning")
            return redirect(url_for("login"))
        return fn(*args, **kwargs)

    return wrapper


def client_ip() -> str:
    forwarded = request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
    if forwarded:
        return forwarded
    return request.remote_addr or "desconocida"


@app.route("/")
def home():
    return render_template("home.html", problems=COMMON_PROBLEMS)


@app.route("/ticket/new/<problem_id>", methods=["GET", "POST"])
def create_ticket(problem_id: str):
    problem = next((p for p in COMMON_PROBLEMS if p["id"] == problem_id), None)
    if not problem:
        flash("Problema no encontrado.", "danger")
        return redirect(url_for("home"))

    if request.method == "POST":
        requester_name = request.form.get("requester_name", "").strip()
        department = request.form.get("department", "").strip()
        phone_internal = request.form.get("phone_internal", "").strip()
        description = request.form.get("description", "").strip()

        if not all([requester_name, department, phone_internal, description]):
            flash("Completa todos los campos obligatorios.", "danger")
            return render_template("create_ticket.html", problem=problem)

        created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        local_ip = client_ip()

        cur = db().cursor()
        cur.execute(
            """
            INSERT INTO tickets (
                requester_name, department, phone_internal,
                problem_key, problem_title, description,
                local_ip, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                requester_name,
                department,
                phone_internal,
                problem["id"],
                problem["title"],
                description,
                local_ip,
                created_at,
            ),
        )
        db().commit()
        ticket_id = cur.lastrowid
        flash(f"Ticket #{ticket_id} creado exitosamente.", "success")
        return redirect(url_for("ticket_created", ticket_id=ticket_id))

    return render_template("create_ticket.html", problem=problem)


@app.route("/ticket/created/<int:ticket_id>")
def ticket_created(ticket_id: int):
    ticket = db().execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
    if not ticket:
        flash("Ticket no encontrado.", "danger")
        return redirect(url_for("home"))
    return render_template("ticket_created.html", ticket=ticket)


@app.route("/ticket/cancel/<int:ticket_id>", methods=["POST"])
def cancel_by_requester(ticket_id: int):
    cur = db().cursor()
    cur.execute(
        """
        UPDATE tickets
        SET status = 'cancelado', canceled_by_requester = 1,
            closed_at = ?, close_note = 'Cancelado por solicitante'
        WHERE id = ? AND status = 'pendiente'
        """,
        (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), ticket_id),
    )
    db().commit()
    if cur.rowcount:
        flash("Ticket cancelado correctamente.", "success")
    else:
        flash("No fue posible cancelar (ya fue gestionado o no existe).", "warning")
    return redirect(url_for("home"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        user = db().execute(
            "SELECT * FROM users WHERE username = ? AND password = ?", (username, password)
        ).fetchone()
        if user:
            session["user_id"] = user["id"]
            session["user_full_name"] = user["full_name"]
            flash("Sesión iniciada.", "success")
            return redirect(url_for("dashboard_pending"))
        flash("Credenciales inválidas.", "danger")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("Sesión cerrada.", "info")
    return redirect(url_for("home"))




def get_pending_payload() -> dict[str, Any]:
    pending = db().execute(
        """
        SELECT t.*, u.full_name AS assigned_to_name
        FROM tickets t
        LEFT JOIN users u ON u.id = t.assigned_to_user_id
        WHERE t.status = 'pendiente'
        ORDER BY t.created_at ASC
        """
    ).fetchall()
    unresolved_count = db().execute(
        "SELECT COUNT(*) AS c FROM tickets WHERE status = 'pendiente'"
    ).fetchone()["c"]
    users = db().execute("SELECT id, full_name FROM users ORDER BY full_name ASC").fetchall()
    return {
        "unresolved_count": unresolved_count,
        "tickets": [dict(row) for row in pending],
        "users": [dict(row) for row in users],
    }


@app.route("/admin/pending")
@login_required
def dashboard_pending():
    payload = get_pending_payload()
    return render_template(
        "dashboard_pending.html",
        initial_payload=payload,
    )


@app.route("/admin/pending/data")
@login_required
def dashboard_pending_data():
    return jsonify(get_pending_payload())




@app.route("/admin/pending/stream")
@login_required
def dashboard_pending_stream():
    @stream_with_context
    def event_stream():
        last_payload = None
        while True:
            payload = get_pending_payload()
            encoded = json.dumps(payload, ensure_ascii=False)
            if encoded != last_payload:
                yield f"data: {encoded}\n\n"
                last_payload = encoded
            else:
                yield ": keep-alive\n\n"
            time.sleep(2)

    return Response(event_stream(), mimetype="text/event-stream", headers={"Cache-Control": "no-cache"})


@app.route("/admin/resolved")
@login_required
def dashboard_resolved():
    resolved = db().execute(
        """
        SELECT t.*, c.full_name AS closed_by_name, a.full_name AS assigned_to_name
        FROM tickets t
        LEFT JOIN users c ON c.id = t.closed_by_user_id
        LEFT JOIN users a ON a.id = t.assigned_to_user_id
        WHERE t.status IN ('resuelto', 'cancelado')
        ORDER BY t.closed_at DESC
        """
    ).fetchall()
    return render_template("dashboard_resolved.html", tickets=resolved)


@app.route("/admin/assign/<int:ticket_id>", methods=["POST"])
@login_required
def assign_ticket(ticket_id: int):
    assigned_to = request.form.get("assigned_to", type=int)
    if not assigned_to:
        flash("Selecciona un usuario para asignar.", "warning")
        return redirect(url_for("dashboard_pending"))
    db().execute(
        "UPDATE tickets SET assigned_to_user_id = ? WHERE id = ? AND status = 'pendiente'",
        (assigned_to, ticket_id),
    )
    db().commit()
    flash("Ticket asignado.", "success")
    return redirect(url_for("dashboard_pending"))


@app.route("/admin/close/<int:ticket_id>", methods=["POST"])
@login_required
def close_ticket(ticket_id: int):
    status = request.form.get("status")
    if status not in {"resuelto", "cancelado"}:
        flash("Estado inválido.", "danger")
        return redirect(url_for("dashboard_pending"))

    db().execute(
        """
        UPDATE tickets
        SET status = ?, closed_by_user_id = ?, closed_at = ?, close_note = ?
        WHERE id = ? AND status = 'pendiente'
        """,
        (
            status,
            session["user_id"],
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            f"Cierre por {session['user_full_name']}",
            ticket_id,
        ),
    )
    db().commit()
    flash("Ticket cerrado.", "success")
    return redirect(url_for("dashboard_pending"))


if __name__ == "__main__":
    init_db()
    app.run(debug=True, host="0.0.0.0", port=5000)
