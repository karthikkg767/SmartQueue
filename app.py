from flask import Flask, render_template, request, redirect, session, jsonify
import sqlite3

app = Flask(__name__)

# Secret key is used for admin login session
app.secret_key = "smartqueue-secret-key-2026"

DATABASE = "queue.db"

# Admin credentials
ADMIN_USERNAME = "Karthik"
ADMIN_PASSWORD = "karthi@123"


# ==============================
# DATABASE
# ==============================

def get_db():
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    return connection


def create_database():

    connection = get_db()
    cursor = connection.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            token TEXT NOT NULL,
            service TEXT DEFAULT 'General Service',
            priority INTEGER DEFAULT 0,
            status TEXT DEFAULT 'waiting',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            called_at TIMESTAMP
        )
    """)

    connection.commit()
    connection.close()


def upgrade_database():

    connection = get_db()
    cursor = connection.cursor()

    cursor.execute("PRAGMA table_info(tokens)")

    columns = [row["name"] for row in cursor.fetchall()]

    if "service" not in columns:
        cursor.execute("""
            ALTER TABLE tokens
            ADD COLUMN service TEXT DEFAULT 'General Service'
        """)

    if "priority" not in columns:
        cursor.execute("""
            ALTER TABLE tokens
            ADD COLUMN priority INTEGER DEFAULT 0
        """)

    if "status" not in columns:
        cursor.execute("""
            ALTER TABLE tokens
            ADD COLUMN status TEXT DEFAULT 'waiting'
        """)

    if "created_at" not in columns:
        cursor.execute("""
            ALTER TABLE tokens
            ADD COLUMN created_at TIMESTAMP
        """)

    if "called_at" not in columns:
        cursor.execute("""
            ALTER TABLE tokens
            ADD COLUMN called_at TIMESTAMP
        """)

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
            VALUES (?, ?, ?, 'waiting', CURRENT_TIMESTAMP)
        """, (
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
            WHERE id = ?
        """, (result["id"],))

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
            WHERE id = ?
        """, (result["id"],))

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


# ==============================
# START APPLICATION
# ==============================

if __name__ == "__main__":

    create_database()

    upgrade_database()

    app.run(debug=True)