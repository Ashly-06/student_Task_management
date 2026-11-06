# Student Task Management System

A beginner-friendly full-stack web app built with **Flask, SQLite, Jinja2 and Bootstrap 5**.
Students can register, log in and manage their own tasks (add, view, edit, delete, mark Pending/Completed, due dates).

## Features
- Registration, login, logout (Flask session authentication)
- Passwords hashed with Werkzeug (`generate_password_hash` / `check_password_hash`)
- Task CRUD + Pending/Completed toggle + due dates
- Dashboard: Total / Pending / Completed / Overdue counts, plus filter tabs
- Each user can only see and change their own tasks (every query filters on `user_id`)
- Validation + Flask flash messages, custom 404 and 500 pages, responsive Bootstrap UI

## Setup (Windows / macOS / Linux)
```bash
cd student-task-management
python -m venv venv
# Windows:      venv\Scripts\activate
# macOS/Linux:  source venv/bin/activate
pip install -r requirements.txt
python app.py
```
Open **http://127.0.0.1:5000** . `database.db` is created automatically on first run.

## Project structure
```
student-task-management/
├── app.py              # routes, validation, database code
├── test_app.py         # automated tests (python test_app.py)
├── requirements.txt
├── database.db         # auto-created
├── templates/          # base, login, register, dashboard, add_task, edit_task, 404, 500
└── static/css/style.css
```

## Routes
| URL | Method | Purpose |
|---|---|---|
| `/` | GET | Redirect to dashboard or login |
| `/register` | GET, POST | Create account |
| `/login` | GET, POST | Log in |
| `/logout` | GET | Log out |
| `/dashboard` | GET | Stats + task list (`?filter=all|pending|completed|overdue`) |
| `/tasks/add` | GET, POST | Add task |
| `/tasks/<id>/edit` | GET, POST | Edit task |
| `/tasks/<id>/delete` | POST | Delete task |
| `/tasks/<id>/status` | POST | Toggle Pending/Completed |

## Database
- `users(id, name, email UNIQUE, password)`
- `tasks(id, user_id -> users.id, task_title, description, status, due_date, created_at)`

## Security notes (for viva)
- Passwords are never stored in plain text (hashed + salted).
- All SQL uses `?` placeholders, which prevents SQL injection.
- Protected routes use a `@login_required` decorator that checks `session`.
- Authorization: `WHERE id = ? AND user_id = ?` means changing the ID in the URL returns "Task not found".
- Jinja2 auto-escapes output, which protects against XSS.
- For production you would also add CSRF tokens (e.g. Flask-WTF) and set `SECRET_KEY` via an environment variable.

## Testing checklist (manual)
| # | Test | Steps | Expected |
|---|---|---|---|
| 1 | Registration | Fill valid form on /register | Success flash, redirect to login |
| 2 | Duplicate registration | Register same email again | "account with this email already exists" |
| 3 | Empty fields | Submit register/login/add-task blank | Error flash messages |
| 4 | Invalid email / weak password | `abc`, password `abc` | Validation errors |
| 5 | Login | Correct credentials | Dashboard with welcome message |
| 6 | Invalid login | Wrong password | "Invalid email or password" |
| 7 | Add task | Title, due date, status | Appears in table, counts update |
| 8 | View task | Open dashboard | Title, description, status, due, created shown |
| 9 | Edit task | Edit → change title → Update | Changes saved |
| 10 | Change status | Click Mark Done / Mark Pending | Badge and counts change |
| 11 | Delete task | Delete → confirm | Task removed |
| 12 | Overdue | Add pending task with past date | Overdue badge, Overdue count +1 |
| 13 | Logout | Click Logout | Back to login |
| 14 | Unauthorized access | Logged out, open /dashboard | Redirect to login with warning |
| 15 | User isolation | User B opens `/tasks/<A's id>/edit` | "Task not found", redirected |
| 16 | 404 page | Open /random | Custom 404 page |

Automated: `python test_app.py` (7 tests covering the above).
No JSON API is implemented, so no Postman tests are needed; all forms are tested through the browser.

## Common errors and fixes
| Problem | Fix |
|---|---|
| `ModuleNotFoundError: No module named 'flask'` | Activate the venv, then `pip install -r requirements.txt` |
| `'python' is not recognized` | Use `py app.py` (Windows) or `python3 app.py` |
| `Address already in use` (port 5000) | Change last line of app.py to `app.run(debug=True, port=5001)` |
| `sqlite3.OperationalError: no such table` | Delete `database.db` and restart the app |
| Bootstrap looks unstyled | Bootstrap loads from a CDN, so check your internet connection |
| Logged out after restart | Set a fixed `SECRET_KEY` environment variable |
