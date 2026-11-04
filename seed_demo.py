"""
seed_demo.py  (optional)
------------------------
Fills the database with a few sample tasks so you can explore TaskFlow
straight away.   Run once with:   python seed_demo.py
"""

from datetime import date, timedelta

from database import DEFAULT_DB_PATH, init_db
from models import TaskRepository


def day(offset):
    """Return a date `offset` days from today as YYYY-MM-DD."""
    return (date.today() + timedelta(days=offset)).isoformat()


SAMPLE_TASKS = [
    # (title, description, priority, due date, mark as completed?)
    ("Submit project report", "Final version with charts, sent to the team lead.", "High", day(-2), False),
    ("Pay electricity bill", "Use the online portal before the late fee applies.", "High", day(0), False),
    ("Prepare presentation slides", "Ten slides: problem, approach, demo and results.", "High", day(2), False),
    ("Book dentist appointment", "Ask for a morning slot next week.", "Medium", day(5), False),
    ("Buy groceries", "Rice, vegetables, milk, fruit.", "Medium", day(1), False),
    ("Read a chapter of Python book", "Chapter on dictionaries and sets.", "Low", day(9), False),
    ("Clean up desktop files", "", "Low", "", False),
    ("Renew library membership", "", "Medium", day(-6), True),
    ("Practice Flask routes", "Built the first TaskFlow routes.", "Medium", day(-1), True),
]


def seed(db_path=DEFAULT_DB_PATH):
    init_db(db_path)
    repo = TaskRepository(db_path)
    for title, description, priority, due, done in SAMPLE_TASKS:
        task_id = repo.create(title, description, priority, due)
        if done:
            repo.toggle_status(task_id)
    return len(SAMPLE_TASKS)


if __name__ == "__main__":
    print(f"Added {seed()} sample tasks.")
