# app/system_notifications.py

from datetime import datetime, timedelta
from app import db
from app.models import Trip, Expense, User, Notification

# -----------------------------
# 1. Budget Overrun Alerts
# -----------------------------
def check_budget_alerts():
    """Send notifications if trips exceed their planned budget"""
    trips = Trip.query.all()
    for trip in trips:
        if not trip.budget:
            continue
        total_expenses = trip.budget.total_expenses()
        planned_total = trip.budget.total_planned()
        
        # Only notify if over budget
        if total_expenses > planned_total:
            for user in trip.participants:
                # Prevent duplicate notifications (optional: you can mark in DB)
                Notification.send(
                    receiver_id=user.id,
                    sender_id=None,  # system
                    type="budget_over",
                    message=f"Trip '{trip.title}' has exceeded the planned budget!",
                    trip_id=trip.id
                )

# -----------------------------
# 2. Upcoming Trip Reminders
# -----------------------------
def check_upcoming_trips():
    """Send notifications for trips starting tomorrow"""
    today = datetime.today().date()
    upcoming_trips = Trip.query.filter(Trip.start_date == today + timedelta(days=1)).all()
    
    for trip in upcoming_trips:
        for user in trip.participants:
            Notification.send(
                receiver_id=user.id,
                sender_id=None,
                type="trip_starting",
                message=f"Reminder: Trip '{trip.title}' starts tomorrow!",
                trip_id=trip.id
            )

# -----------------------------
# 3. Overdue Shared Expenses
# -----------------------------
def check_overdue_expenses():
    """Notify users about shared expenses that are overdue"""
    today = datetime.today().date()
    overdue_expenses = Expense.query.filter(Expense.due_date < today, Expense.is_settled == False).all()
    
    for expense in overdue_expenses:
        for user in expense.shared_users:
            Notification.send(
                receiver_id=user.id,
                sender_id=None,
                type="expense_overdue",
                message=f"Shared expense '{expense.description}' in trip '{expense.budget.trip.title}' is overdue!",
                trip_id=expense.budget.trip.id,
                expense_id=expense.id
            )

# -----------------------------
# 4. Trip Completed Notifications
# -----------------------------
def check_completed_trips():
    """Notify users 1 day after trip ends to leave reviews"""
    today = datetime.today().date()
    completed_trips = Trip.query.filter(Trip.end_date == today - timedelta(days=1)).all()
    
    for trip in completed_trips:
        for user in trip.participants:
            Notification.send(
                receiver_id=user.id,
                sender_id=None,
                type="trip_completed",
                message=f"Trip '{trip.title}' has ended. Please leave a review!",
                trip_id=trip.id
            )

# -----------------------------
# 5. Scheduler Integration
# -----------------------------
def start_system_notifications_scheduler(scheduler):
    """
    Pass in APScheduler instance and schedule the jobs.
    Example:
        from apscheduler.schedulers.background import BackgroundScheduler
        scheduler = BackgroundScheduler()
        start_system_notifications_scheduler(scheduler)
        scheduler.start()
    """
    # Run budget check every hour
    scheduler.add_job(check_budget_alerts, 'interval', hours=1)

    # Run upcoming trip reminders once a day
    scheduler.add_job(check_upcoming_trips, 'interval', hours=24)

    # Run overdue expense checks once a day
    scheduler.add_job(check_overdue_expenses, 'interval', hours=24)

    # Run trip completed notifications once a day
    scheduler.add_job(check_completed_trips, 'interval', hours=24)
