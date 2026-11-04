"""
database.py
-----------
Everything that has to do with *connecting* to the SQLite database lives here.

SQLite is a tiny database stored in a single file (taskflow.db). Python
already includes the `sqlite3` module, so we don't need to install anything.
"""

import sqlite3
from pathlib import Path

# The database file is created next to this script.
DEFAULT_DB_PATH = Path(__file__).resolve().parent / "taskflow.db"


class DatabaseError(Exception):
    """Our own error type, raised when something goes wrong with the database.

    The web layer (app.py) catches this one error and shows a friendly message
    instead of crashing.
    """


def get_connection(db_path=DEFAULT_DB_PATH):
    """Open a connection to the SQLite database.

    `row_factory = sqlite3.Row` lets us read columns by name
    (row["title"]) instead of by position (row[1]).
    """
    try:
        connection = sqlite3.connect(db_path)
        connection.row_factory = sqlite3.Row
        return connection
    except sqlite3.Error as error:
        raise DatabaseError(f"Could not open the database: {error}") from error


def init_db(db_path=DEFAULT_DB_PATH):
    """Create the `tasks` table if it does not exist yet.

    It is safe to call this every time the app starts: "IF NOT EXISTS"
    means existing data is never touched.
    """
    create_table_sql = """
        CREATE TABLE IF NOT EXISTS tasks (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            title       TEXT    NOT NULL,
            description TEXT    NOT NULL DEFAULT '',
            priority    TEXT    NOT NULL DEFAULT 'Medium'
                        CHECK (priority IN ('High', 'Medium', 'Low')),
            due_date    TEXT,                       -- stored as YYYY-MM-DD
            completed   INTEGER NOT NULL DEFAULT 0, -- 0 = pending, 1 = completed
            created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
        )
    """
    connection = get_connection(db_path)
    try:
        with connection:  # commits automatically if no error happens
            connection.execute(create_table_sql)
    except sqlite3.Error as error:
        raise DatabaseError(f"Could not create the tasks table: {error}") from error
    finally:
        connection.close()
