import os
import secrets
import sqlite3

from flask import Flask, render_template, request, redirect, session, jsonify

app = Flask(__name__)

DATABASE_URL = (
    os.environ.get("DATABASE_URL")
    or os.environ.get("DATABASE_POSTGRES_URL")
)
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD")
app.secret_key = os.environ.get("SECRET_KEY") or secrets.token_hex(32)

if os.environ.get("VERCEL") == "1":
    missing_settings = [
        name for name, value in (
            ("DATABASE_URL", DATABASE_URL),
            ("SECRET_KEY", os.environ.get("SECRET_KEY")),
            ("ADMIN_USERNAME", ADMIN_USERNAME),
            ("ADMIN_PASSWORD", ADMIN_PASSWORD),
        )
        if not value
    ]
    if missing_settings:
        raise RuntimeError(
            "Missing required Vercel environment variables: "
            + ", ".join(missing_settings)
        )

DATABASE = os.environ.get(
    "DATABASE_PATH",
    os.path.join(app.root_path, "queue.db")
)
PLACEHOLDER = "%s" if DATABASE_URL else "?"


# ==============================
# DATABASE
# ==============================

def get_db():
    if DATABASE_URL:
        import psycopg
        from psycopg.rows import dict_row

        return psycopg.connect(DATABASE_URL, row_factory=dict_row)

    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    return connection


def create_database():
    connection = get_db()
    cursor = connection.cursor()
    token_id = (
        "BIGSERIAL PRIMARY KEY"
        if DATABASE_URL
        else "INTEGER PRIMARY KEY AUTOINCREMENT"
    )

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tokens (
            id %s,
            token TEXT NOT NULL,
            service TEXT DEFAULT 'General Service',
            priority INTEGER DEFAULT 0,
            status TEXT DEFAULT 'waiting',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            called_at TIMESTAMP
        )
    """ % token_id)

    connection.commit()
    connection.close()


def upgrade_database():

    connection = get_db()
    cursor = connection.cursor()

    if DATABASE_URL:
        cursor.execute("""
            SELECT column_name AS name
            FROM information_schema.columns
            WHERE table_schema = current_schema()
              AND table_name = 'tokens'
        """)
        columns = [row["name"] for row in cursor.fetchall()]
    else:
        cursor.execute("PRAGMA table_info(tokens)")
        columns = [row["name"] for row in cursor.fetchall()]

    column_definitions = {
        "service": "TEXT DEFAULT 'General Service'",
        "priority": "INTEGER DEFAULT 0",
        "status": "TEXT DEFAULT 'waiting'",
        "created_at": "TIMESTAMP",
        "called_at": "TIMESTAMP",
    }
    for name, definition in column_definitions.items():
        if name not in columns:
            add_if_missing = "IF NOT EXISTS " if DATABASE_URL else ""
            cursor.execute(
                f"ALTER TABLE tokens ADD COLUMN {add_if_missing}{name} {definition}"
            )

    connection.commit()
    connection.close()


# ==============================
# CUSTOMER HOME
# ==============================

@app.route("/", methods=["GET", "POST"])
def home():

    your_token = None

    if request.method == "POST":

        service = request.form.get("service")

        priority = request.form.get("priority")

        if not service:
            service = "General Service"

        priority_value = 1 if priority == "yes" else 0

        connection = get_db()
        cursor = connection.cursor()

        # Find last generated token
        cursor.execute("""
            SELECT token
            FROM tokens
            ORDER BY id DESC
            LIMIT 1
        """)

        result = cursor.fetchone()

        if result:

            try:
                last_number = int(
                    result["token"].split("-")[1]
                )

            except:
                last_number = 0

        else:
            last_number = 0

        token_number = last_number + 1

        your_token = f"A-{token_number:02d}"

        cursor.execute("""
            INSERT INTO tokens
            (token, service, priority, status, created_at)
            VALUES (%s, %s, %s, 'waiting', CURRENT_TIMESTAMP)
        """ % (PLACEHOLDER, PLACEHOLDER, PLACEHOLDER), (
            your_token,
            service,
            priority_value
        ))

        connection.commit()
        connection.close()

    return customer_dashboard(your_token)


# ==============================
# CUSTOMER DASHBOARD
# ==============================

def customer_dashboard(your_token=None):

    connection = get_db()
    cursor = connection.cursor()

    # Waiting queue
    cursor.execute("""
        SELECT *
        FROM tokens
        WHERE status = 'waiting'
        ORDER BY priority DESC, id ASC
    """)

    queue = cursor.fetchall()

    # Current serving token
    cursor.execute("""
        SELECT *
        FROM tokens
        WHERE status = 'serving'
        ORDER BY id DESC
        LIMIT 1
    """)

    current = cursor.fetchone()

    # Completed
    cursor.execute("""
        SELECT COUNT(*) AS total
        FROM tokens
        WHERE status = 'completed'
    """)

    completed = cursor.fetchone()["total"]

    # Skipped
    cursor.execute("""
        SELECT COUNT(*) AS total
        FROM tokens
        WHERE status = 'skipped'
    """)

    skipped = cursor.fetchone()["total"]

    # Total tokens
    cursor.execute("""
        SELECT COUNT(*) AS total
        FROM tokens
    """)

    total_tokens = cursor.fetchone()["total"]

    # Service statistics
    cursor.execute("""
        SELECT service, COUNT(*) AS total
        FROM tokens
        GROUP BY service
        ORDER BY total DESC
    """)

    service_stats = cursor.fetchall()

    connection.close()

    if current:

        current_token = current["token"]
        current_service = current["service"]

    else:

        current_token = "None"
        current_service = "No customer"

    return render_template(
        "index.html",
        your_token=your_token,
        queue=queue,
        people_waiting=len(queue),
        current_token=current_token,
        current_service=current_service,
        completed=completed,
        skipped=skipped,
        total_tokens=total_tokens,
        service_stats=service_stats
    )


# ==============================
# ADMIN LOGIN
# ==============================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":
        if not ADMIN_USERNAME or not ADMIN_PASSWORD:
            return render_template(
                "login.html",
                error="Admin login is not configured."
            ), 503

        username = request.form.get("username")
        password = request.form.get("password")

        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:

            session["admin_logged_in"] = True

            return redirect("/admin")

        else:

            return render_template(
                "login.html",
                error="Invalid username or password"
            )

    return render_template("login.html")


# ==============================
# ADMIN DASHBOARD
# ==============================

@app.route("/admin")
def admin():

    if not session.get("admin_logged_in"):

        return redirect("/login")

    connection = get_db()
    cursor = connection.cursor()

    # Waiting queue
    cursor.execute("""
        SELECT *
        FROM tokens
        WHERE status = 'waiting'
        ORDER BY priority DESC, id ASC
    """)

    queue = cursor.fetchall()

    # Current token
    cursor.execute("""
        SELECT *
        FROM tokens
        WHERE status = 'serving'
        ORDER BY id DESC
        LIMIT 1
    """)

    current = cursor.fetchone()

    # Total
    cursor.execute("""
        SELECT COUNT(*) AS total
        FROM tokens
    """)

    total_tokens = cursor.fetchone()["total"]

    # Waiting
    cursor.execute("""
        SELECT COUNT(*) AS total
        FROM tokens
        WHERE status = 'waiting'
    """)

    waiting = cursor.fetchone()["total"]

    # Completed
    cursor.execute("""
        SELECT COUNT(*) AS total
        FROM tokens
        WHERE status = 'completed'
    """)

    completed = cursor.fetchone()["total"]

    # Skipped
    cursor.execute("""
        SELECT COUNT(*) AS total
        FROM tokens
        WHERE status = 'skipped'
    """)

    skipped = cursor.fetchone()["total"]

    # Service statistics
    cursor.execute("""
        SELECT service, COUNT(*) AS total
        FROM tokens
        GROUP BY service
        ORDER BY total DESC
    """)

    service_stats = cursor.fetchall()

    connection.close()

    if current:

        current_token = current["token"]
        current_service = current["service"]

    else:

        current_token = "None"
        current_service = "No customer"

    return render_template(
        "admin.html",
        queue=queue,
        current_token=current_token,
        current_service=current_service,
        total_tokens=total_tokens,
        waiting=waiting,
        completed=completed,
        skipped=skipped,
        service_stats=service_stats
    )


# ==============================
# ADMIN CALL NEXT
# ==============================

@app.route("/admin/next")
def admin_next():

    if not session.get("admin_logged_in"):

        return redirect("/login")

    connection = get_db()
    cursor = connection.cursor()

    # Complete current token
    cursor.execute("""
        UPDATE tokens
        SET status = 'completed'
        WHERE status = 'serving'
    """)

    # Find next token
    cursor.execute("""
        SELECT id
        FROM tokens
        WHERE status = 'waiting'
        ORDER BY priority DESC, id ASC
        LIMIT 1
    """)

    result = cursor.fetchone()

    if result:

        cursor.execute("""
            UPDATE tokens
            SET status = 'serving',
                called_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """ % PLACEHOLDER, (result["id"],))

    connection.commit()
    connection.close()

    return redirect("/admin")


# ==============================
# ADMIN SKIP
# ==============================

@app.route("/admin/skip")
def admin_skip():

    if not session.get("admin_logged_in"):

        return redirect("/login")

    connection = get_db()
    cursor = connection.cursor()

    # Skip current token
    cursor.execute("""
        UPDATE tokens
        SET status = 'skipped'
        WHERE status = 'serving'
    """)

    # Call next token
    cursor.execute("""
        SELECT id
        FROM tokens
        WHERE status = 'waiting'
        ORDER BY priority DESC, id ASC
        LIMIT 1
    """)

    result = cursor.fetchone()

    if result:

        cursor.execute("""
            UPDATE tokens
            SET status = 'serving',
                called_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """ % PLACEHOLDER, (result["id"],))

    connection.commit()
    connection.close()

    return redirect("/admin")


# ==============================
# HISTORY
# ==============================

@app.route("/history")
def history():

    if not session.get("admin_logged_in"):

        return redirect("/login")

    connection = get_db()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT *
        FROM tokens
        WHERE status IN ('completed', 'skipped')
        ORDER BY id DESC
    """)

    history_data = cursor.fetchall()

    connection.close()

    return render_template(
        "history.html",
        history=history_data
    )


# ==============================
# RESET QUEUE
# ==============================

@app.route("/admin/reset")
def reset_queue():

    if not session.get("admin_logged_in"):

        return redirect("/login")

    connection = get_db()
    cursor = connection.cursor()

    cursor.execute("DELETE FROM tokens")

    connection.commit()
    connection.close()

    return redirect("/admin")


# ==============================
# VOICE DATA
# ==============================

@app.route("/current")
def current_token():

    connection = get_db()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT token, service
        FROM tokens
        WHERE status = 'serving'
        ORDER BY id DESC
        LIMIT 1
    """)

    result = cursor.fetchone()

    connection.close()

    if result:

        return jsonify({
            "token": result["token"],
            "service": result["service"]
        })

    return jsonify({
        "token": "None",
        "service": ""
    })


# ==============================
# LOGOUT
# ==============================

@app.route("/logout")
def logout():

    session.pop("admin_logged_in", None)

    return redirect("/login")


create_database()
upgrade_database()

if __name__ == "__main__":
    app.run(debug=False)