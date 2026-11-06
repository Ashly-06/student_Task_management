
import os
import re
import sqlite3
from datetime import date, datetime
from functools import wraps

from flask import (Flask, flash, g, redirect, render_template, request,
                   session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-change-me")
app.config["DATABASE"] = os.path.join(BASE_DIR, "database.db")

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
VALID_STATUS = ("Pending", "Completed")


def get_db():
    """One SQLite connection per request (stored on Flask's `g`)."""
    if "db" not in g:
        g.db = sqlite3.connect(app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row         
        g.db.execute("PRAGMA foreign_keys = ON")  
    return g.db


@app.teardown_appcontext
def close_db(exc=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    """Create tables if they do not exist."""
    db = sqlite3.connect(app.config["DATABASE"])
    db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            name     TEXT NOT NULL,
            email    TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS tasks (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL,
            task_title  TEXT NOT NULL,
            description TEXT,
            status      TEXT NOT NULL DEFAULT 'Pending'
                        CHECK (status IN ('Pending', 'Completed')),
            due_date    TEXT NOT NULL,
            created_at  TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        );
    """)
    db.commit()
    db.close()



def login_required(view):
    """Redirect to login if the user is not in the session."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to continue.", "warning")
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


def get_own_task(task_id):
    """Fetch a task ONLY if it belongs to the logged-in user (else None)."""
    return get_db().execute(
        "SELECT * FROM tasks WHERE id = ? AND user_id = ?",
        (task_id, session["user_id"]),
    ).fetchone()


def validate_task_form(form):
    """Return (cleaned_data, list_of_errors)."""
    title = form.get("task_title", "").strip()
    description = form.get("description", "").strip()
    status = form.get("status", "Pending").strip()
    due_date = form.get("due_date", "").strip()
    errors = []

    if not title:
        errors.append("Task title is required.")
    elif not 3 <= len(title) <= 100:
        errors.append("Task title must be 3-100 characters long.")
    if len(description) > 500:
        errors.append("Description must be at most 500 characters.")
    if status not in VALID_STATUS:
        errors.append("Status must be Pending or Completed.")
    if not due_date:
        errors.append("Due date is required.")
    else:
        try:
            datetime.strptime(due_date, "%Y-%m-%d")
        except ValueError:
            errors.append("Due date is not a valid date (use YYYY-MM-DD).")

    data = {"task_title": title, "description": description,
            "status": status, "due_date": due_date}
    return data, errors


@app.route("/")
def index():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/register", methods=["GET", "POST"])
def register():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")
        errors = []

        if not name or not email or not password or not confirm:
            errors.append("All fields are required.")
        else:
            if len(name) < 2:
                errors.append("Name must be at least 2 characters.")
            if not EMAIL_RE.match(email):
                errors.append("Please enter a valid email address.")
            if len(password) < 6 or not re.search(r"[A-Za-z]", password) \
                    or not re.search(r"\d", password):
                errors.append("Password must be at least 6 characters and "
                              "contain a letter and a number.")
            if password != confirm:
                errors.append("Passwords do not match.")

        db = get_db()
        if not errors and db.execute(
                "SELECT id FROM users WHERE email = ?", (email,)).fetchone():
            errors.append("An account with this email already exists.")

        if errors:
            for e in errors:
                flash(e, "danger")
            return render_template("register.html", name=name, email=email)

        db.execute("INSERT INTO users (name, email, password) VALUES (?, ?, ?)",
                   (name, email, generate_password_hash(password)))
        db.commit()
        flash("Registration successful! Please log in.", "success")
        return redirect(url_for("login"))
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        if not email or not password:
            flash("Email and password are required.", "danger")
            return render_template("login.html", email=email)

        user = get_db().execute(
            "SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if user is None or not check_password_hash(user["password"], password):
            flash("Invalid email or password.", "danger")
            return render_template("login.html", email=email)

        session.clear()
        session["user_id"] = user["id"]
        session["user_name"] = user["name"]
        flash(f"Welcome back, {user['name']}!", "success")
        return redirect(url_for("dashboard"))
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("login"))


@app.route("/dashboard")
@login_required
def dashboard():
    db = get_db()
    uid = session["user_id"]
    today = date.today().isoformat()

    def count(extra="", params=()):
        return db.execute(
            "SELECT COUNT(*) FROM tasks WHERE user_id = ? " + extra,
            (uid,) + params).fetchone()[0]

    stats = {
        "total": count(),
        "pending": count("AND status = 'Pending'"),
        "completed": count("AND status = 'Completed'"),
        "overdue": count("AND status = 'Pending' AND due_date < ?", (today,)),
    }

    flt = request.args.get("filter", "all")
    sql = "SELECT * FROM tasks WHERE user_id = ?"
    params = [uid]
    if flt == "pending":
        sql += " AND status = 'Pending'"
    elif flt == "completed":
        sql += " AND status = 'Completed'"
    elif flt == "overdue":
        sql += " AND status = 'Pending' AND due_date < ?"
        params.append(today)
    else:
        flt = "all"
    sql += " ORDER BY due_date ASC, id DESC"
    tasks = db.execute(sql, params).fetchall()
    return render_template("dashboard.html", tasks=tasks, stats=stats,
                           today=today, current_filter=flt)


@app.route("/tasks/add", methods=["GET", "POST"])
@login_required
def add_task():
    if request.method == "POST":
        data, errors = validate_task_form(request.form)
        if errors:
            for e in errors:
                flash(e, "danger")
            return render_template("add_task.html", task=data)
        db = get_db()
        db.execute(
            "INSERT INTO tasks (user_id, task_title, description, status, due_date) "
            "VALUES (?, ?, ?, ?, ?)",
            (session["user_id"], data["task_title"], data["description"],
             data["status"], data["due_date"]))
        db.commit()
        flash("Task added successfully.", "success")
        return redirect(url_for("dashboard"))
    return render_template("add_task.html", task={"status": "Pending"})


@app.route("/tasks/<int:task_id>/edit", methods=["GET", "POST"])
@login_required
def edit_task(task_id):
    task = get_own_task(task_id)
    if task is None:                      # missing OR belongs to someone else
        flash("Task not found.", "danger")
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        data, errors = validate_task_form(request.form)
        if errors:
            for e in errors:
                flash(e, "danger")
            data["id"] = task_id
            return render_template("edit_task.html", task=data)
        db = get_db()
        db.execute(
            "UPDATE tasks SET task_title = ?, description = ?, status = ?, "
            "due_date = ? WHERE id = ? AND user_id = ?",
            (data["task_title"], data["description"], data["status"],
             data["due_date"], task_id, session["user_id"]))
        db.commit()
        flash("Task updated successfully.", "success")
        return redirect(url_for("dashboard"))
    return render_template("edit_task.html", task=task)


@app.route("/tasks/<int:task_id>/delete", methods=["POST"])
@login_required
def delete_task(task_id):
    if get_own_task(task_id) is None:
        flash("Task not found.", "danger")
        return redirect(url_for("dashboard"))
    db = get_db()
    db.execute("DELETE FROM tasks WHERE id = ? AND user_id = ?",
               (task_id, session["user_id"]))
    db.commit()
    flash("Task deleted.", "info")
    return redirect(url_for("dashboard"))


@app.route("/tasks/<int:task_id>/status", methods=["POST"])
@login_required
def update_status(task_id):
    task = get_own_task(task_id)
    if task is None:
        flash("Task not found.", "danger")
        return redirect(url_for("dashboard"))
    new_status = "Completed" if task["status"] == "Pending" else "Pending"
    db = get_db()
    db.execute("UPDATE tasks SET status = ? WHERE id = ? AND user_id = ?",
               (new_status, task_id, session["user_id"]))
    db.commit()
    flash(f"Task marked as {new_status}.", "success")
    return redirect(request.referrer or url_for("dashboard"))

@app.errorhandler(404)
def not_found(e):
    return render_template("404.html"), 404


@app.errorhandler(500)
def server_error(e):
    return render_template("500.html"), 500


init_db()

if __name__ == "__main__":
    app.run(debug=True)
