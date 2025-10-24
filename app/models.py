from app import db
from werkzeug.security import generate_password_hash, check_password_hash
from flask import session
from datetime import datetime, timedelta
import secrets
from flask_mail import Message
from flask import current_app
from app import mail

#==========================================================================================================

# Association table (Many to Many) between Users and Trips
trip_users = db.Table(      # This creates a join table (no model class needed) linking users and trips
    "trip_users",
    db.Column("user_id", db.Integer, db.ForeignKey("user.id"), primary_key=True),
    db.Column("trip_id", db.Integer, db.ForeignKey("trip.id"), primary_key=True)
)

# Association table (Many to Many) between Expenses and Users for sharing
expense_shared = db.Table(
    "expense_shared",
    db.Column("expense_id", db.Integer, db.ForeignKey("expense.id"), primary_key=True),
    db.Column("user_id", db.Integer, db.ForeignKey("user.id"), primary_key=True)
)

#==========================================================================================================

class PasswordResetToken(db.Model):
    __tablename__ = "password_reset_tokens"

    id = db.Column(db.Integer, primary_key=True)
    token = db.Column(db.String(100), unique=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=False)
    used = db.Column(db.Boolean, default=False)

    # Relationship to user
    user = db.relationship("User", backref=db.backref("reset_tokens", lazy=True))

    @classmethod
    def generate_token(cls, user, expires_in=3600):
        token = secrets.token_urlsafe(32)  # secure random token
        expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
        reset_token = cls(token=token, user=user, expires_at=expires_at)
        db.session.add(reset_token)
        db.session.commit()
        return token

    def is_valid(self):
        return not self.used and datetime.utcnow() < self.expires_at

    def mark_as_used(self):
        self.used = True
        db.session.commit()

    def reset_password(self, new_password):
        """
        Resets the user's password and marks the token as used.
        Raises ValueError if token is invalid or expired.
        """
        if not self.is_valid():
            raise ValueError("Token is invalid or expired.")

        self.user.password = generate_password_hash(new_password)
        self.mark_as_used()  # marks the token as used and commits
        db.session.commit()

    def send_email(to_email, subject, body):
        msg = Message(subject=subject, recipients=[to_email], body=body, sender=current_app.config['MAIL_USERNAME'])
        mail.send(msg)

#==========================================================================================================
class User(db.Model):
    # Attributes
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key = True)
    username = db.Column(db.String(100), nullable = False)
    email = db.Column(db.String(100), unique = True, nullable = False)
    password = db.Column(db.String(200), nullable = False)

    # Relationships
    shared_expenses = db.relationship("Expense", secondary=expense_shared, backref="users_shared")

    # Functions
    @classmethod
    def register(cls, username, email, password):   # Register new User
        if cls.query.filter_by(email = email).first():
            return None
        
        hashed_password = generate_password_hash(password)
        user = cls(username = username, email = email, password = hashed_password)
        db.session.add(user)
        db.session.commit()
        return user
    
    @classmethod
    def authenticate(cls, email, password):     # Check if user is authentic
        user = cls.query.filter_by(email = email).first()
        if user and check_password_hash(user.password, password):
            return user
        return None
    
    def login(self):        # Log in this user in session
        session['user_id'] = self.id
        session['user_email'] = self.email
        session['user_name'] = self.username

    @staticmethod
    def logout():           # Log out current user from session
        session.pop('user_id', None)
        session.pop('user_name', 'None')
        session.pop('user_email', 'None')

    def __repr__(self):     # Returns a readable string representation of the User object for debugging
        return f"<User {self.username}>"

#==========================================================================================================

class Task(db.Model):
    # Attributes
    __tablename__ = 'task'
    id = db.Column(db.Integer, primary_key = True)
    title = db.Column(db.String(100), nullable = False) 
    due_date = db.Column(db.Date, nullable = True)
    due_time = db.Column(db.Time, nullable = True)
    status = db.Column(db.String(20), default = "Pending")
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))

    # Functions
    @classmethod
    def create(cls, title, user_id, due_date, due_time):    # Create New Task
        task = cls(title=title, user_id=user_id, due_date=due_date, due_time=due_time)
        db.session.add(task)
        db.session.commit()
        return task
    
    def update(self, title=None, due_date=None, due_time=None):   # Update Task Details
        if title: self.title = title
        if due_date: self.due_date = due_date
        if due_time: self.due_time = due_time
        db.session.commit()
        return self
    
    def toggle_status(self):    # Change Status Pending -> Working -> Done -> Pending
        if self.status == 'Pending':
            self.status = 'Working'
        elif self.status == 'Working':
            self.status = 'Done'
        else:
            self.status = 'Pending'
        db.session.commit()

    def delete(self):   # Delete this Task
        db.session.delete(self)
        db.session.commit()

    @classmethod
    def clear_user_tasks(cls, user_id):     # Delete all Tasks of this User
        cls.query.filter_by(user_id = user_id).delete()
        db.session.commit()

#==========================================================================================================

class Trip(db.Model):
    # Attributes
    __tablename__ = "trip"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    description = db.Column(db.Text, nullable=True)
    destinations = db.relationship(
        "TripDestination",
        backref="trip",
        cascade="all, delete-orphan",
        lazy=True
    )

    # Relationships
    itinerary = db.relationship("ItineraryItem", backref="trip", lazy=True, cascade="all, delete-orphan")
    budget = db.relationship("Budget", backref="trip", uselist=False, cascade="all, delete-orphan")
    participants = db.relationship("User", secondary=trip_users, backref=db.backref("trips", lazy="dynamic"))

    # Functions 
    @classmethod
    def create(cls, title, destinations, start_date, end_date, description, participant):   # Create New Trip

        trip = cls(
            title=title,
            start_date=start_date,
            end_date=end_date,
            description=description
        )
        db.session.add(trip)
        db.session.flush()      # Get trip.id before commit

        for dest in destinations:       # Split by comma and add each destination
            if dest.strip():
                trip.destinations.append(TripDestination(name=dest.strip()))

        trip.participants.append(participant)   # Add the user as a participant of this tri[]
        db.session.commit()
        return trip
    
    def update_details(self, title=None, destinations=None, start_date=None, end_date=None, description=None):
        # Update trip details
        if title: 
            self.title = title
        if destinations:
            self.destinations = []
            for dest in destinations:       # Split by comma and add each destination
                if dest.strip():
                    self.destinations.append(TripDestination(name=dest.strip()))
        if start_date: 
            self.start_date = start_date
        if end_date: 
            self.end_date = end_date
        if description is not None: 
            self.description = description

        db.session.commit()
        return self

    def add_itinerary_item(self, title, date, location=None, notes=None, time=None):   # Add new itinerary item
        item = ItineraryItem(title=title, date=date, location=location, notes=notes, time=time, trip_id=self.id)
        db.session.add(item)
        db.session.commit()
        return item

    def init_budget(self):   # Initialize budget if none exists
        if not self.budget:
            budget = Budget(total_planned=0.0, total_spent=0.0, trip_id=self.id)
            db.session.add(budget)
            db.session.commit()
        return self.budget

    def add_expense(self, amount, category, description, shared_friends=None):     # Add new expense to budget, create budget if none exists
        if not self.budget:
            self.init_budget()

        expense = Expense(
            amount=amount,
            description=description,
            budget_id=self.budget.id,
            category=category
        )
        if shared_friends:
            for user in shared_friends:
                if user in User.query.all() and user not in expense.shared_users:
                    if user in self.participants:
                        expense.shared_users.append(user)
        self.budget.total_spent += amount  
        db.session.add(expense)
        db.session.commit()
        return expense

    def share_with(self, user):     # Share this trip with another user
        if user not in self.participants:
            self.participants.append(user)      # Add friend(user) as participant
            db.session.commit()

    def remove_participant(self, user):     # Remove a participant from this trip
        if user in self.participants:
            self.participants.remove(user)
            if not self.participants:   # If no participants left, delete the trip from database
                db.session.delete(self)
            db.session.commit()

    def get_participant_ids(self):   # Return list of user IDs participating in this trip
        return [user.id for user in self.participants]
    
    def delete_trip(self):      # Delete this trip and all related data (Composition)
        # Delete itinerary items
        for item in self.itinerary:
            db.session.delete(item)

        # Delete budget + expenses
        if self.budget:
            for expense in self.budget.expenses:
                db.session.delete(expense)
            db.session.delete(self.budget)

        # Finally delete the trip itself
        db.session.delete(self)
        db.session.commit()

    def delete_all_trips(self):   # Delete all trips of the user
        for trip in self.trips:
            trip.delete_trip()  
        db.session.commit()

    def add_destination(self, name: str):   # Encapsulated method to add a destination
        self.destinations.append(TripDestination(name=name))

    def __repr__(self):
        return f"<Trip {self.title}>"

#==========================================================================================================

class TripDestination(db.Model):
    # Attributes
    __tablename__ = "trip_destination"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(250), nullable=False)
    trip_id = db.Column(db.Integer, db.ForeignKey("trip.id"), nullable=False)

    
    def __repr__(self):
        return f"<Destination {self.name}>"

#==========================================================================================================

class ItineraryItem(db.Model):
    # Attributes
    __tablename__ = "itinerary_item"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    date = db.Column(db.Date, nullable=False)
    location = db.Column(db.String(150))
    notes = db.Column(db.Text)
    time = db.Column(db.Time)

    # Relationships
    trip_id = db.Column(db.Integer, db.ForeignKey("trip.id"), nullable=False)

    # Functions
    def update(self, title=None, date=None, location=None, notes=None, time=None):     # Update itinerary item details
        if title: self.title = title
        if date: self.date = date
        if location: self.location = location
        if notes: self.notes = notes
        if time: self.time = time
        db.session.commit()
        return self

    def delete(self):       # Delete this itinerary item
        db.session.delete(self)
        db.session.commit()

    def __repr__(self):
        return f"<ItineraryItem {self.title}>"

#==========================================================================================================

class Budget(db.Model):
    # Attributes
    __tablename__ = "budget"
    id = db.Column(db.Integer, primary_key=True)
    total_planned = db.Column(db.Float, default=0.0)
    total_spent = db.Column(db.Float, default=0.0)

    # Relationships
    trip_id = db.Column(db.Integer, db.ForeignKey("trip.id"), nullable=False)
    expenses = db.relationship("Expense", backref="budget", lazy=True, cascade="all, delete-orphan")
    planned_budgets = db.relationship("PlannedBudget", backref="budget", cascade="all, delete-orphan")

    # Functions
    def add_expense(self, amount, description, shared_with=None):
        expense = Expense(amount=amount, description=description, shared_with=shared_with, budget_id=self.id)
        self.total_spent += amount
        db.session.add(expense)
        db.session.commit()
        return expense
    
    def add_planned_budget(self, amount, category):
        planned_budget = PlannedBudget(amount=amount, category=category, budget_id=self.id)
        self.total_planned += amount
        db.session.add(planned_budget)
        db.session.commit()
        return planned_budget

    def calculate_remaining(self):  # Return remaining balance in budget
        return self.total_planned - self.total_spent
    
    def update_totals(self):   # Recalculate total planned and spent amounts
        self.total_planned = sum(pb.amount for pb in self.planned_budgets)
        self.total_spent = sum(exp.amount for exp in self.expenses)
        db.session.commit()

    def __repr__(self):
        return f"<Budget Planned={self.total_planned}, Spent={self.total_spent}>"

#==========================================================================================================
class PlannedBudget(db.Model):
    __tablename__ = "planned_budget"
    id = db.Column(db.Integer, primary_key=True)
    amount = db.Column(db.Float, nullable=False)
    category = db.Column(db.String(50), nullable=False)

    # Relationships
    budget_id = db.Column(db.Integer, db.ForeignKey("budget.id"), nullable=False)

    def update_budget(self, new_amount, new_category):   # Update planned budget amount
        self.amount = float(new_amount)
        self.category = new_category
        db.session.commit()
        self.budget.update_totals()
        return self

    def delete_planned_budget(self):   # Delete this planned budget
        db.session.delete(self)
        db.session.commit()
        self.budget.update_totals()

    def __repr__(self):
        return f"<PlannedBudget {self.category}: {self.amount}>"
#==========================================================================================================

class Expense(db.Model):
    # Attributes
    __tablename__ = "expense"
    id = db.Column(db.Integer, primary_key=True)
    amount = db.Column(db.Float, nullable=False)
    description = db.Column(db.String(200))
    category = db.Column(db.String(50), default="General") 
    status = db.Column(db.String(20), default="Unshared")  # Unshared, Shared, Accepted, Rejected 

    # Relationships
    budget_id = db.Column(db.Integer, db.ForeignKey("budget.id"), nullable=False)
    shared_users = db.relationship("User", secondary=expense_shared, backref="expenses_shared_with_me")

    # Functions
    def update_details(self, amount=None, description=None, category=None, shared_friends=None):   # Update this expense details
        if amount is not None:
            self.amount = float(amount)
        if description is not None:
            self.description = description
        if category is not None:
            self.category = category
        if shared_friends is not None:
            for user in shared_friends:
                if user in User.query.all() and user not in self.shared_users:
                    if user in self.budget.trip.participants:
                        self.shared_users.append(user)

        db.session.commit()
        self.budget.update_totals()
        return self
    
    def leave_expense(self, user):   # Remove a shared user from this expense
        if user in self.shared_users and user.id == session.get('user_id'): # You can only remove yourself
            self.shared_users.remove(user)
            db.session.commit()

        if not self.shared_users:   # If no shared users left, mark expense as Unshared
            db.session.delete(self)
            db.session.commit()
            # create logic if u want to remove someone else first notify them and then remove
        
    def remove_all_shared_users(self):   # Remove all shared users from this expense
        for user in self.shared_users:
            self.shared_users.remove(user)
        db.session.commit()

    def delete_expense(self):   # Delete this expense
        self.remove_all_shared_users()
        db.session.delete(self)
        db.session.commit()
        self.budget.update_totals()

    def split_with(self, usernames):    # Share this expense with other users(friends)
        self.shared_with = ",".join(usernames)
        self.status = "Pending"
        db.session.commit()
        return self

    def update_status(self, response):  # Update status of shared expense (Accepted / Rejected)
        self.status = response
        if response == "Rejected":
            self.shared_with = None
        db.session.commit()
        return self
    
    def __repr__(self):
        return f"<Expense {self.amount} - {self.description}>"
    
#==========================================================================================================


# <......WE NEED TO FIX THIS NOTIFICATION CLASS AND ITS INHERITORS LATER......>

# class NotificationService:
#     """Abstract parent class for all notifications."""

#     def __init__(self, sender, receiver, message):
#         self.sender = sender
#         self.receiver = receiver
#         self.message = message
#         self.status = "Pending"  # default for all notifications

#     def send(self):
#         raise NotImplementedError("Subclasses must implement this method")

#     def respond(self, response):
#         """Accept / Reject / Mark as Read."""
#         self.status = response
#         return self.status
    
#==========================================================================================================

# class ExpenseShareNotification(NotificationService):
#     def __init__(self, sender, receiver, expense):
#         message = f"{sender.username} wants to share expense '{expense.description}' with you."
#         super().__init__(sender, receiver, message)
#         self.expense = expense

#     def send(self):
#         # Logic to store in DB or notify user
#         print(f"Notification sent to {self.receiver.username}: {self.message}")

#==========================================================================================================

# class TripShareNotification(NotificationService):
#     def __init__(self, sender, receiver, trip):
#         message = f"{sender.username} wants to share trip '{trip.title}' with you."
#         super().__init__(sender, receiver, message)
#         self.trip = trip

#     def send(self):
#         # 🔹 For now just print, but you can later extend to DB storage
#         print(f"Notification sent to {self.receiver.username}: {self.message}")
#         # e.g. save to Notification table if you want persistence
