"""
tests/test_app.py
-----------------
Automatic tests for every major TaskFlow feature.
Uses Python's built-in `unittest` module, so nothing extra to install.

Run from the project folder with:   python -m unittest discover -s tests -v
Every test uses a temporary database, so your real tasks are never touched.
"""

import os
import sys
import tempfile
import unittest
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app  # noqa: E402
from database import DatabaseError, init_db  # noqa: E402
from models import TaskRepository  # noqa: E402


def days_from_today(days):
    return (date.today() + timedelta(days=days)).isoformat()


class TaskFlowTests(unittest.TestCase):
    def setUp(self):
        # A fresh, empty database for every single test.
        self.db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_file.close()
        app.config["DATABASE"] = self.db_file.name
        app.config["TESTING"] = True
        init_db(self.db_file.name)
        self.client = app.test_client()
        self.repo = TaskRepository(self.db_file.name)

    def tearDown(self):
        os.unlink(self.db_file.name)

    def add(self, title="Buy milk", description="", priority="Medium", due_date=""):
        return self.client.post(
            "/tasks/new",
            data={"title": title, "description": description, "priority": priority, "due_date": due_date},
            follow_redirects=True,
        )

    # 1. Add
    def test_add_task_with_title_and_description(self):
        response = self.add("Write report", "Quarterly numbers")
        self.assertIn(b"Task added.", response.data)
        task = self.repo.get_all()[0]
        self.assertEqual(task.title, "Write report")
        self.assertEqual(task.description, "Quarterly numbers")

    def test_add_task_requires_title(self):
        response = self.add(title="   ")
        self.assertIn(b"Please enter a task title.", response.data)
        self.assertEqual(len(self.repo.get_all()), 0)

    def test_invalid_priority_and_date_are_rejected(self):
        response = self.add("Bad", priority="Urgent", due_date="not-a-date")
        self.assertIn(b"choose High, Medium or Low", response.data)
        self.assertIn(b"due date is not valid", response.data)
        self.assertEqual(len(self.repo.get_all()), 0)

    def test_sql_injection_text_is_stored_safely(self):
        self.add("x'); DROP TABLE tasks;--")
        self.assertEqual(self.repo.get_all()[0].title, "x'); DROP TABLE tasks;--")

    # 2. Edit and delete
    def test_edit_task(self):
        self.add("Old title")
        task_id = self.repo.get_all()[0].id
        response = self.client.post(
            f"/tasks/{task_id}/edit",
            data={"title": "New title", "description": "d", "priority": "High", "due_date": days_from_today(3)},
            follow_redirects=True,
        )
        self.assertIn(b"Changes saved.", response.data)
        task = self.repo.get_by_id(task_id)
        self.assertEqual((task.title, task.priority), ("New title", "High"))
        self.assertEqual(task.due_date_iso, days_from_today(3))

    def test_edit_form_is_prefilled(self):
        self.add("Prefill me", "Some details", "Low")
        task_id = self.repo.get_all()[0].id
        html = self.client.get(f"/tasks/{task_id}/edit").data.decode()
        self.assertIn("Prefill me", html)
        self.assertIn("Some details", html)

    def test_delete_task(self):
        self.add("Delete me")
        task_id = self.repo.get_all()[0].id
        response = self.client.post(f"/tasks/{task_id}/delete", follow_redirects=True)
        self.assertIn(b"Task deleted.", response.data)
        self.assertEqual(len(self.repo.get_all()), 0)

    def test_unknown_task_gives_404(self):
        self.assertEqual(self.client.get("/tasks/999/edit").status_code, 404)
        self.assertEqual(self.client.post("/tasks/999/delete").status_code, 404)
        self.assertEqual(self.client.post("/tasks/999/toggle").status_code, 404)

    # 3. Completed / pending
    def test_toggle_completed_and_back(self):
        self.add("Toggle me")
        task_id = self.repo.get_all()[0].id
        self.client.post(f"/tasks/{task_id}/toggle")
        self.assertTrue(self.repo.get_by_id(task_id).completed)
        self.client.post(f"/tasks/{task_id}/toggle")
        self.assertFalse(self.repo.get_by_id(task_id).completed)

    # 4 + 5. Priority and due date
    def test_priority_and_due_date_saved(self):
        self.add("Planned", priority="High", due_date=days_from_today(5))
        task = self.repo.get_all()[0]
        self.assertEqual(task.priority, "High")
        self.assertEqual(task.due_date, date.today() + timedelta(days=5))

    def test_tasks_sorted_by_due_date_then_priority(self):
        self.add("Later", due_date=days_from_today(9))
        self.add("No date")
        self.add("Soon", due_date=days_from_today(1))
        titles = [t.title for t in self.repo.get_all()]
        self.assertEqual(titles, ["Soon", "Later", "No date"])

    # 6. Filter
    def test_filter_all_pending_completed(self):
        self.add("Open task")
        self.add("Finished task")
        finished_id = [t for t in self.repo.get_all() if t.title == "Finished task"][0].id
        self.client.post(f"/tasks/{finished_id}/toggle")

        everything = self.client.get("/?filter=all").data.decode()
        pending = self.client.get("/?filter=pending").data.decode()
        completed = self.client.get("/?filter=completed").data.decode()

        self.assertIn("Open task", everything)
        self.assertIn("Finished task", everything)
        self.assertIn("Open task", pending)
        self.assertNotIn("Finished task", pending)
        self.assertIn("Finished task", completed)
        self.assertNotIn("Open task", completed)

    def test_unknown_filter_falls_back_to_all(self):
        self.add("Visible")
        self.assertIn(b"Visible", self.client.get("/?filter=banana").data)

    # 7. Search
    def test_search_by_title_is_case_insensitive(self):
        self.add("Buy groceries")
        self.add("Call dentist")
        html = self.client.get("/?q=GROCER").data.decode()
        self.assertIn("Buy groceries", html)
        self.assertNotIn("Call dentist", html)

    def test_search_with_no_match_shows_message(self):
        self.add("Something")
        self.assertIn(b"No tasks match", self.client.get("/?q=zzz").data)

    def test_search_and_filter_work_together(self):
        self.add("Report A")
        self.add("Report B")
        done_id = [t for t in self.repo.get_all() if t.title == "Report B"][0].id
        self.client.post(f"/tasks/{done_id}/toggle")
        html = self.client.get("/?filter=completed&q=report").data.decode()
        self.assertIn("Report B", html)
        self.assertNotIn("Report A", html)

    # 8. Statistics
    def test_statistics_counts(self):
        for name in ("A", "B", "C"):
            self.add(name)
        first_id = self.repo.get_all()[0].id
        self.client.post(f"/tasks/{first_id}/toggle")
        stats = self.repo.get_stats()
        self.assertEqual((stats["total"], stats["completed"], stats["pending"]), (3, 1, 2))

    def test_statistics_on_empty_database(self):
        stats = self.repo.get_stats()
        self.assertEqual(stats, {"total": 0, "completed": 0, "pending": 0, "overdue": 0})
        self.assertEqual(self.client.get("/").status_code, 200)

    # 9. Overdue
    def test_overdue_task_is_highlighted(self):
        self.add("Late one", due_date=days_from_today(-2))
        task = self.repo.get_all()[0]
        self.assertTrue(task.is_overdue)
        self.assertEqual(task.due_label, "Overdue by 2 days")
        self.assertIn(b"is-overdue", self.client.get("/").data)
        self.assertEqual(self.repo.get_stats()["overdue"], 1)

    def test_completed_or_future_tasks_are_not_overdue(self):
        self.add("Past but done", due_date=days_from_today(-3))
        self.add("Future", due_date=days_from_today(4))
        self.add("Today", due_date=days_from_today(0))
        past_id = [t for t in self.repo.get_all() if t.title == "Past but done"][0].id
        self.client.post(f"/tasks/{past_id}/toggle")
        self.assertFalse(any(t.is_overdue for t in self.repo.get_all()))
        self.assertNotIn(b"is-overdue", self.client.get("/").data)

    def test_due_labels(self):
        self.add("Today", due_date=days_from_today(0))
        self.add("Tomorrow", due_date=days_from_today(1))
        self.add("None")
        labels = {t.title: t.due_label for t in self.repo.get_all()}
        self.assertEqual(labels["Today"], "Due today")
        self.assertEqual(labels["Tomorrow"], "Due tomorrow")
        self.assertEqual(labels["None"], "No due date")

    # 10. Permanent storage
    def test_tasks_persist_in_database_file(self):
        self.add("Remember me")
        brand_new_repo = TaskRepository(self.db_file.name)  # simulates restarting the app
        self.assertEqual(brand_new_repo.get_all()[0].title, "Remember me")

    # Exception handling
    def test_database_error_is_handled(self):
        app.config["DATABASE"] = "/this/folder/does/not/exist/tasks.db"
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Could not", response.data)
        with self.assertRaises(DatabaseError):
            TaskRepository("/this/folder/does/not/exist/tasks.db").get_all()

    # Pages
    def test_pages_load(self):
        self.assertEqual(self.client.get("/").status_code, 200)
        self.assertEqual(self.client.get("/tasks/new").status_code, 200)
        self.assertEqual(self.client.get("/nope").status_code, 404)

    def test_html_in_titles_is_escaped(self):
        self.add("<script>alert(1)</script>")
        html = self.client.get("/").data.decode()
        self.assertNotIn("<script>alert(1)</script>", html)
        self.assertIn("&lt;script&gt;", html)


if __name__ == "__main__":
    unittest.main()
