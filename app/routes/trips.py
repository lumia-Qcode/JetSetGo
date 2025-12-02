from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from app.models import Trip, ItineraryItem, Expense, User, PlannedBudget, FavoriteDestination, TripDestination, Review, ReviewPhoto, Notification, db
from werkzeug.security import check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime
import os

trips_bp = Blueprint("trips", __name__)

# Configure upload folder
UPLOAD_FOLDER = 'app/static/uploads/reviews'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

#==========================================================================================================
# TRIPS ROUTES
#==========================================================================================================

@trips_bp.route("/trips")
def view_trips():
    """View all trips for the logged-in user"""
    if "user_id" not in session:
        flash("Please log in to view your trips", "danger")
        return redirect(url_for("auth.login"))

    trips = Trip.query.all()
    return render_template("trips.html", trips=trips)

#==========================================================================================================

@trips_bp.route("/create_trip", methods=["GET", "POST"])
def create_trip():
    """Create a new trip"""
    if "user_id" not in session:
        flash("Please log in to create a trip", "danger")
        return redirect(url_for("auth.login"))

    if request.method == "POST":
        title = request.form.get("title")
        destinations = request.form.getlist("destinations")
        start_date = request.form.get("start_date")
        end_date = request.form.get("end_date")
        description = request.form.get("description")

        if not title or not destinations or not start_date or not end_date:
            flash("All required fields must be filled", "info")
            return redirect(url_for("trips.create_trip"))
        
        start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
        end_date = datetime.strptime(end_date, "%Y-%m-%d").date()
 
        user_id = session.get("user_id")
        participant = User.query.get(user_id)

        trip = Trip.create(
            title=title,
            destinations=destinations,
            start_date=start_date,
            end_date=end_date,
            description=description,
            participant=participant
        )

        flash(f"Trip '{trip.title}' created successfully!", "success")
        Notification.send(
            receiver_id=participant.id,
            sender_id=session.get("user_id"),
            type="trip_created",
            message=f"{session['user_name']} created a new trip: {title}",
            trip_id=trip.id
        )

        return redirect(url_for("trips.view_trips"))

    return render_template("create_trip.html")

#==========================================================================================================

@trips_bp.route("/trip/<int:trip_id>/edit", methods=["GET", "POST"])
def edit_trip(trip_id):
    """Edit an existing trip"""
    trip = Trip.query.get_or_404(trip_id)
    user_id = session.get("user_id")

    if user_id not in trip.get_participant_ids():
        flash("You do not have permission to edit this trip.", "danger")
        return redirect(url_for("trips.view_trips"))

    if request.method == "POST":
        title = request.form.get("title")
        destinations = request.form.getlist("destinations")
        start_date = request.form.get("start_date")
        end_date = request.form.get("end_date")
        description = request.form.get("description")

        start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
        end_date = datetime.strptime(end_date, "%Y-%m-%d").date()

        trip.update_details(
            title=title,
            destinations=destinations,
            start_date=start_date,
            end_date=end_date,
            description=description
        )

        flash("Trip updated successfully!", "success")
        for user in trip.participants:
            if user.id != session["user_id"]:
                Notification.send(
                    receiver_id=user.id,
                    sender_id=session["user_id"],
                    type="trip_updated",
                    message=f"Trip '{trip.title}' was updated. View to check the details",
                    trip_id=trip.id
                )

        return redirect(url_for("trips.view_trips", trip_id=trip.id))
    
    return render_template("edit_trip.html", trip=trip)

#==========================================================================================================

@trips_bp.route("/trip/<int:trip_id>/share", methods=["POST"])
def share_trip(trip_id):
    trip = Trip.query.get_or_404(trip_id)
    sender_id = session.get("user_id")

    if not sender_id:
        flash("Please log in first", "danger")
        return redirect(url_for("auth.login"))

    username = request.form.get("username")
    friend = User.query.filter_by(username=username).first()

    if not friend:
        flash("User not found!", "danger")
        return redirect(url_for("trips.trip_detail", trip_id=trip.id))

    # Prevent sending request to someone already in trip
    if friend.id in trip.get_participant_ids():
        flash(f"{username} is already part of this trip!", "info")
        return redirect(url_for("trips.trip_detail", trip_id=trip.id))

    
    Notification.send(
        receiver_id=friend.id,
        sender_id=sender_id,
        type="trip_request",
        message=f"{session['user_name']} invited you to join the trip '{trip.title}'.",
        trip_id=trip.id
    )

    flash(f"Invitation sent to {username}", "success")
    return redirect(url_for("trips.trip_detail", trip_id=trip.id))


#==========================================================================================================

@trips_bp.route("/respond_trip_share/<int:trip_id>/<string:response>", methods=["POST"])
def respond_trip_share(trip_id, response):
    trip = Trip.query.get_or_404(trip_id)
    user_id = session.get("user_id")

    if not user_id:
        return jsonify({"error": "Not logged in"}), 403

    user = User.query.get(user_id)

    # --- FIX: WE MUST GET notif_id FROM REQUEST BODY ---
    notif_id = request.json.get("notif_id")
    sender_id = request.json.get("sender_id")

    if not notif_id or not sender_id:
        return jsonify({"error": "Missing notification data"}), 400

    # get notif from db first
    notif = Notification.query.get(notif_id)
    if not notif:
        return jsonify({"error": "Notification not found"}), 404

    # original sender is stored on the notif
    original_sender_id = notif.sender_id

    # remove or mark read the notif
    db.session.delete(notif)
    db.session.commit()

    # ACCEPT
    if response == "accept":
        trip.share_with(user)
        Notification.send(
            receiver_id=original_sender_id,    # SERVER-SIDE SOURCE
            sender_id=user.id,
            type="trip_request_accepted",
            message=f"{user.username} accepted your request and joined trip '{trip.title}'.",
            trip_id=trip.id
        )
        return jsonify({"status": "accepted", "removed": notif_id})
    # DENY (same pattern)


    # DENY
    else:
        Notification.send(
            receiver_id=original_sender_id,
            sender_id=user.id,
            type="trip_request_denied",
            message=f"{user.username} rejected your trip invitation for '{trip.title}'.",
            trip_id=trip.id
        )

        return jsonify({"status": "denied", "removed": notif_id})


#==========================================================================================================

@trips_bp.route("/trip/<int:trip_id>/delete", methods=["POST"])
def delete_trip(trip_id):
    """Delete/leave a trip"""
    trip = Trip.query.get_or_404(trip_id)
    user_id = session.get('user_id')

    if not user_id:
        flash("You must be logged in to perform this action.", "info")
        return redirect(url_for("auth.login"))

    user = User.query.get(session["user_id"])
    trip.remove_participant(user)

    flash("You left this trip.", "success")
    for member in trip.participants:
        Notification.send(
            receiver_id=member.id,
            sender_id=user.id,
            type="trip_member_left",
            message=f"{user.username} left the trip '{trip.title}'.",
            trip_id=trip.id
        )

    return redirect(url_for("trips.view_trips"))

#==========================================================================================================

@trips_bp.route("/trip/<int:trip_id>")
def trip_detail(trip_id):
    """View detailed information about a trip"""
    trip = Trip.query.get_or_404(trip_id)
    user_id = session.get("user_id")
    user = User.query.get(user_id) if user_id else None
    
    return render_template("trip_detail.html", trip=trip, user=user)

#==========================================================================================================

@trips_bp.route("/user/<int:user_id>/delete_trips", methods=["GET", "POST"])
def delete_user_trips(user_id):
    """Delete all trips for a user"""
    user = User.query.get_or_404(user_id)
    user_id = session.get('user_id')

    if not user_id:
        flash("You must be logged in to perform this action.", "info")
        return redirect(url_for("auth.login"))

    if request.method == "POST":
        password = request.form.get("password")

        if not check_password_hash(user.password, password):
            flash("Incorrect password. Trips not deleted.", "danger")
            return redirect(url_for("trips.delete_user_trips", user_id=user_id))
        
        Trip.delete_all_trips(user)
        flash("All trips deleted successfully!", "info")
        return redirect(url_for("trips.view_trips"))

    return render_template("confirm_delete.html", user=user)

#==========================================================================================================
# ITINERARY ROUTES
#==========================================================================================================

@trips_bp.route("/trip/<int:trip_id>/add_itinerary", methods=["POST"])
def add_itinerary(trip_id):
    """Add an itinerary item to a trip"""
    trip = Trip.query.get_or_404(trip_id)
    user_id = session.get("user_id")

    if user_id not in trip.get_participant_ids():
        flash("You do not have permission to add itinerary items to this trip.", "danger")
        return redirect(url_for("trips.view_trips"))
    
    title = request.form.get("title")
    date = request.form.get("date")
    time = request.form.get("time")
    location = request.form.get("location")
    notes = request.form.get("notes")

    if not title or not date:
        flash("Itinerary item must have a title and date", "info")
        return redirect(url_for("trips.trip_detail", trip_id=trip_id))
    
    date = datetime.strptime(date, "%Y-%m-%d").date()
    time = datetime.strptime(time, "%H:%M").time() if time else None
    trip.add_itinerary_item(title, date, location, notes, time)

    flash("Itinerary item added!", "success")
    for user in trip.participants:
        if user.id != session["user_id"]:
            Notification.send(
                receiver_id=user.id,
                sender_id=session["user_id"],
                type="itinerary_add",
                message=f"New itinerary item added in '{trip.title}'.",
                trip_id=trip.id
            )


    return redirect(url_for("trips.trip_detail", trip_id=trip_id))

#==========================================================================================================

@trips_bp.route("/itinerary/<int:item_id>/edit", methods=["GET", "POST"])
def edit_itinerary(item_id):
    """Edit an itinerary item"""
    item = ItineraryItem.query.get_or_404(item_id)
    user_id = session.get("user_id")

    if user_id not in item.trip.get_participant_ids():
        flash("You do not have permission to edit this itinerary item.", "info")
        return redirect(url_for("trips.trip_detail", trip_id=item.trip_id))

    if request.method == 'POST':
        title = request.form.get("title")
        date = request.form.get("date")
        time = request.form.get("time")
        location = request.form.get("location")
        notes = request.form.get("notes")

        if date:
            date = datetime.strptime(date, "%Y-%m-%d").date()
        if time:
            time = time[:5]
            time = datetime.strptime(time, "%H:%M").time()

        item.update(title=title, date=date, location=location, notes=notes, time=time)
        flash("Itinerary item updated!", "success")
        for user in item.trip.participants:
            if user.id != session["user_id"]:
                Notification.send(
                    receiver_id=user.id,
                    sender_id=session["user_id"],
                    type="itinerary_updated",
                    message=f"An itinerary item was updated in '{item.trip.title}'.",
                    trip_id=item.trip.id
                )


        return redirect(url_for("trips.all_itineraries", trip_id=item.trip_id))
    
    trip = item.trip
    return render_template("edit_itinerary.html", item=item, trip=trip)

#==========================================================================================================

@trips_bp.route("/itinerary/<int:item_id>/delete", methods=["POST"])
def delete_itinerary(item_id):
    """Delete an itinerary item"""
    item = ItineraryItem.query.get_or_404(item_id)
    trip_id = item.trip_id
    user_id = session.get("user_id")

    if user_id not in item.trip.get_participant_ids():
        flash("You do not have permission to delete this itinerary item.", "danger")
        return redirect(url_for("trips.all_itineraries", trip_id=trip_id))

    item.delete()
    flash("Itinerary item deleted!", "success")
    for user in item.trip.participants:

            if user.id != session["user_id"]:
                Notification.send(
                    receiver_id=user.id,
                    sender_id=session["user_id"],
                    type="itinerary_deleted",
                    message=f"An itinerary item was removed from '{item.trip.title}'.",
                    trip_id=trip_id
                )
    return redirect(url_for("trips.all_itineraries", trip_id=trip_id))
#==========================================================================================================
@trips_bp.route('/trip/<int:trip_id>/itineraries')
def all_itineraries(trip_id):
    trip = Trip.query.get_or_404(trip_id)
    return render_template('all_itineraries.html', trip=trip)

#==========================================================================================================
# BUDGET ROUTES
#==========================================================================================================

@trips_bp.route("/trip/<int:trip_id>/budget", methods=["GET", "POST"])
def trip_budget(trip_id):
    """View and manage trip budget"""
    trip = Trip.query.get_or_404(trip_id)

    if not trip.budget:
        trip.init_budget()

    if request.method == "POST":
        amount = float(request.form.get("amount"))
        category = request.form.get("category")
        description = request.form.get("description")
        shared_with = request.form.get("shared_with")
        
        # Find shared users
        users = []
        if shared_with:
            usernames = [u.strip() for u in shared_with.split(",")]
            users = User.query.filter(User.username.in_(usernames)).all()

        # Add the person creating the expense
        creator = User.query.get(session["user_id"])
        users.append(creator)

        if amount <= 0 or not category:
            flash("Invalid expense details", "danger")
        else:
            new_expense= trip.add_expense(
                amount, 
                category=category, 
                description=description, 
                shared_friends=users
            )

            flash("Expense added successfully!", "success")

            for u in users:
                if u.id != creator.id:
                    Notification.send(
                        receiver_id=u.id,
                        sender_id=creator.id,
                        type="expense_share_request",
                        message=f"{creator.username} added an expense and shared it with you in '{trip.title}'.",
                        trip_id=trip.id,
                        expense_id=new_expense.id
                        
                    )

        return redirect(url_for("trips.trip_budget", trip_id=trip_id))

    return render_template("budget.html", trip=trip)


#==========================================================================================================

@trips_bp.route("/trip/<int:trip_id>/add_planned_budget", methods=["GET", "POST"])
def add_planned_budget(trip_id):
    """Add a planned budget category"""
    trip = Trip.query.get_or_404(trip_id)

    if not trip.budget:
        trip.init_budget()

    if request.method == "POST":
        amount = float(request.form.get("amount"))
        category = request.form.get("category")

        if amount <= 0 or not category:
            flash("Invalid planned budget details", "danger")
        else:
            trip.budget.add_planned_budget(amount=amount, category=category)

        flash("Planned budget added successfully!", "success")
        return redirect(url_for("trips.trip_budget", trip_id=trip_id))
    
    return render_template("budget.html", trip=trip)

#==========================================================================================================

@trips_bp.route("/update_planned_budget/<int:planned_budget_id>", methods=["GET", "POST"])
def update_planned_budget(planned_budget_id):
    """Update a planned budget"""
    planned_budget = PlannedBudget.query.get_or_404(planned_budget_id)
    trip = planned_budget.budget.trip
    user_id = session.get("user_id")

    if user_id not in trip.get_participant_ids():
        flash("You do not have permission to update this planned budget.", "danger")
        return redirect(url_for("trips.trip_budget", trip_id=trip.id))

    if request.method == "POST":
        new_amount = float(request.form.get("amount"))
        new_category = request.form.get("category")

        if new_amount <= 0 or not new_category:
            flash("Invalid planned budget details", "danger")
        else:
            planned_budget.update_budget(new_amount=new_amount, new_category=new_category)

        flash("Planned budget updated successfully!", "success")
        return redirect(url_for("trips.trip_budget", trip_id=trip.id))
    
    return render_template("edit_planned_budget.html", trip=trip, planned_budget=planned_budget)

#==========================================================================================================

@trips_bp.route("/delete_planned_budget/<int:planned_budget_id>", methods=["POST"])
def delete_planned_budget(planned_budget_id):
    """Delete a planned budget"""
    planned_budget = PlannedBudget.query.get_or_404(planned_budget_id)
    trip = planned_budget.budget.trip
    user_id = session.get("user_id")

    if user_id not in trip.get_participant_ids():
        flash("You do not have permission to delete this planned budget.", "danger")
        return redirect(url_for("trips.trip_budget", trip_id=trip.id))

    planned_budget.delete_planned_budget()

    flash("Planned budget deleted successfully!", "success")
    return redirect(url_for("trips.trip_budget", trip_id=trip.id))

#==========================================================================================================
# EXPENSE ROUTES
#==========================================================================================================

@trips_bp.route("/expense/<int:expense_id>/edit", methods=["GET", "POST"])
def edit_expense(expense_id):
    """Edit an expense"""
    expense = Expense.query.get_or_404(expense_id)

    if request.method == "POST":
        amount = request.form.get("amount")
        description = request.form.get("description")
        shared_with = request.form.get("shared_with")
        category = request.form.get("category")

        if shared_with:
            usernames = [u.strip() for u in shared_with.split(",")]
            users = User.query.filter(User.username.in_(usernames)).all()
        else:
            users = []

        if not amount or float(amount) <= 0:
            flash("Invalid expense amount", "danger")
            return redirect(url_for("trips.trip_budget", trip_id=expense.budget.trip_id))
    
        expense.update_details(amount=amount, description=description, shared_friends=users, category=category)

        flash("Expense updated successfully!", "success")
        for friend in expense.shared_users:
            if friend.id != session["user_id"]:
                Notification.send(
                    receiver_id=friend.id,
                    sender_id=session["user_id"],
                    type="expense_updated",
                    message=f"An expense was updated in trip '{expense.budget.trip.title}'.",
                    trip_id=expense.budget.trip.id
                )

        return redirect(url_for("trips.trip_budget", trip_id=expense.budget.trip_id))
    
    return render_template("edit_expense.html", expense=expense)

#==========================================================================================================

@trips_bp.route("/expense/<int:expense_id>/delete", methods=["POST"])
def delete_expense(expense_id):
    """Delete an expense"""
    expense = Expense.query.get_or_404(expense_id)
    trip_id = expense.budget.trip_id
    for friend in expense.shared_users:
        Notification.send(
            receiver_id=friend.id,
            sender_id=session["user_id"],
            type="expense_deleted",
            message=f"An expense was deleted from trip '{expense.budget.trip.title}'.",
            trip_id=trip_id
        )


    expense.delete_expense()

    flash("Expense deleted!", "success")
    return redirect(url_for("trips.trip_budget", trip_id=trip_id))

#==========================================================================================================

@trips_bp.route("/expense/<int:expense_id>/leave_expense", methods=["POST"])
def leave_expense(expense_id):
    """Leave a shared expense"""
    expense = Expense.query.get_or_404(expense_id)

    if request.method == "POST":
        trip_id = expense.budget.trip_id
        user = User.query.get(session["user_id"])
        expense.leave_expense(user)

        flash("You have left this expense.", "info")
        return redirect(url_for("trips.trip_budget", trip_id=trip_id))
    
    return redirect(url_for("trips.trip_budget", trip_id=trip_id))

#==========================================================================================================

@trips_bp.route("/share_expense/<int:expense_id>", methods=["POST"])
def share_expense(expense_id):
    """Send an expense sharing request to another user."""
    expense = Expense.query.get_or_404(expense_id)
    trip = expense.budget.trip
    sender_id = session.get("user_id")

    if not sender_id:
        flash("Please log in first", "danger")
        return redirect(url_for("auth.login"))

    username = request.form.get("username")
    userB = User.query.filter_by(username=username).first()

    if not userB:
        flash("User not found!", "danger")
        return redirect(url_for("trips.trip_detail", trip_id=trip.id))
    
    # Check if userB is part of this trip
    if userB.id not in trip.get_participant_ids():
        flash(f"{username} is not part of this trip!", "info")
        return redirect(url_for("trips.trip_detail", trip_id=trip.id))

    # Prevent sending request to someone already shared
    if userB in expense.shared_users:
        flash(f"{username} is already sharing this expense!", "info")
        return redirect(url_for("trips.trip_detail", trip_id=trip.id))

    # Send notification
    Notification.send(
        receiver_id=userB.id,
        sender_id=sender_id,
        type="expense_share_request",
        message=f"{session['user_name']} wants to share an expense '{expense.description}' with you.",
        trip_id=trip.id,
        expense_id=expense.id
    )

    flash(f"Share request sent to {username}", "success")
    return redirect(url_for("trips.trip_detail", trip_id=trip.id))



#==========================================================================================================

@trips_bp.route("/respond_expense_share/<int:expense_id>/<string:response>", methods=["POST"])
def respond_expense_share(expense_id, response):
    """Respond to an expense share request."""
    expense = Expense.query.get_or_404(expense_id)
    trip = expense.budget.trip
    user_id = session.get("user_id")
    user = User.query.get(user_id)

    if not user:
        flash("Please log in first", "danger")
        return redirect(url_for("auth.login"))

    sender_id = request.form.get("sender_id")
    notif_id = request.form.get("notif_id")  # Pass notification ID in hidden input

    # ACCEPT
    if response == "accept":
        if user not in expense.shared_users:
            expense.shared_users.append(user)
            db.session.commit()


        # Notify original sender
        Notification.send(
            receiver_id=sender_id,
            sender_id=user.id,
            type="expense_share_accepted",
            message=f"{user.username} accepted your expense sharing request for '{expense.description}'.",
            trip_id=trip.id,
            expense_id=expense.id
        )

        flash("You accepted the expense share request.", "success")

    # DENY
    else:
        Notification.send(
            receiver_id=sender_id,
            sender_id=user.id,
            type="expense_share_denied",
            message=f"{user.username} denied your expense sharing request for '{expense.description}'.",
            trip_id=trip.id,
            expense_id=expense.id
        )

        flash("You denied the expense share request.", "info")

    # Remove the request notification from user
    notif = Notification.query.get(notif_id)
    if notif:
        original_sender_id = notif.sender_id
        db.session.delete(notif)
        db.session.commit()
    # then send response to original_sender_id


    return redirect(url_for("trips.trip_detail", trip_id=trip.id))


#==========================================================================================================
# FAVORITE DESTINATIONS ROUTES
#==========================================================================================================

@trips_bp.route("/favorites")
def view_favorites():
    """View all favorite destinations for the logged-in user"""
    if "user_id" not in session:
        flash("Please log in to view your favorite destinations", "danger")
        return redirect(url_for("auth.login"))

    user = User.query.get(session["user_id"])
    favorites = user.get_favorite_destinations()
    
    return render_template("favorites.html", favorites=favorites)

#==========================================================================================================

@trips_bp.route("/favorites/add", methods=["GET", "POST"])
def add_favorite():
    """Add a new favorite destination"""
    if "user_id" not in session:
        flash("Please log in to add favorites", "danger")
        return redirect(url_for("auth.login"))

    if request.method == "POST":
        name = request.form.get("name")
        country = request.form.get("country")
        description = request.form.get("description")
        image_url = request.form.get("image_url")

        if not name:
            flash("Destination name is required", "danger")
            return redirect(url_for("trips.add_favorite"))

        user = User.query.get(session["user_id"])
        destination = user.add_favorite_destination(
            name=name,
            country=country,
            description=description,
            image_url=image_url
        )

        if destination:
            flash(f"Added '{name}' to your favorites!", "success")
        else:
            flash(f"'{name}' is already in your favorites!", "info")

        return redirect(url_for("trips.view_favorites"))

    return render_template("add_favorite.html")

#==========================================================================================================

@trips_bp.route("/favorites/<int:destination_id>/remove", methods=["POST"])
def remove_favorite(destination_id):
    """Remove a destination from favorites"""
    if "user_id" not in session:
        flash("Please log in to manage favorites", "danger")
        return redirect(url_for("auth.login"))

    user = User.query.get(session["user_id"])
    destination = FavoriteDestination.query.get_or_404(destination_id)

    if user.remove_favorite_destination(destination):
        flash(f"Removed '{destination.name}' from your favorites", "success")
    else:
        flash("Destination not found in your favorites", "danger")

    return redirect(url_for("trips.view_favorites"))

#==========================================================================================================

@trips_bp.route("/favorites/<int:destination_id>/edit", methods=["GET", "POST"])
def edit_favorite(destination_id):
    """Edit a favorite destination (only if user is the creator or admin)"""
    if "user_id" not in session:
        flash("Please log in to edit favorites", "danger")
        return redirect(url_for("auth.login"))

    destination = FavoriteDestination.query.get_or_404(destination_id)

    if request.method == "POST":
        name = request.form.get("name")
        country = request.form.get("country")
        description = request.form.get("description")
        image_url = request.form.get("image_url")

        destination.update_details(
            name=name,
            country=country,
            description=description,
            image_url=image_url
        )

        flash(f"Updated '{destination.name}' successfully!", "success")
        return redirect(url_for("trips.view_favorites"))

    return render_template("edit_favorite.html", destination=destination)

#==========================================================================================================

@trips_bp.route("/trip/<int:trip_id>/destination/<int:destination_id>/toggle_favorite", methods=["POST"])
def toggle_trip_destination_favorite(trip_id, destination_id):
    """Toggle favorite status for a trip destination"""
    if "user_id" not in session:
        flash("Please log in to favorite destinations", "danger")
        return redirect(url_for("auth.login"))

    trip = Trip.query.get_or_404(trip_id)
    destination = TripDestination.query.get_or_404(destination_id)
    user = User.query.get(session["user_id"])

    if destination.trip_id != trip_id:
        flash("Invalid destination for this trip", "danger")
        return redirect(url_for("trips.trip_detail", trip_id=trip_id))

    destination.toggle_favorite(user)

    if destination.is_favorited:
        flash(f"Added '{destination.name}' to your favorites!", "success")
    else:
        flash(f"Removed '{destination.name}' from your favorites", "info")

    return redirect(url_for("trips.trip_detail", trip_id=trip_id))

#==========================================================================================================

@trips_bp.route("/favorites/popular")
def popular_destinations():
    """View most popular destinations"""
    limit = request.args.get("limit", 10, type=int)
    popular = FavoriteDestination.get_popular_destinations(limit=limit)
    
    return render_template("popular_destinations.html", destinations=popular)

#==========================================================================================================

@trips_bp.route("/favorites/search")
def search_favorites():
    """Search for destinations"""
    query = request.args.get("q", "")
    
    if not query:
        flash("Please enter a search query", "info")
        return redirect(url_for("trips.view_favorites"))

    results = FavoriteDestination.search_destinations(query)
    
    return render_template("search_results.html", results=results, query=query)

#==========================================================================================================

@trips_bp.route("/api/favorites/check/<string:destination_name>")
def check_favorite_status(destination_name):
    """API endpoint to check if a destination is favorited by the current user"""
    if "user_id" not in session:
        return jsonify({"favorited": False, "error": "Not logged in"}), 401

    user = User.query.get(session["user_id"])
    is_favorited = user.is_destination_favorited(destination_name)

    return jsonify({"favorited": is_favorited, "destination": destination_name})

#==========================================================================================================

@trips_bp.route("/api/favorites/stats")
def favorite_stats():
    """API endpoint to get user's favorite statistics"""
    if "user_id" not in session:
        return jsonify({"error": "Not logged in"}), 401

    user = User.query.get(session["user_id"])
    favorites = user.get_favorite_destinations()

    stats = {
        "total_favorites": len(favorites),
        "countries": list(set([f.country for f in favorites if f.country])),
        "destinations": [{"name": f.name, "country": f.country} for f in favorites]
    }

    return jsonify(stats)

#==========================================================================================================

@trips_bp.route("/trip/<int:trip_id>/add_destination_from_favorites", methods=["POST"])
def add_destination_from_favorites(trip_id):
    """Add a destination from favorites to a trip"""
    if "user_id" not in session:
        flash("Please log in", "danger")
        return redirect(url_for("auth.login"))

    trip = Trip.query.get_or_404(trip_id)
    user_id = session.get("user_id")

    if user_id not in trip.get_participant_ids():
        flash("You do not have permission to modify this trip.", "danger")
        return redirect(url_for("trips.view_trips"))

    destination_id = request.form.get("destination_id")
    favorite_destination = FavoriteDestination.query.get_or_404(destination_id)

    # Check if destination already exists in trip
    existing = any(d.name.lower() == favorite_destination.name.lower() for d in trip.destinations)
    
    if existing:
        flash(f"'{favorite_destination.name}' is already in this trip!", "info")
    else:
        trip.add_destination(favorite_destination.name)
        flash(f"Added '{favorite_destination.name}' to trip!", "success")

    return redirect(url_for("trips.trip_detail", trip_id=trip_id))

#==========================================================================================================
# REVIEW ROUTES
#==========================================================================================================

@trips_bp.route("/reviews")
def view_all_reviews():
    """View all reviews from all trips"""
    if "user_id" not in session:
        flash("Please log in to view reviews", "danger")
        return redirect(url_for("auth.login"))
    
    # Get all reviews ordered by most recent
    reviews = Review.query.order_by(Review.created_at.desc()).all()
    return render_template("reviews.html", reviews=reviews)

#==========================================================================================================

@trips_bp.route("/trip/<int:trip_id>/reviews")
def trip_reviews(trip_id):
    """View all reviews for a specific trip"""
    trip = Trip.query.get_or_404(trip_id)
    return render_template("trip_reviews.html", trip=trip)

#==========================================================================================================

@trips_bp.route("/trip/<int:trip_id>/review/add", methods=["GET", "POST"])
def add_review(trip_id):
    """Add a review for a trip"""
    if "user_id" not in session:
        flash("Please log in to add a review", "danger")
        return redirect(url_for("auth.login"))

    trip = Trip.query.get_or_404(trip_id)
    user_id = session.get("user_id")

    # Check if user already reviewed this trip
    existing_review = Review.query.filter_by(trip_id=trip_id, user_id=user_id).first()
    if existing_review:
        flash("You have already reviewed this trip. You can edit your existing review.", "info")
        return redirect(url_for("trips.edit_review", review_id=existing_review.id))

    if request.method == "POST":
        rating = request.form.get("rating", type=int)
        comment = request.form.get("comment")

        if not rating or rating < 1 or rating > 5:
            flash("Please select a rating between 1 and 5 stars", "danger")
            return redirect(url_for("trips.add_review", trip_id=trip_id))

        try:
            review = Review.create(trip_id=trip_id, user_id=user_id, rating=rating, comment=comment)
            
            # Handle photo uploads
            if 'photos' in request.files:
                files = request.files.getlist('photos')
                for file in files:
                    if file and file.filename and allowed_file(file.filename):
                        filename = secure_filename(f"{datetime.now().timestamp()}_{file.filename}")
                        
                        # Create upload directory if it doesn't exist
                        os.makedirs(UPLOAD_FOLDER, exist_ok=True)
                        
                        filepath = os.path.join(UPLOAD_FOLDER, filename)
                        file.save(filepath)
                        
                        # Store relative path for URL
                        photo_url = f"/static/uploads/reviews/{filename}"
                        review.add_photo(photo_url)

            flash("Review added successfully!", "success")
            return redirect(url_for("trips.view_all_reviews"))

        except ValueError as e:
            flash(str(e), "danger")
            return redirect(url_for("trips.add_review", trip_id=trip_id))

    return render_template("add_review.html", trip=trip)

#==========================================================================================================

@trips_bp.route("/review/<int:review_id>/edit", methods=["GET", "POST"])
def edit_review(review_id):
    """Edit an existing review"""
    if "user_id" not in session:
        flash("Please log in to edit reviews", "danger")
        return redirect(url_for("auth.login"))

    review = Review.query.get_or_404(review_id)
    user_id = session.get("user_id")

    # Check if user owns this review
    if review.user_id != user_id:
        flash("You can only edit your own reviews", "danger")
        return redirect(url_for("trips.view_all_reviews"))

    if request.method == "POST":
        rating = request.form.get("rating", type=int)
        comment = request.form.get("comment")

        if not rating or rating < 1 or rating > 5:
            flash("Please select a rating between 1 and 5 stars", "danger")
            return redirect(url_for("trips.edit_review", review_id=review_id))

        try:
            review.update(rating=rating, comment=comment)
            
            # Handle photo deletion (photos_to_delete comes from the hidden input)
            photos_to_delete = request.form.get('photos_to_delete', '')
            if photos_to_delete:
                photo_ids = [int(pid) for pid in photos_to_delete.split(',') if pid.strip()]
                for photo_id in photo_ids:
                    photo = ReviewPhoto.query.get(photo_id)
                    if photo and photo.review_id == review_id:
                        try:
                            # Delete photo from filesystem
                            photo_path = os.path.join('app', photo.photo_url.lstrip('/'))
                            if os.path.exists(photo_path):
                                os.remove(photo_path)
                        except Exception as e:
                            print(f"Error deleting photo file: {e}")
                        
                        # Delete photo record from database
                        db.session.delete(photo)
                
                db.session.commit()
            
            # Handle new photo uploads
            if 'photos' in request.files:
                files = request.files.getlist('photos')
                for file in files:
                    if file and file.filename and allowed_file(file.filename):
                        filename = secure_filename(f"{datetime.now().timestamp()}_{file.filename}")
                        
                        # Create upload directory if it doesn't exist
                        os.makedirs(UPLOAD_FOLDER, exist_ok=True)
                        
                        filepath = os.path.join(UPLOAD_FOLDER, filename)
                        file.save(filepath)
                        
                        # Store relative path for URL
                        photo_url = f"/static/uploads/reviews/{filename}"
                        review.add_photo(photo_url)

            flash("Review updated successfully!", "success")
            return redirect(url_for("trips.view_all_reviews"))

        except ValueError as e:
            db.session.rollback()
            flash(str(e), "danger")
            return redirect(url_for("trips.edit_review", review_id=review_id))
        except Exception as e:
            db.session.rollback()
            flash(f"Error updating review: {str(e)}", "danger")
            return redirect(url_for("trips.edit_review", review_id=review_id))

    return render_template("edit_review.html", review=review)
#==========================================================================================================

@trips_bp.route("/review/<int:review_id>/delete", methods=["POST"])
def delete_review(review_id):
    """Delete a review"""
    if "user_id" not in session:
        flash("Please log in", "danger")
        return redirect(url_for("auth.login"))

    review = Review.query.get_or_404(review_id)
    user_id = session.get("user_id")

    # Check if user owns this review
    if review.user_id != user_id:
        flash("You can only delete your own reviews", "danger")
        return redirect(url_for("trips.view_all_reviews"))

    # Delete associated photos from filesystem
    for photo in review.photos:
        try:
            photo_path = os.path.join('app', photo.photo_url.lstrip('/'))
            if os.path.exists(photo_path):
                os.remove(photo_path)
        except Exception as e:
            print(f"Error deleting photo: {e}")

    review.delete()
    flash("Review deleted successfully!", "success")
    return redirect(url_for("trips.view_all_reviews"))

#==========================================================================================================

@trips_bp.route("/review/<int:review_id>/photo/<int:photo_id>/delete", methods=["POST"])
def delete_review_photo(review_id, photo_id):
    """Delete a photo from a review"""
    if "user_id" not in session:
        flash("Please log in", "danger")
        return redirect(url_for("auth.login"))

    review = Review.query.get_or_404(review_id)
    photo = ReviewPhoto.query.get_or_404(photo_id)
    user_id = session.get("user_id")

    # Check if user owns this review
    if review.user_id != user_id:
        flash("You can only delete photos from your own reviews", "danger")
        return redirect(url_for("trips.view_all_reviews"))

    # Check if photo belongs to this review
    if photo.review_id != review_id:
        flash("Invalid photo", "danger")
        return redirect(url_for("trips.edit_review", review_id=review_id))

    # Delete photo from filesystem
    try:
        photo.delete()
    except Exception as e:
        print(f"Error deleting photo: {e}")

    flash("Photo deleted successfully!", "success")
    return redirect(url_for("trips.edit_review", review_id=review_id))