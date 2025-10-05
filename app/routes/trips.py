from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from app.models import db, Trip, ItineraryItem, Budget, Expense, User, TripShareNotification, NotificationService
from werkzeug.security import check_password_hash
from datetime import datetime

trips_bp = Blueprint("trips", __name__)

@trips_bp.route("/trips")
def view_trips():
    if "user_id" not in session:
        flash("Please log in to view your trips", "warning")
        return redirect(url_for("auth.login"))

    user_id = session["user_id"]
    trips = Trip.query.filter_by(user_id=user_id).all()
    return render_template("trips.html", trips=trips)


@trips_bp.route("/create_trip", methods=["GET", "POST"])
def create_trip():
    if "user_id" not in session:
        flash("Please log in to create a trip", "warning")
        return redirect(url_for("auth.login"))

    if request.method == "POST":
        title = request.form.get("title")
        destination = request.form.get("destination")
        start_date = request.form.get("start_date")
        end_date = request.form.get("end_date")
        description = request.form.get("description")

        if not title or not destination or not start_date or not end_date:
            flash("All required fields must be filled", "danger")
            return redirect(url_for("trips.create_trip"))
        
        start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
        end_date = datetime.strptime(end_date, "%Y-%m-%d").date()

        trip = Trip.create(
            title=title,
            destination=destination,
            start_date=start_date,
            end_date=end_date,
            description=description,
            user_id=session["user_id"]
        )

        flash(f"Trip '{trip.title}' created successfully!", "success")
        return redirect(url_for("trips.view_trips"))

    return render_template("create_trip.html")


@trips_bp.route("/trip/<int:trip_id>/edit", methods=["POST"])
def edit_trip(trip_id):
    trip = Trip.query.get_or_404(trip_id)

    title = request.form.get("title")
    destination = request.form.get("destination")
    start_date = request.form.get("start_date")
    end_date = request.form.get("end_date")
    description = request.form.get("description")

    trip.update_details(title=title, destination=destination,
                        start_date=start_date, end_date=end_date,
                        description=description)

    flash("Trip updated successfully!", "success")
    return redirect(url_for("trips.trip_detail", trip_id=trip.id))


@trips_bp.route("/trip/<int:trip_id>/share", methods=["POST"])
def share_trip(trip_id):
    trip = Trip.query.get_or_404(trip_id)
    user_id = session.get("user_id")
    if not user_id:
        flash("Please log in.", "warning")
        return redirect(url_for("auth.login"))

    username = request.form.get("username")
    friend = User.query.filter_by(username=username).first()
    if not friend:
        flash("User not found!", "danger")
        return redirect(url_for("trips.trip_detail", trip_id=trip.id))

    # ask friend for permission via notification
    notif = TripShareNotification(sender=User.query.get(user_id), receiver=friend, trip=trip)
    notif.send()
    flash(f"Share request sent to {username}", "info")

    return redirect(url_for("trips.trip_detail", trip_id=trip.id))


@trips_bp.route("/respond_trip_share/<int:trip_id>/<string:response>", methods=["POST"])
def respond_trip_share(trip_id, response):
    trip = Trip.query.get_or_404(trip_id)
    user = User.query.get(session["user_id"])

    if response == "accept":
        trip.share_with(user)
        flash(f"You now have access to trip '{trip.title}'.", "success")
    else:
        flash("You rejected the trip share request.", "info")

    return redirect(url_for("trips.view_trips"))


@trips_bp.route("/trip/<int:trip_id>/delete", methods=["POST"])
def delete_trip(trip_id):
    trip = Trip.query.get_or_404(trip_id)
    user = User.query.get(session["user_id"])

    #  user only removes their access
    trip.remove_participant(user)

    flash("You left this trip. (Trip remains for others)", "info")
    return redirect(url_for("trips.view_trips"))


@trips_bp.route("/trip/<int:trip_id>")
def trip_detail(trip_id):
    trip = Trip.query.get_or_404(trip_id)
    return render_template("trip_detail.html", trip=trip)

@trips_bp.route("/user/<int:user_id>/delete_trips", methods=["GET", "POST"])
def delete_user_trips(user_id):
    user = User.query.get_or_404(user_id)

    if request.method == "POST":
        password = request.form.get("password")

        # Verify password
        if not check_password_hash(user.password, password):
            flash("Incorrect password. Trips not deleted.", "danger")
            return redirect(url_for("trips.delete_user_trips", user_id=user_id))

        #user.delete_all_trips()
        Trip.delete_all_trips(user)
        flash("All trips deleted successfully!", "info")
        return redirect(url_for("trips.view_trips"))

    return render_template("confirm_delete.html", user=user)

@trips_bp.route("/trip/<int:trip_id>/add_itinerary", methods=["POST"])
def add_itinerary(trip_id):
    trip = Trip.query.get_or_404(trip_id)
    title = request.form.get("title")
    date = request.form.get("date")
    location = request.form.get("location")
    notes = request.form.get("notes")

    if not title or not date:
        flash("Itinerary item must have a title and date", "danger")
        return redirect(url_for("trips.trip_detail", trip_id=trip_id))
    
    date = datetime.strptime(date, "%Y-%m-%d").date()

    trip.add_itinerary_item(title, date, location, notes)

    flash("Itinerary item added!", "success")
    return redirect(url_for("trips.trip_detail", trip_id=trip_id))


@trips_bp.route("/itinerary/<int:item_id>/edit", methods=["POST"])
def edit_itinerary(item_id):
    item = ItineraryItem.query.get_or_404(item_id)

    title = request.form.get("title")
    date = request.form.get("date")
    location = request.form.get("location")
    notes = request.form.get("notes")

    item.update(title=title, date=date, location=location, notes=notes)
    flash("Itinerary item updated!", "success")

    return redirect(url_for("trips.trip_detail", trip_id=item.trip_id))


@trips_bp.route("/itinerary/<int:item_id>/delete", methods=["POST"])
def delete_itinerary(item_id):
    item = ItineraryItem.query.get_or_404(item_id)
    trip_id = item.trip_id

    item.delete()
    flash("Itinerary item deleted!", "info")

    return redirect(url_for("trips.trip_detail", trip_id=trip_id))


@trips_bp.route("/trip/<int:trip_id>/budget", methods=["GET", "POST"])
def trip_budget(trip_id):
    trip = Trip.query.get_or_404(trip_id)

    if not trip.budget:
        trip.init_budget()

    if request.method == "POST":
        amount = float(request.form.get("amount"))
        category = request.form.get("category")
        description = request.form.get("description")
        shared_with = request.form.get("shared_with")

        trip.add_expense(amount, category, description,
                         shared_with.split(",") if shared_with else None)

        flash("Expense added successfully!", "success")
        return redirect(url_for("trips.trip_budget", trip_id=trip_id))

    return render_template("budget.html", trip=trip)


@trips_bp.route("/expense/<int:expense_id>/edit", methods=["POST"])
def edit_expense(expense_id):
    expense = Expense.query.get_or_404(expense_id)

    amount = request.form.get("amount")
    description = request.form.get("description")
    shared_with = request.form.get("shared_with")

    expense.update_details(amount=amount, description=description, shared_with=shared_with)

    flash("Expense updated successfully!", "success")
    return redirect(url_for("trips.trip_budget", trip_id=expense.budget.trip_id))


@trips_bp.route("/expense/<int:expense_id>/delete", methods=["POST"])
def delete_expense(expense_id):
    expense = Expense.query.get_or_404(expense_id)
    trip_id = expense.budget.trip_id

    expense.delete_expense()

    flash("Expense deleted!", "info")
    return redirect(url_for("trips.trip_budget", trip_id=trip_id))


@trips_bp.route("/share_expense/<int:expense_id>", methods=["POST"])
def share_expense(expense_id):
    expense = Expense.query.get_or_404(expense_id)
    username = request.form.get("username")  # entered by User A

    userB = User.query.filter_by(username=username).first()
    if not userB:
        flash("User not found!", "danger")
        return redirect(url_for("trips.trip_detail", trip_id=expense.budget.trip_id))

    expense.split_with([username])   # OOP method

    flash(f"Share request sent to {username}", "info")
    return redirect(url_for("trips.trip_detail", trip_id=expense.budget.trip_id))


@trips_bp.route("/respond_share/<int:expense_id>/<string:response>", methods=["POST"])
def respond_share(expense_id, response):
    expense = Expense.query.get_or_404(expense_id)

    expense.update_status("Accepted" if response == "accept" else "Rejected")

    if response == "accept":
        flash(f"You accepted sharing {expense.description}", "success")
    else:
        flash(f"You rejected sharing {expense.description}", "danger")

    return redirect(url_for("trips.trip_detail", trip_id=expense.budget.trip_id))
