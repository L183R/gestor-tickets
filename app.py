from __future__ import annotations

import json
import os
import sqlite3
import time
from datetime import datetime
from functools import wraps
from typing import Any

from flask import Flask, Response, flash, g, jsonify, redirect, render_template, request, session, stream_with_context, url_for
from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "tickets.db")

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-change-me")

COMMON_PROBLEMS = [
    {
        "id": "conectividad",
        "title": "Conectividad",
        "description": "Fallas de red, cortes de internet, Wi‑Fi inestable o sin acceso a servicios internos.",
        "image": "/static/Imagenes/conexion.png",
    },
    {
        "id": "equipo-lentos",
        "title": "Equipo lentos",
        "description": "Computadores con bajo rendimiento, lentitud general o bloqueos frecuentes.",
        "image": "/static/Imagenes/lento.png",
    },
    {
        "id": "correo-electronico",
        "title": "Correo electrónico",
        "description": "Errores al enviar o recibir correos, problemas de sincronización o acceso al buzón.",
        "image": "/static/Imagenes/correo.png",
    },
    {
        "id": "inicio-sesion",
        "title": "Inicio de sesión",
        "description": "Dificultades para autenticarse, contraseñas inválidas o cuentas bloqueadas.",
        "image": "/static/Imagenes/sesion.png",
    },
    {
        "id": "impresora",
        "title": "Impresora",
        "description": "Documentos atascados en cola, fallas de conexión o errores durante la impresión.",
        "image": "/static/Imagenes/impresora.png",
    },
    {
        "id": "programas",
        "title": "Programas",
        "description": "Aplicaciones que no abren, se cierran solas o presentan mensajes de error.",
        "image": "/static/Imagenes/programas.png",
    },
    {
        "id": "acceso-recursos",
        "title": "Acceso a recursos",
        "description": "Sin permisos o acceso a carpetas compartidas, sistemas corporativos o herramientas internas.",
        "image": "/static/Imagenes/recursoscompartidos.png",
    },
    {
        "id": "otros",
        "title": "Otros",
        "description": "Incidentes no clasificados en categorías anteriores y solicitudes especiales de soporte.",
        "image": "/static/Imagenes/otros.png",
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
            assigned_at TEXT,
            canceled_by_requester INTEGER NOT NULL DEFAULT 0,
            closed_by_user_id INTEGER,
            closed_at TEXT,
            close_note TEXT,
            FOREIGN KEY (assigned_to_user_id) REFERENCES users(id),
            FOREIGN KEY (closed_by_user_id) REFERENCES users(id)
        );
        """
    )
    ticket_columns = {row["name"] for row in cur.execute("PRAGMA table_info(tickets)").fetchall()}
    if "assigned_at" not in ticket_columns:
        cur.execute("ALTER TABLE tickets ADD COLUMN assigned_at TEXT")

    cur.execute("SELECT COUNT(*) as total FROM users")
    if cur.fetchone()["total"] == 0:
        cur.execute(
            "INSERT INTO users (username, password, full_name) VALUES (?, ?, ?)",
            ("soporte", generate_password_hash("soporte123"), "Mesa de Ayuda"),
        )
        cur.execute(
            "INSERT INTO users (username, password, full_name) VALUES (?, ?, ?)",
            ("tecnico2", generate_password_hash("tecnico123"), "Técnico Secundario"),
        )
    else:
        # Migra instalaciones anteriores que guardaban contraseñas en texto plano.
        users = cur.execute("SELECT id, password FROM users").fetchall()
        for user in users:
            if not _is_password_hash(user["password"]):
                cur.execute(
                    "UPDATE users SET password = ? WHERE id = ?",
                    (generate_password_hash(user["password"]), user["id"]),
                )
    conn.commit()
    conn.close()


def _is_password_hash(value: str) -> bool:
    """Reconoce los formatos generados por Werkzeug sin validar la contraseña."""
    return value.startswith(("scrypt:", "pbkdf2:"))


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
        description = request.form.get("description", "").strip()

        if not all([requester_name, description]):
            flash("Completa todos los campos obligatorios.", "danger")
            return render_template(
                "create_ticket.html", problem=problem, local_ip=client_ip()
            )

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
                "",
                "",
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

    return render_template("create_ticket.html", problem=problem, local_ip=client_ip())


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
        user = db().execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        if user and check_password_hash(user["password"], password):
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




def get_pending_payload(local_ip: str | None = None) -> dict[str, Any]:
    conditions = ["t.status = 'pendiente'"]
    params: list[Any] = []
    if local_ip is not None:
        conditions.append("t.local_ip = ?")
        params.append(local_ip)

    where_clause = " AND ".join(conditions)
    pending = db().execute(
        f"""
        SELECT t.*, u.full_name AS assigned_to_name
        FROM tickets t
        LEFT JOIN users u ON u.id = t.assigned_to_user_id
        WHERE {where_clause}
        ORDER BY t.created_at ASC
        """,
        tuple(params),
    ).fetchall()
    unresolved_count = db().execute(
        f"SELECT COUNT(*) AS c FROM tickets t WHERE {where_clause}",
        tuple(params),
    ).fetchone()["c"]
    users = []
    if local_ip is None:
        users = db().execute("SELECT id, full_name FROM users ORDER BY full_name ASC").fetchall()
    return {
        "unresolved_count": unresolved_count,
        "tickets": [dict(row) for row in pending],
        "users": [dict(row) for row in users],
    }


@app.route("/admin/pending")
def dashboard_pending():
    is_authenticated = "user_id" in session
    payload = get_pending_payload(None if is_authenticated else client_ip())
    return render_template(
        "dashboard_pending.html",
        initial_payload=payload,
        is_authenticated=is_authenticated,
    )


@app.route("/admin/pending/data")
def dashboard_pending_data():
    local_ip = None if "user_id" in session else client_ip()
    return jsonify(get_pending_payload(local_ip))




@app.route("/admin/pending/stream")
def dashboard_pending_stream():
    local_ip = None if "user_id" in session else client_ip()

    @stream_with_context
    def event_stream():
        last_payload = None
        while True:
            payload = get_pending_payload(local_ip)
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
    assigned_to = request.args.get("assigned_to", type=int)
    problem_key = request.args.get("problem_key", "").strip()
    start_date = request.args.get("start_date", "").strip()
    end_date = request.args.get("end_date", "").strip()

    conditions = ["t.status IN ('resuelto', 'cancelado')"]
    params: list[Any] = []

    if assigned_to:
        conditions.append("t.assigned_to_user_id = ?")
        params.append(assigned_to)
    if problem_key:
        conditions.append("t.problem_key = ?")
        params.append(problem_key)
    if start_date:
        conditions.append("date(t.closed_at) >= date(?)")
        params.append(start_date)
    if end_date:
        conditions.append("date(t.closed_at) <= date(?)")
        params.append(end_date)

    where_clause = " AND ".join(conditions)
    resolved = db().execute(
        f"""
        SELECT t.*, c.full_name AS closed_by_name, a.full_name AS assigned_to_name
        FROM tickets t
        LEFT JOIN users c ON c.id = t.closed_by_user_id
        LEFT JOIN users a ON a.id = t.assigned_to_user_id
        WHERE {where_clause}
        ORDER BY t.closed_at DESC
        """,
        tuple(params),
    ).fetchall()

    metric_rows = []
    for row in resolved:
        ticket = dict(row)
        created_at = datetime.strptime(ticket["created_at"], "%Y-%m-%d %H:%M:%S")
        closed_at = datetime.strptime(ticket["closed_at"], "%Y-%m-%d %H:%M:%S")
        minutes_from_created = int((closed_at - created_at).total_seconds() // 60)

        minutes_from_assigned = None
        if ticket.get("assigned_at"):
            assigned_at_dt = datetime.strptime(ticket["assigned_at"], "%Y-%m-%d %H:%M:%S")
            minutes_from_assigned = int((closed_at - assigned_at_dt).total_seconds() // 60)

        ticket["minutes_from_created"] = minutes_from_created
        ticket["minutes_from_assigned"] = minutes_from_assigned
        metric_rows.append(ticket)

    summary: dict[str, dict[str, Any]] = {}
    for ticket in metric_rows:
        key = ticket["assigned_to_name"] or "Sin asignar"
        if key not in summary:
            summary[key] = {
                "count": 0,
                "sum_created": 0,
                "sum_assigned": 0,
                "count_assigned": 0,
            }
        summary[key]["count"] += 1
        summary[key]["sum_created"] += ticket["minutes_from_created"]
        if ticket["minutes_from_assigned"] is not None:
            summary[key]["sum_assigned"] += ticket["minutes_from_assigned"]
            summary[key]["count_assigned"] += 1

    summary_rows = []
    for assignee, values in summary.items():
        avg_created = round(values["sum_created"] / values["count"], 1) if values["count"] else 0
        avg_assigned = (
            round(values["sum_assigned"] / values["count_assigned"], 1)
            if values["count_assigned"]
            else None
        )
        summary_rows.append({
            "assignee": assignee,
            "count": values["count"],
            "avg_created": avg_created,
            "avg_assigned": avg_assigned,
        })

    users = db().execute("SELECT id, full_name FROM users ORDER BY full_name ASC").fetchall()
    problems = [{"id": p["id"], "title": p["title"]} for p in COMMON_PROBLEMS]

    return render_template(
        "dashboard_resolved.html",
        tickets=metric_rows,
        users=users,
        problems=problems,
        summary_rows=summary_rows,
        filters={
            "assigned_to": assigned_to,
            "problem_key": problem_key,
            "start_date": start_date,
            "end_date": end_date,
        },
    )


@app.route("/admin/assign/<int:ticket_id>", methods=["POST"])
@login_required
def assign_ticket(ticket_id: int):
    assigned_to = request.form.get("assigned_to", type=int)
    if not assigned_to:
        flash("Selecciona un usuario para asignar.", "warning")
        return redirect(url_for("dashboard_pending"))
    db().execute(
        """
        UPDATE tickets
        SET assigned_to_user_id = ?, assigned_at = COALESCE(assigned_at, ?)
        WHERE id = ? AND status = 'pendiente'
        """,
        (assigned_to, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), ticket_id),
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
