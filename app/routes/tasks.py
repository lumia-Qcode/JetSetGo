from flask import Blueprint, render_template, url_for, flash, request, session, redirect
from datetime import datetime, date
from app.models import Task, Notification, User, db

tasks_bp = Blueprint('tasks', __name__)

# =====================================================================
# VIEW TASKS
# =====================================================================
@tasks_bp.route("/")
def view_tasks():
    if 'user_id' not in session:
        flash("Please log in to view your tasks", "danger")
        return redirect(url_for('auth.login'))

    user_id = session['user_id']
    tasks = Task.query.filter_by(user_id=user_id).all()

    return render_template('tasks.html', tasks=tasks)


# =====================================================================
# ADD TASK + ASSIGN TO USER + NOTIFICATIONS
# =====================================================================
@tasks_bp.route('/add', methods=["POST"])
def add_task():
    if 'user_id' not in session:
        return redirect(url_for("auth.login"))

    title = request.form.get("title")
    due_date_str = request.form.get("due_date")
    due_time_str = request.form.get("due_time")
    assigned_username = request.form.get("assigned_to")
    due_today_notified = False
    overdue_notified = False

    due_date = datetime.strptime(due_date_str, "%Y-%m-%d").date() if due_date_str else None
    due_time = datetime.strptime(due_time_str, "%H:%M").time() if due_time_str else None

    creator_id = session["user_id"]
    assigned_user = None

    if assigned_username:
        assigned_user = User.query.filter_by(username=assigned_username).first()

    # Task owner
    task_owner_id = assigned_user.id if assigned_user else creator_id

    if title:
        task = Task.create(
            title=title,
            user_id=task_owner_id,
            due_date=due_date,
            due_time=due_time,
            due_today_notified=due_today_notified,
            overdue_notified=overdue_notified
        )

        # Notify task owner
        Notification.send(
            receiver_id=task_owner_id,
            sender_id=creator_id,
            type="task_created",
            message=f"New task '{title}' assigned to you. Due on {due_date}."
        )

        # Notify creator if assigned to another user
        if assigned_user:
            Notification.send(
                receiver_id=creator_id,
                sender_id=None,
                type="task_assigned",
                message=f"You assigned task '{title}' to {assigned_username}."
            )

        flash("Task added successfully!", "success")

    return redirect(url_for("tasks.view_tasks"))


# =====================================================================
# EDIT TASK + NOTIFICATION
# =====================================================================
@tasks_bp.route('/edit/<int:task_id>', methods=["GET", "POST"])
def edit_task(task_id):
    task = Task.query.get(task_id)

    if request.method == "POST":
        if task and task.user_id == session["user_id"]:
            title = request.form.get("title")
            due_date_str = request.form.get("due_date")
            due_time_str = request.form.get("due_time")

            due_date = datetime.strptime(due_date_str, "%Y-%m-%d").date() if due_date_str else None
            due_time = datetime.strptime(due_time_str, "%H:%M").time() if due_time_str else None

            task.update(title=title, due_date=due_date, due_time=due_time)

            Notification.send(
                receiver_id=task.user_id,
                sender_id=None,
                type="task_updated",
                message=f"Task '{task.title}' was updated. New due date: {task.due_date}."
            )

            flash("Task updated!", "success")
            return redirect(url_for("tasks.view_tasks"))

    return render_template("edit_task.html", task=task)


# =====================================================================
# TOGGLE COMPLETION + NOTIFICATION + XP & BADGE SYSTEM
# =====================================================================
@tasks_bp.route('/toggle/<int:task_id>', methods=["POST"])
def toggle_status(task_id):
    task = Task.query.get(task_id)

    if task and task.user_id == session["user_id"]:
        task.toggle_status()

        if task.status == "Done":
            # Add XP and increment task count
            user = User.query.get(task.user_id)
            user_stats = user.ensure_stats()
            user_stats.increment_tasks()  # This adds XP and checks for badges
            
            Notification.send(
                receiver_id=task.user_id,
                sender_id=None,
                type="task_completed",
                message=f"You completed the task '{task.title}'. +10 XP earned!"
            )
        elif task.status == "Working":
            Notification.send(
                receiver_id=task.user_id,
                sender_id=None,
                type="task_marked_pending",
                message=f"Task '{task.title}' is in progress."
            )
        else:
            Notification.send(
                receiver_id=task.user_id,
                sender_id=None,
                type="task_marked_pending",
                message=f"Task '{task.title}' is pending."
            )

    return redirect(url_for("tasks.view_tasks"))


# =====================================================================
# DELETE TASK + NOTIFICATION
# =====================================================================
@tasks_bp.route("/delete_task/<int:task_id>", methods=["POST"])
def delete_task(task_id):
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    task = Task.query.get(task_id)

    if task and task.user_id == session["user_id"]:
        Notification.send(
            receiver_id=session["user_id"],
            sender_id=None,
            type="task_deleted",
            message=f"Task '{task.title}' was deleted."
        )

        task.delete()
        flash("Task deleted!", "info")
    else:
        flash("Unauthorized to delete this task", "danger")

    return redirect(url_for("tasks.view_tasks"))


# =====================================================================
# CLEAR ALL TASKS + NOTIFICATION
# =====================================================================
@tasks_bp.route("/clear", methods=["POST"])
def clear_tasks():
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    user_id = session["user_id"]
    Task.clear_user_tasks(user_id)

    Notification.send(
        receiver_id=user_id,
        sender_id=None,
        type="task_cleared",
        message="All your tasks were cleared."
    )

    flash("All tasks cleared!", "info")
    return redirect(url_for("tasks.view_tasks"))


# =====================================================================
# DAILY TASK NOTIFICATIONS (run via APScheduler)
# =====================================================================
def send_daily_task_notifications():
    today = date.today()
    
    tasks = Task.query.all()

    for task in tasks:
        if task.status == "Done":
            continue

        # Task due today
        if task.due_date == today and not task.due_today_notified:
            Notification.send(
                receiver_id=task.user_id,
                sender_id=None,
                type="task_due_today",
                message=f"Your task '{task.title}' is due today!"
            )
            task.due_today_notified = True
            db.session.commit()

        # Task overdue
        elif task.due_date and task.due_date < today and not task.overdue_notified:
            Notification.send(
                receiver_id=task.user_id,
                sender_id=None,
                type="task_overdue",
                message=f"Your task '{task.title}' is OVERDUE!"
            )
            task.overdue_notified = True
            db.session.commit()


# Optional: reset flags at midnight if you want overdue notifications repeated daily
def reset_task_notifications():
    Task.query.update({
        Task.due_today_notified: False,
        Task.overdue_notified: False
    })
    db.session.commit()