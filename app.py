"""
app.py
------
The main file. It creates the Flask app and defines the "routes"
(the web addresses) of TaskFlow:

    /                    -> dashboard (list, filter, search, statistics)
    /tasks/new           -> form to add a task
    /tasks/<id>/edit     -> form to edit a task
    /tasks/<id>/toggle   -> mark completed / pending   (POST)
    /tasks/<id>/delete   -> delete a task              (POST)

Run it with:  python app.py
"""

from datetime import datetime

from flask import Flask, abort, flash, redirect, render_template, request, url_for

from database import DEFAULT_DB_PATH, DatabaseError, init_db
from models import PRIORITIES, TaskRepository

app = Flask(__name__)
# The secret key is needed by Flask to show "flash" messages.
# For a real, public website you would load this from an environment variable.
app.config["SECRET_KEY"] = "change-this-secret-key-before-deploying"
app.config["DATABASE"] = DEFAULT_DB_PATH

VALID_FILTERS = ("all", "pending", "completed")

# Create the tasks table when the app is loaded, so it also works with
# "flask run" and not only with "python app.py".
init_db(app.config["DATABASE"])


# ------------------------------------------------------------------
# Helper functions
# ------------------------------------------------------------------
def get_repository():
    """Return a TaskRepository connected to the configured database."""
    return TaskRepository(app.config["DATABASE"])


def validate_task_form(form):
    """Check the data sent from the add/edit form.

    Returns a tuple: (clean_data, errors)
      * clean_data - dictionary with the cleaned values
      * errors     - list of messages to show the user (empty if all is fine)
    """
    title = form.get("title", "").strip()
    description = form.get("description", "").strip()
    priority = form.get("priority", "Medium")
    due_date = form.get("due_date", "").strip()
    errors = []

    if not title:
        errors.append("Please enter a task title.")
    elif len(title) > 100:
        errors.append("The title must be 100 characters or fewer.")

    if len(description) > 500:
        errors.append("The description must be 500 characters or fewer.")

    if priority not in PRIORITIES:
        errors.append("Please choose High, Medium or Low priority.")

    if due_date:
        try:
            datetime.strptime(due_date, "%Y-%m-%d")
        except ValueError:
            errors.append("The due date is not valid.")

    data = {"title": title, "description": description, "priority": priority, "due_date": due_date}
    return data, errors


# ------------------------------------------------------------------
# Routes
# ------------------------------------------------------------------
@app.route("/")
def index():
    """Dashboard: shows statistics and the (filtered / searched) task list."""
    status = request.args.get("filter", "all")
    if status not in VALID_FILTERS:
        status = "all"
    search = request.args.get("q", "").strip()

    try:
        repo = get_repository()
        tasks = repo.get_all(status=status, search=search)
        stats = repo.get_stats()
    except DatabaseError as error:
        flash(str(error), "error")
        tasks, stats = [], {"total": 0, "completed": 0, "pending": 0, "overdue": 0}

    percent_done = round(stats["completed"] * 100 / stats["total"]) if stats["total"] else 0
    return render_template(
        "index.html",
        tasks=tasks,
        stats=stats,
        percent_done=percent_done,
        status=status,
        search=search,
    )


@app.route("/tasks/new", methods=["GET", "POST"])
def add_task():
    """Show the 'add task' form (GET) and save the new task (POST)."""
    form_data = {"title": "", "description": "", "priority": "Medium", "due_date": ""}

    if request.method == "POST":
        form_data, errors = validate_task_form(request.form)
        if errors:
            for message in errors:
                flash(message, "error")
        else:
            try:
                get_repository().create(**form_data)
                flash("Task added.", "success")
                return redirect(url_for("index"))
            except DatabaseError as error:
                flash(str(error), "error")

    return render_template("task_form.html", task=None, form=form_data, priorities=PRIORITIES)


@app.route("/tasks/<int:task_id>/edit", methods=["GET", "POST"])
def edit_task(task_id):
    """Show the 'edit task' form (GET) and save the changes (POST)."""
    try:
        task = get_repository().get_by_id(task_id)
    except DatabaseError as error:
        flash(str(error), "error")
        return redirect(url_for("index"))
    if task is None:
        abort(404)

    form_data = {
        "title": task.title,
        "description": task.description,
        "priority": task.priority,
        "due_date": task.due_date_iso,
    }

    if request.method == "POST":
        form_data, errors = validate_task_form(request.form)
        if errors:
            for message in errors:
                flash(message, "error")
        else:
            try:
                get_repository().update(task_id, **form_data)
                flash("Changes saved.", "success")
                return redirect(url_for("index"))
            except DatabaseError as error:
                flash(str(error), "error")

    return render_template("task_form.html", task=task, form=form_data, priorities=PRIORITIES)


@app.route("/tasks/<int:task_id>/toggle", methods=["POST"])
def toggle_task(task_id):
    """Switch a task between pending and completed."""
    try:
        if not get_repository().toggle_status(task_id):
            abort(404)
    except DatabaseError as error:
        flash(str(error), "error")
    return redirect(request.referrer or url_for("index"))


@app.route("/tasks/<int:task_id>/delete", methods=["POST"])
def delete_task(task_id):
    """Delete a task."""
    try:
        if get_repository().delete(task_id):
            flash("Task deleted.", "success")
        else:
            abort(404)
    except DatabaseError as error:
        flash(str(error), "error")
    return redirect(request.referrer or url_for("index"))


@app.errorhandler(404)
def page_not_found(error):
    """Friendly page for addresses that do not exist."""
    return render_template("404.html"), 404


# ------------------------------------------------------------------
# Start the app
# ------------------------------------------------------------------
if __name__ == "__main__":
    app.run(debug=True)
