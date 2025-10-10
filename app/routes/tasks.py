from flask import Blueprint, render_template, url_for, flash, request, session, redirect
from app import db
from datetime import datetime
from app.models import Task

tasks_bp = Blueprint('tasks', __name__)

#==========================================================================================================
@tasks_bp.route("/")
def view_tasks():
    if 'user_id' not in session or 'user_email' not in session:     # If user not logged in, redirect to login
        return redirect(url_for('auth.login'))

    user_id = session['user_id']        # Get user_id from session
    tasks = Task.query.filter_by(user_id = user_id).all()   # Filter queries of tasks for the logged-in user
    return render_template('tasks.html', tasks = tasks)     # Render tasks.html template with user's tasks

#==========================================================================================================

@tasks_bp.route('/add', methods = ["POST"])
def add_task():
    if 'user_id' not in session or 'user_email' not in session:     # If user not logged in, redirect to login
        return redirect(url_for('auth.login'))
    
    # Retrieve form data
    title = request.form.get('title')
    user_id = session['user_id']
    due_date_str = request.form.get('due_date')
    due_time_str = request.form.get('due_time')
    
    # Convert date and time strings (STR) to appropriate formats (DATE and TIME)
    due_date = datetime.strptime(due_date_str, '%Y-%m-%d').date() if due_date_str else None
    due_time = datetime.strptime(due_time_str, '%H:%M').time() if due_time_str else None

    if title:   # If a title is provided, create and save the task
        Task.create(title=title, user_id= user_id, due_date = due_date, due_time = due_time)
        flash('Task added successfully', 'success')
    
    # Redirect back to the tasks view after adding the task
    return redirect(url_for("tasks.view_tasks"))

#==========================================================================================================

@tasks_bp.route('/toggle/<int:task_id>', methods = ["POST"])
def toggle_status(task_id):     # Toggle task completion status, called when user clicks the toggle button
    task = Task.query.get(task_id)      # Get task by ID
    if task and task.user_id == session['user_id']:    # If task exists and belongs to the logged-in user, toggle its status
        task.toggle_status()
    return redirect(url_for('tasks.view_tasks'))

#==========================================================================================================

@tasks_bp.route("/clear", methods = ['POST'])
def clear_tasks():      # Clear all tasks for the logged-in user
    if 'user_id' not in session or 'user_email' not in session:    # If user not logged in, redirect to login
        return redirect(url_for('auth.login'))
    
    user_id = session['user_id']    # Get user_id from session
    Task.clear_user_tasks(user_id)  # Call class method to clear tasks for the user
    flash('All tasks cleared!', 'info')
    return redirect(url_for('tasks.view_tasks'))    # Redirect back to tasks view

#==========================================================================================================

@tasks_bp.route("/delete_task/<int:task_id>", methods = ['POST'])
def delete_task(task_id):
    if 'user_id' not in session or 'user_email' not in session:    # If user not logged in, redirect to login
        return redirect(url_for('auth.login'))
    
    task = Task.query.get(task_id)    # Get task by ID
    if task and task.user_id == session['user_id']:   # If task exists and belongs to the logged-in user, delete it
        task.delete()   # Call instance method to delete the task
        flash('Task deleted successfully!', 'info')
    else:
        flash('You are not authorized to delete this task', 'danger')   # Unauthorized attempt to delete task

    return redirect(url_for('tasks.view_tasks'))    # Redirect back to tasks view