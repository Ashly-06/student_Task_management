"""Automated smoke tests. Run with:  python test_app.py"""
import os, tempfile, unittest
import app as app_module

class TaskAppTests(unittest.TestCase):
    def setUp(self):
        self.fd, self.path = tempfile.mkstemp(suffix=".db")
        app_module.app.config.update(DATABASE=self.path, TESTING=True)
        app_module.init_db()
        self.c = app_module.app.test_client()

    def tearDown(self):
        os.close(self.fd); os.remove(self.path)

    def register(self, c, email="a@test.com", pw="pass123", name="Alice"):
        return c.post("/register", data=dict(name=name, email=email,
                      password=pw, confirm_password=pw), follow_redirects=True)

    def login(self, c, email="a@test.com", pw="pass123"):
        return c.post("/login", data=dict(email=email, password=pw), follow_redirects=True)

    def add(self, c, title="Write report", due="2030-01-01"):
        return c.post("/tasks/add", data=dict(task_title=title, description="d",
                      status="Pending", due_date=due), follow_redirects=True)

    def test_register_login_logout(self):
        self.assertIn(b"Registration successful", self.register(self.c).data)
        self.assertIn(b"Welcome back", self.login(self.c).data)
        self.assertIn(b"logged out", self.c.get("/logout", follow_redirects=True).data)

    def test_validation_and_duplicates(self):
        self.assertIn(b"All fields are required", self.c.post("/register", data={}).data)
        self.assertIn(b"valid email", self.register(self.c, email="bad").data)
        self.assertIn(b"at least 6", self.register(self.c, pw="abc").data)
        self.register(self.c)
        self.assertIn(b"already exists", self.register(self.c).data)
        self.assertIn(b"Invalid email or password", self.login(self.c, pw="wrong999").data)

    def test_password_hashed(self):
        self.register(self.c)
        import sqlite3
        pw = sqlite3.connect(self.path).execute("select password from users").fetchone()[0]
        self.assertNotEqual(pw, "pass123"); self.assertTrue(pw.startswith(("scrypt", "pbkdf2")))

    def test_crud_and_status(self):
        self.register(self.c); self.login(self.c)
        self.assertIn(b"Task added", self.add(self.c).data)
        self.assertIn(b"Write report", self.c.get("/dashboard").data)
        r = self.c.post("/tasks/1/edit", data=dict(task_title="Renamed", description="",
                        status="Pending", due_date="2030-02-02"), follow_redirects=True)
        self.assertIn(b"Task updated", r.data)
        self.assertIn(b"marked as Completed", self.c.post("/tasks/1/status", follow_redirects=True).data)
        self.assertIn(b"Task deleted", self.c.post("/tasks/1/delete", follow_redirects=True).data)

    def test_bad_task_input_and_overdue(self):
        self.register(self.c); self.login(self.c)
        self.assertIn(b"3-100", self.add(self.c, title="ab").data)
        self.assertIn(b"not a valid date", self.add(self.c, due="31-12-2030").data)
        self.add(self.c, title="Old task", due="2000-01-01")
        self.assertIn(b"Overdue", self.c.get("/dashboard?filter=overdue").data)

    def test_unauthorized_and_isolation(self):
        self.assertEqual(self.c.get("/dashboard").status_code, 302)
        self.register(self.c); self.login(self.c); self.add(self.c)
        other = app_module.app.test_client()
        self.register(other, email="b@test.com", name="Bob"); self.login(other, email="b@test.com")
        self.assertNotIn(b"Write report", other.get("/dashboard").data)
        self.assertIn(b"Task not found", other.get("/tasks/1/edit", follow_redirects=True).data)
        other.post("/tasks/1/delete"); other.post("/tasks/1/status")
        self.assertIn(b"Write report", self.c.get("/dashboard").data)

    def test_404(self):
        self.assertEqual(self.c.get("/nope").status_code, 404)

if __name__ == "__main__":
    unittest.main()
