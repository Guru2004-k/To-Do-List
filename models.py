"""
models.py
---------
Two classes live here (this is the "OOP" part of the project):

* Task            - represents ONE task and knows things about itself
                    (is it overdue? how should its due date be shown?).
* TaskRepository  - talks to the database. It contains the CRUD methods:
                    Create, Read, Update, Delete.
"""

import sqlite3
from datetime import date, datetime

from database import DEFAULT_DB_PATH, DatabaseError, get_connection

PRIORITIES = ("High", "Medium", "Low")


class Task:
    """A single to-do item."""

    def __init__(self, id, title, description, priority, due_date, completed, created_at):
        self.id = id
        self.title = title
        self.description = description
        self.priority = priority
        # Convert the stored text "2026-11-20" into a real date object (or None).
        self.due_date = self._parse_date(due_date)
        self.completed = bool(completed)
        self.created_at = created_at

    @classmethod
    def from_row(cls, row):
        """Build a Task from a database row."""
        return cls(
            id=row["id"],
            title=row["title"],
            description=row["description"],
            priority=row["priority"],
            due_date=row["due_date"],
            completed=row["completed"],
            created_at=row["created_at"],
        )

    @staticmethod
    def _parse_date(value):
        if not value:
            return None
        try:
            return datetime.strptime(value, "%Y-%m-%d").date()
        except ValueError:
            return None

    # ---- Small helper properties used by the HTML templates ----

    @property
    def is_overdue(self):
        """A task is overdue when it is still pending and its due date has passed."""
        return (not self.completed) and self.due_date is not None and self.due_date < date.today()

    @property
    def due_date_iso(self):
        """Date as YYYY-MM-DD (the format an HTML date input expects)."""
        return self.due_date.isoformat() if self.due_date else ""

    @property
    def due_label(self):
        """Human friendly text such as 'Due today' or 'Overdue by 3 days'."""
        if self.due_date is None:
            return "No due date"
        days_left = (self.due_date - date.today()).days
        if self.completed:
            return f"Was due {self.due_date.strftime('%d %b %Y')}"
        if days_left < 0:
            days = abs(days_left)
            return f"Overdue by {days} day{'s' if days != 1 else ''}"
        if days_left == 0:
            return "Due today"
        if days_left == 1:
            return "Due tomorrow"
        return f"Due {self.due_date.strftime('%d %b %Y')}"


class TaskRepository:
    """All database operations for tasks (CRUD)."""

    def __init__(self, db_path=DEFAULT_DB_PATH):
        self.db_path = db_path

    # ---------------- CREATE ----------------
    def create(self, title, description, priority, due_date):
        """Insert a new task and return its id."""
        sql = "INSERT INTO tasks (title, description, priority, due_date) VALUES (?, ?, ?, ?)"
        connection = get_connection(self.db_path)
        try:
            with connection:
                cursor = connection.execute(sql, (title, description, priority, due_date or None))
                return cursor.lastrowid
        except sqlite3.Error as error:
            raise DatabaseError(f"Could not add the task: {error}") from error
        finally:
            connection.close()

    # ---------------- READ ----------------
    def get_by_id(self, task_id):
        """Return one Task, or None if it does not exist."""
        connection = get_connection(self.db_path)
        try:
            row = connection.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
            return Task.from_row(row) if row else None
        except sqlite3.Error as error:
            raise DatabaseError(f"Could not load the task: {error}") from error
        finally:
            connection.close()

    def get_all(self, status="all", search=""):
        """Return a list of Tasks.

        status: "all", "pending" or "completed"
        search: only tasks whose title contains this text
        """
        sql = "SELECT * FROM tasks WHERE 1 = 1"
        params = []

        if status == "pending":
            sql += " AND completed = 0"
        elif status == "completed":
            sql += " AND completed = 1"

        if search:
            sql += " AND title LIKE ?"
            params.append(f"%{search}%")

        # Pending first, then earliest due date (no date last), then High > Medium > Low.
        sql += """
            ORDER BY completed ASC,
                     due_date IS NULL ASC,
                     due_date ASC,
                     CASE priority WHEN 'High' THEN 1 WHEN 'Medium' THEN 2 ELSE 3 END,
                     id DESC
        """
        connection = get_connection(self.db_path)
        try:
            rows = connection.execute(sql, params).fetchall()
            return [Task.from_row(row) for row in rows]
        except sqlite3.Error as error:
            raise DatabaseError(f"Could not load tasks: {error}") from error
        finally:
            connection.close()

    def get_stats(self):
        """Return counts for the dashboard: total, completed, pending, overdue."""
        today = date.today().isoformat()
        sql = """
            SELECT COUNT(*)                                                     AS total,
                   COALESCE(SUM(completed = 1), 0)                              AS completed,
                   COALESCE(SUM(completed = 0), 0)                              AS pending,
                   COALESCE(SUM(completed = 0 AND due_date < ?), 0)             AS overdue
            FROM tasks
        """
        connection = get_connection(self.db_path)
        try:
            row = connection.execute(sql, (today,)).fetchone()
            return {key: row[key] for key in ("total", "completed", "pending", "overdue")}
        except sqlite3.Error as error:
            raise DatabaseError(f"Could not calculate statistics: {error}") from error
        finally:
            connection.close()

    # ---------------- UPDATE ----------------
    def update(self, task_id, title, description, priority, due_date):
        """Change a task's details. Returns True if a task was updated."""
        sql = "UPDATE tasks SET title = ?, description = ?, priority = ?, due_date = ? WHERE id = ?"
        connection = get_connection(self.db_path)
        try:
            with connection:
                cursor = connection.execute(
                    sql, (title, description, priority, due_date or None, task_id)
                )
                return cursor.rowcount > 0
        except sqlite3.Error as error:
            raise DatabaseError(f"Could not update the task: {error}") from error
        finally:
            connection.close()

    def toggle_status(self, task_id):
        """Switch a task between pending and completed. Returns True if found."""
        sql = "UPDATE tasks SET completed = 1 - completed WHERE id = ?"
        connection = get_connection(self.db_path)
        try:
            with connection:
                cursor = connection.execute(sql, (task_id,))
                return cursor.rowcount > 0
        except sqlite3.Error as error:
            raise DatabaseError(f"Could not change the task status: {error}") from error
        finally:
            connection.close()

    # ---------------- DELETE ----------------
    def delete(self, task_id):
        """Remove a task for good. Returns True if a task was deleted."""
        connection = get_connection(self.db_path)
        try:
            with connection:
                cursor = connection.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
                return cursor.rowcount > 0
        except sqlite3.Error as error:
            raise DatabaseError(f"Could not delete the task: {error}") from error
        finally:
            connection.close()
