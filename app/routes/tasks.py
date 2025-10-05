from flask import Blueprint, render_template, url_for, flash, request, session, redirect
from app import db
from datetime import datetime
from app.models import Task

tasks_bp = Blueprint('tasks', __name__)

@tasks_bp.route("/")
def view_tasks():
    if 'user_id' not in session or 'user_email' not in session:
        return redirect(url_for('auth.login'))

    user_id = session['user_id']
    tasks = Task.query.filter_by(user_id = user_id).all()
    return render_template('tasks.html', tasks = tasks)

@tasks_bp.route('/add', methods = ["POST"])
def add_task():
    if 'user_id' not in session or 'user_email' not in session:
        return redirect(url_for('auth.login'))
    
    title = request.form.get('title')
    user_id = session['user_id']
    due_date_str = request.form.get('due_date')
    due_time_str = request.form.get('due_time')
    
    due_date = datetime.strptime(due_date_str, '%Y-%m-%d').date() if due_date_str else None
    due_time = datetime.strptime(due_time_str, '%H:%M').time() if due_time_str else None

    if title:
        # new_task = Task(title = title, user_id = user_id, due_date = due_date, due_time = due_time, status = 'Pending')
        # db.session.add(new_task)
        # db.session.commit()
        Task.create(title=title, user_id= user_id, due_date = due_date, due_time = due_time)
        flash('Task added successfully', 'success')
    return redirect(url_for("tasks.view_tasks"))

@tasks_bp.route('/toggle/<int:task_id>', methods = ["POST"])
def toggle_status(task_id):
    task = Task.query.get(task_id)
    if task:
        # if task.status == 'Pending':
        #     task.status = 'Working'
        # elif task.status == 'Working':
        #     task.status = 'Done'
        # else:
        #     task.status = 'Pending'
        # db.session.commit()
        task.toggle_status()
    return redirect(url_for('tasks.view_tasks'))

@tasks_bp.route("/clear", methods = ['POST'])
def clear_tasks():
    if 'user_id' not in session or 'user_email' not in session:
        return redirect(url_for('auth.login'))
    
    user_id = session['user_id']
    # Task.query.filter_by(user_id = user_id).delete()
    # db.session.commit()
    Task.clear_user_tasks(user_id)
    flash('All tasks cleared!', 'info')
    return redirect(url_for('tasks.view_tasks'))

@tasks_bp.route("/delete_task/<int:task_id>", methods = ['POST'])
def delete_task(task_id):
    if 'user_id' not in session or 'user_email' not in session:
        return redirect(url_for('auth.login'))
    
    task = Task.query.get(task_id)

    if task and task.user_id == session['user_id']:
        # db.session.delete(task)
        # db.session.commit()
        task.delete()
        flash('Task deleted successfully!', 'info')
    else:
        flash('You are not authorized to delete this task', 'danger')
    return redirect(url_for('tasks.view_tasks'))