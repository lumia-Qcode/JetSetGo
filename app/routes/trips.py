from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from app.models import Trip, ItineraryItem, Expense, User, PlannedBudget, FavoriteDestination, TripDestination
from werkzeug.security import check_password_hash
from datetime import datetime

trips_bp = Blueprint("trips", __name__)

#==========================================================================================================
# TRIPS ROUTES
#==========================================================================================================

@trips_bp.route("/trips")
def view_trips():
    """View all trips for the logged-in user"""
    if "user_id" not in session:
        flash("Please log in to view your trips", "warning")
        return redirect(url_for("auth.login"))

    trips = Trip.query.all()
    return render_template("trips.html", trips=trips)

#==========================================================================================================

@trips_bp.route("/create_trip", methods=["GET", "POST"])
def create_trip():
    """Create a new trip"""
    if "user_id" not in session:
        flash("Please log in to create a trip", "warning")
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
        return redirect(url_for("trips.view_trips", trip_id=trip.id))
    
    return render_template("edit_trip.html", trip=trip)

#==========================================================================================================

@trips_bp.route("/trip/<int:trip_id>/share", methods=["POST"])
def share_trip(trip_id):
    """Share a trip with another user"""
    trip = Trip.query.get_or_404(trip_id)
    user_id = session.get("user_id")
    
    if not user_id:
        flash("Please log in.", "info")
        return redirect(url_for("auth.login"))

    if user_id not in trip.get_participant_ids():
        flash("You do not have permission to share this trip.", "danger")
        return redirect(url_for("trips.view_trips"))
    
    username = request.form.get("username")
    friend = User.query.filter_by(username=username).first()
    
    if not friend:
        flash("User not found!", "danger")
        return redirect(url_for("trips.trip_detail", trip_id=trip.id))

    flash(f"Share request sent to {username}", "success")
    return redirect(url_for("trips.trip_detail", trip_id=trip.id))

#==========================================================================================================

@trips_bp.route("/respond_trip_share/<int:trip_id>/<string:response>", methods=["POST"])
def respond_trip_share(trip_id, response):
    """Respond to a trip share request"""
    trip = Trip.query.get_or_404(trip_id)
    user = User.query.get(session["user_id"])

    if user.id in trip.get_participant_ids():
        flash("You already have access to this trip.", "info")
        return redirect(url_for("trips.view_trips"))
    
    if response == "accept":
        trip.share_with(user)
        flash(f"You now have access to trip '{trip.title}'.", "success")
    else:
        flash("You rejected the trip share request.", "info")

    return redirect(url_for("trips.view_trips"))

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
        
        if shared_with:
            usernames = [u.strip() for u in shared_with.split(",")]
            users = User.query.filter(User.username.in_(usernames)).all()
            users.append(User.query.get(session["user_id"]))
        else:
            users = []

        if amount <= 0 or not category:
            flash("Invalid expense details", "danger")
        else:
            trip.add_expense(amount, category=category, description=description, shared_friends=users)

        flash("Expense added successfully!", "success")
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
        return redirect(url_for("trips.trip_budget", trip_id=expense.budget.trip_id))
    
    return render_template("edit_expense.html", expense=expense)

#==========================================================================================================

@trips_bp.route("/expense/<int:expense_id>/delete", methods=["POST"])
def delete_expense(expense_id):
    """Delete an expense"""
    expense = Expense.query.get_or_404(expense_id)
    trip_id = expense.budget.trip_id

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
    """Share an expense with another user"""
    expense = Expense.query.get_or_404(expense_id)
    username = request.form.get("username")

    userB = User.query.filter_by(username=username).first()
    
    if not userB:
        flash("User not found!", "danger")
        return redirect(url_for("trips.trip_detail", trip_id=expense.budget.trip_id))

    expense.split_with([username])

    flash(f"Share request sent to {username}", "info")
    return redirect(url_for("trips.trip_detail", trip_id=expense.budget.trip_id))

#==========================================================================================================

@trips_bp.route("/respond_share/<int:expense_id>/<string:response>", methods=["POST"])
def respond_share(expense_id, response):
    """Respond to an expense share request"""
    expense = Expense.query.get_or_404(expense_id)
    expense.update_status("Accepted" if response == "accept" else "Rejected")

    if response == "accept":
        flash(f"You accepted sharing {expense.description}", "success")
    else:
        flash(f"You rejected sharing {expense.description}", "danger")

    return redirect(url_for("trips.trip_detail", trip_id=expense.budget.trip_id))

#==========================================================================================================
# FAVORITE DESTINATIONS ROUTES
#==========================================================================================================

@trips_bp.route("/favorites")
def view_favorites():
    """View all favorite destinations for the logged-in user"""
    if "user_id" not in session:
        flash("Please log in to view your favorite destinations", "warning")
        return redirect(url_for("auth.login"))

    user = User.query.get(session["user_id"])
    favorites = user.get_favorite_destinations()
    
    return render_template("favorites.html", favorites=favorites)

#==========================================================================================================

@trips_bp.route("/favorites/add", methods=["GET", "POST"])
def add_favorite():
    """Add a new favorite destination"""
    if "user_id" not in session:
        flash("Please log in to add favorites", "warning")
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
        flash("Please log in to manage favorites", "warning")
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
        flash("Please log in to edit favorites", "warning")
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
        flash("Please log in to favorite destinations", "warning")
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
        flash("Please log in", "warning")
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