from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from app.models import Trip, ItineraryItem,  Expense, User, PlannedBudget
from werkzeug.security import check_password_hash
from datetime import datetime

trips_bp = Blueprint("trips", __name__)

#==========================================================================================================

@trips_bp.route("/trips")
def view_trips():       # View all trips for the logged-in user
    if "user_id" not in session:
        flash("Please log in to view your trips", "warning")
        return redirect(url_for("auth.login"))

    trips = Trip.query.all()        # Fetch all trips (filtering by user_id is done in trips.html)
    return render_template("trips.html", trips=trips)

#==========================================================================================================

@trips_bp.route("/create_trip", methods=["GET", "POST"])
def create_trip():
    if "user_id" not in session:    # If user not logged in, redirect to login
        flash("Please log in to create a trip", "warning")
        return redirect(url_for("auth.login"))

    if request.method == "POST":
        # Retrieve form data
        title = request.form.get("title")
        destinations = request.form.getlist("destinations")
        start_date = request.form.get("start_date")
        end_date = request.form.get("end_date")
        description = request.form.get("description")

        if not title or not destinations or not start_date or not end_date:  # Basic validation
            flash("All required fields must be filled", "info")
            return redirect(url_for("trips.create_trip"))
        
        
        # Convert date strings to date objects
        start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
        end_date = datetime.strptime(end_date, "%Y-%m-%d").date()
 
        # Get the current user as the trip participant
        user_id = session.get("user_id")
        participant = User.query.get(user_id)

        trip = Trip.create(      # Call class method to create and save the trip
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
    trip = Trip.query.get_or_404(trip_id)   # Get trip by ID or return 404 if not found
    user_id = session.get("user_id")

    if user_id not in trip.get_participant_ids():  # Check if current user is a participant
        flash("You do not have permission to edit this trip.", "danger")
        return redirect(url_for("trips.view_trips"))

    if request.method == "POST":    # Process form submission
        title = request.form.get("title")
        destinations = request.form.getlist("destinations")
        start_date = request.form.get("start_date")
        end_date = request.form.get("end_date")
        description = request.form.get("description")

        # Convert date strings to date objects
        start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
        end_date = datetime.strptime(end_date, "%Y-%m-%d").date()

        # Update trip details using instance method
        trip.update_details(title=title, destinations=destinations,
                            start_date=start_date, end_date=end_date,
                            description=description)

        flash("Trip updated successfully!", "success")
        return redirect(url_for("trips.trip_detail", trip_id=trip.id))
    return render_template("edit_trip.html", trip=trip)

#==========================================================================================================

@trips_bp.route("/trip/<int:trip_id>/share", methods=["POST"])
def share_trip(trip_id):
    trip = Trip.query.get_or_404(trip_id)       # Get trip by ID or return 404 if not found
    user_id = session.get("user_id")
    if not user_id:     # If user not logged in, redirect to login
        flash("Please log in.", "info")
        return redirect(url_for("auth.login"))

    if user_id not in trip.get_participant_ids():  # Check if current user is a participant
        flash("You do not have permission to share this trip.", "danger")
        return redirect(url_for("trips.view_trips"))
    
    # Ensure the user is a participant of the trip
    username = request.form.get("username")
    friend = User.query.filter_by(username=username).first()    # User B (the one to share with)
    if not friend:      # If user doesnot exists in our database
        flash("User not found!", "danger")
        return redirect(url_for("trips.trip_detail", trip_id=trip.id))

    flash(f"Share request sent to {username}", "success")
    return redirect(url_for("trips.trip_detail", trip_id=trip.id))

#==========================================================================================================

@trips_bp.route("/respond_trip_share/<int:trip_id>/<string:response>", methods=["POST"])
def respond_trip_share(trip_id, response):
    trip = Trip.query.get_or_404(trip_id)   # Get trip by ID or return 404 if not found
    user = User.query.get(session["user_id"])   # Current user (User B) responding to share request

    # Ensure the user is not already a participant
    if user.id in trip.get_participant_ids():
        flash("You already have access to this trip.", "info")
        return redirect(url_for("trips.view_trips"))
    
    if response == "accept":    # If User B accepts the share request
        trip.share_with(user)   # Call instance method to add user as participant
        flash(f"You now have access to trip '{trip.title}'.", "success")
    else:       # If User B rejects the share request
        flash("You rejected the trip share request.", "info")

    return redirect(url_for("trips.view_trips"))

#==========================================================================================================

@trips_bp.route("/trip/<int:trip_id>/delete", methods=["POST"])
def delete_trip(trip_id):
    trip = Trip.query.get_or_404(trip_id)       # Get trip by ID or return 404 if not found
    user_id = session.get('user_id')

    if not user_id:     # If user not logged in, redirect to login
        flash("You must be logged in to perform this action.", "info")
        return redirect(url_for("auth.login"))

    user = User.query.get(session["user_id"])   # Current user attempting to delete the trip

    #  user only removes their access
    trip.remove_participant(user)

    flash("You left this trip.", "success")
    return redirect(url_for("trips.view_trips"))

#==========================================================================================================

@trips_bp.route("/trip/<int:trip_id>")
def trip_detail(trip_id):
    trip = Trip.query.get_or_404(trip_id)   # Get trip by ID or return 404 if not found
    return render_template("trip_detail.html", trip=trip)   # Render trip_detail.html with trip data

#==========================================================================================================

@trips_bp.route("/user/<int:user_id>/delete_trips", methods=["GET", "POST"])
def delete_user_trips(user_id):
    user = User.query.get_or_404(user_id)   # Get user by ID or return 404 if not found
    user_id = session.get('user_id')

    if not user_id:    # If user not logged in, redirect to login
        flash("You must be logged in to perform this action.", "info")
        return redirect(url_for("auth.login"))

    if request.method == "POST":        
        password = request.form.get("password")     # Get password from form to confirm identity

        # Verify password
        if not check_password_hash(user.password, password):
            flash("Incorrect password. Trips not deleted.", "danger")
            return redirect(url_for("trips.delete_user_trips", user_id=user_id))
        
        Trip.delete_all_trips(user)  # Call class method to delete all trips for the associated user
        flash("All trips deleted successfully!", "info")
        return redirect(url_for("trips.view_trips"))

    return render_template("confirm_delete.html", user=user)

#==========================================================================================================

@trips_bp.route("/trip/<int:trip_id>/add_itinerary", methods=["POST"])
def add_itinerary(trip_id):
    trip = Trip.query.get_or_404(trip_id)   # Get trip by ID or return 404 if not found
    user_id = session.get("user_id")

    if user_id not in trip.get_participant_ids():  # Check if current user is a participant
        flash("You do not have permission to add itinerary items to this trip.", "danger")
        return redirect(url_for("trips.view_trips"))
    
    # Retrieve form data
    title = request.form.get("title")
    date = request.form.get("date")
    time = request.form.get("time")
    location = request.form.get("location")
    notes = request.form.get("notes")

    if not title or not date:   # Basic validation
        flash("Itinerary item must have a title and date", "info")
        return redirect(url_for("trips.trip_detail", trip_id=trip_id))
    
    # Convert date string to date object
    date = datetime.strptime(date, "%Y-%m-%d").date()
    time = datetime.strptime(time, "%H:%M:%S").time() if time else None
    trip.add_itinerary_item(title, date, location, notes, time)   # Call instance method to add itinerary item

    flash("Itinerary item added!", "success")
    return redirect(url_for("trips.trip_detail", trip_id=trip_id))

#==========================================================================================================

@trips_bp.route("/itinerary/<int:item_id>/edit", methods=["GET","POST"])
def edit_itinerary(item_id):
    item = ItineraryItem.query.get_or_404(item_id)  # Get itinerary item by ID or return 404 if not found
    user_id = session.get("user_id")

    if user_id not in item.trip.get_participant_ids():  # Check if current user is a participant
        flash("You do not have permission to edit this itinerary item.", "info")
        return redirect(url_for("trips.trip_detail", trip_id=item.trip_id))

    if request.method == 'POST':
        # Retrieve form data
        title = request.form.get("title")
        date = request.form.get("date")
        time = request.form.get("time")
        location = request.form.get("location")
        notes = request.form.get("notes")

        # Convert date string to date object, if user updated date
        if date:
            date = datetime.strptime(date, "%Y-%m-%d").date()
        if time:
            time = datetime.strptime(time, "%H:%M:%S").time()

         # Update itinerary item details using instance method
        item.update(title=title, date=date, location=location, notes=notes, time=time)
        flash("Itinerary item updated!", "success")
        return redirect(url_for("trips.trip_detail", trip_id=item.trip_id))
    
    trip = item.trip    # Get associated trip for context
    return render_template("edit_itinerary.html", item=item, trip=trip)  # Render edit_itinerary.html with item and trip data   

#==========================================================================================================

@trips_bp.route("/itinerary/<int:item_id>/delete", methods=["POST"])
def delete_itinerary(item_id):
    item = ItineraryItem.query.get_or_404(item_id)  # Get itinerary item by ID or return 404 if not found
    trip_id = item.trip_id
    user_id = session.get("user_id")

    if user_id not in item.trip.get_participant_ids():  # Check if current user is a participant
        flash("You do not have permission to delete this itinerary item.", "danger")
        return redirect(url_for("trips.trip_detail", trip_id=trip_id))

     # Call instance method to delete itinerary item
    item.delete()
    flash("Itinerary item deleted!", "success")
    return redirect(url_for("trips.trip_detail", trip_id=trip_id))

#==========================================================================================================

@trips_bp.route("/trip/<int:trip_id>/budget", methods=["GET", "POST"])
def trip_budget(trip_id):
    trip = Trip.query.get_or_404(trip_id)   # Get trip by ID or return 404 if not found

    if not trip.budget:     # If budget does not exist yet, initialize it
        trip.init_budget()

    if request.method == "POST":
        # Retrieve form data
        amount = float(request.form.get("amount"))
        category = request.form.get("category")
        description = request.form.get("description")
        shared_with = request.form.get("shared_with")
        
        if shared_with: 
            usernames = [u.strip() for u in shared_with.split(",")]
            users = User.query.filter(User.username.in_(usernames)).all()
            users.append(User.query.get(session["user_id"]))  # Ensure current user is included
        else: 
            users = []

        if amount <= 0 or not category:   # Basic validation
            flash("Invalid expense details", "danger")
        else:
            trip.add_expense(amount, category=category, description=description, shared_friends=users)

        flash("Expense added successfully!", "success")
        return redirect(url_for("trips.trip_budget", trip_id=trip_id))

    return render_template("budget.html", trip=trip)
#==========================================================================================================
@trips_bp.route("/trip/<int:trip_id>/add_planned_budget", methods=["GET", "POST"])
def add_planned_budget(trip_id):
    trip = Trip.query.get_or_404(trip_id)   # Get trip by ID or return 404 if not found

    if not trip.budget:     # If budget does not exist yet, initialize it
        trip.init_budget()

    # Retrieve form data
    if request.method == "POST":
        amount = float(request.form.get("amount"))
        category = request.form.get("category")

        if amount <= 0 or not category:   # Basic validation
            flash("Invalid planned budget details", "danger")
        else:
            trip.budget.add_planned_budget(amount=amount, category=category)

        flash("Planned budget added successfully!", "success")
        return redirect(url_for("trips.trip_budget", trip_id=trip_id))
    return render_template("budget.html", trip=trip)

#==========================================================================================================
@trips_bp.route("/update_planned_budget/<int:planned_budget_id>", methods=["GET", "POST"])
def update_planned_budget(planned_budget_id):
    planned_budget = PlannedBudget.query.get_or_404(planned_budget_id)  # Get planned budget by ID or return 404 if not found
    trip = planned_budget.budget.trip
    user_id = session.get("user_id")

    if user_id not in trip.get_participant_ids():  # Check if current user is a participant
        flash("You do not have permission to update this planned budget.", "danger")
        return redirect(url_for("trips.trip_budget", trip_id=trip.id))

    if request.method == "POST":
        new_amount = float(request.form.get("amount"))
        new_category = request.form.get("category")

        if new_amount <= 0 or not new_category:   # Basic validation
            flash("Invalid planned budget details", "danger")
        else:
            planned_budget.update_budget(new_amount=new_amount, new_category=new_category)

        flash("Planned budget updated successfully!", "success")
        return redirect(url_for("trips.trip_budget", trip_id=trip.id))
    return render_template("edit_planned_budget.html", trip=trip, planned_budget=planned_budget)

#==========================================================================================================
@trips_bp.route("/delete_planned_budget/<int:planned_budget_id>", methods=["POST"])
def delete_planned_budget(planned_budget_id):
    planned_budget = PlannedBudget.query.get_or_404(planned_budget_id)  # Get planned budget by ID or return 404 if not found
    trip = planned_budget.budget.trip
    user_id = session.get("user_id")

    if user_id not in trip.get_participant_ids():  # Check if current user is a participant
        flash("You do not have permission to delete this planned budget.", "danger")
        return redirect(url_for("trips.trip_budget", trip_id=trip.id))

    # Delete the planned budget
    planned_budget.delete_planned_budget()

    flash("Planned budget deleted successfully!", "success")
    return redirect(url_for("trips.trip_budget", trip_id=trip.id))

#==========================================================================================================

@trips_bp.route("/expense/<int:expense_id>/edit", methods=["GET", "POST"])
def edit_expense(expense_id):
    expense = Expense.query.get_or_404(expense_id)

    # Retrieve form data
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

        if not amount or float(amount) <= 0:   # Basic validation
            flash("Invalid expense amount", "danger")
            return redirect(url_for("trips.trip_budget", trip_id=expense.budget.trip_id))
    
        # Update expense details using instance method
        expense.update_details(amount=amount, description=description, shared_friends=users, category=category)

        flash("Expense updated successfully!", "success")
        return redirect(url_for("trips.trip_budget", trip_id=expense.budget.trip_id))
    return render_template("edit_expense.html", expense=expense)

#==========================================================================================================

@trips_bp.route("/expense/<int:expense_id>/delete", methods=["POST"])
def delete_expense(expense_id):     # Delete an expense
    expense = Expense.query.get_or_404(expense_id)
    trip_id = expense.budget.trip_id

    expense.delete_expense()

    flash("Expense deleted!", "success")
    return redirect(url_for("trips.trip_budget", trip_id=trip_id))

#==========================================================================================================
@trips_bp.route("/expense/<int:expense_id>/leave_expense", methods=["POST"])
def leave_expense(expense_id):     # Leave an expense
    expense = Expense.query.get_or_404(expense_id)

    if request.method == "POST":
        trip_id = expense.budget.trip_id
        user = User.query.get(session["user_id"])   # Current user leaving the expense
        expense.leave_expense(user)

        flash("You have left this expense.", "info")
        return redirect(url_for("trips.trip_budget", trip_id=trip_id))
    return redirect(url_for("trips.trip_budget", trip_id=trip_id))

#==========================================================================================================

@trips_bp.route("/share_expense/<int:expense_id>", methods=["POST"])
def share_expense(expense_id):
    expense = Expense.query.get_or_404(expense_id)
    username = request.form.get("username")  # entered by User A

    userB = User.query.filter_by(username=username).first()   # Finding User B (the one to share with) in our database
    if not userB:       # If user doesnot exists in our database
        flash("User not found!", "danger")
        return redirect(url_for("trips.trip_detail", trip_id=expense.budget.trip_id))

    expense.split_with([username])  # Call instance method to create a share request

    flash(f"Share request sent to {username}", "info")
    return redirect(url_for("trips.trip_detail", trip_id=expense.budget.trip_id))

#==========================================================================================================

@trips_bp.route("/respond_share/<int:expense_id>/<string:response>", methods=["POST"])
def respond_share(expense_id, response):
    expense = Expense.query.get_or_404(expense_id)  # Get expense by ID or return 404 if not found
    expense.update_status("Accepted" if response == "accept" else "Rejected")   # Call instance method to update share status

    if response == "accept":
        flash(f"You accepted sharing {expense.description}", "success")
    else:
        flash(f"You rejected sharing {expense.description}", "danger")

    return redirect(url_for("trips.trip_detail", trip_id=expense.budget.trip_id))
