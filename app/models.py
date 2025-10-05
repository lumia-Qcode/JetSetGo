from app import db
from werkzeug.security import generate_password_hash, check_password_hash
from flask import session
from sqlalchemy.dialects.sqlite import JSON

# Association table (no class, just a raw table)
trip_users = db.Table(
    "trip_users",
    db.Column("user_id", db.Integer, db.ForeignKey("user.id"), primary_key=True),
    db.Column("trip_id", db.Integer, db.ForeignKey("trip.id"), primary_key=True)
)

class User(db.Model):
    # Attributes
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key = True)
    username = db.Column(db.String(100), nullable = False)
    email = db.Column(db.String(100), unique = True, nullable = False)
    password = db.Column(db.String(200), nullable = False)


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
    
    def login(self):    
        session['user_id'] = self.id
        session['user_email'] = self.email
        session['user_name'] = self.username

    @staticmethod
    def logout():
        session.pop('user_id', None)
        session.pop('user_name', 'None')
        session.pop('user_email', 'None')

    def __repr__(self):
        return f"<User {self.username}>"


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
    def clear_user_tasks(cls, user_id): # Delete all Tasks of this User
        cls.query.filter_by(user_id = user_id).delete()
        db.session.commit()


class Trip(db.Model):
    # Attributes
    __tablename__ = "trip"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    destination = db.Column(db.String(150), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    description = db.Column(db.Text, nullable=True)

    # Relationships
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    itinerary = db.relationship("ItineraryItem", backref="trip", lazy=True, cascade="all, delete-orphan")
    budget = db.relationship("Budget", backref="trip", uselist=False, cascade="all, delete-orphan")
    participants = db.relationship("User", secondary=trip_users, backref=db.backref("trips", lazy="dynamic"))

    # Functions 

    @classmethod
    def create(cls, title, destination, start_date, end_date, description, user_id):
        trip = cls(
            title=title,
            destination=destination,
            start_date=start_date,
            end_date=end_date,
            description=description,
            user_id=user_id
        )
        db.session.add(trip)
        db.session.commit()
        return trip
    
    def update_details(self, title=None, destination=None, start_date=None, end_date=None, description=None):
        """Update trip details."""
        if title: 
            self.title = title
        if destination: 
            self.destination = destination
        if start_date: 
            self.start_date = start_date
        if end_date: 
            self.end_date = end_date
        if description is not None: 
            self.description = description

        db.session.commit()
        return self


    def add_itinerary_item(self, title, date, location=None, notes=None):
        item = ItineraryItem(title=title, date=date, location=location, notes=notes, trip_id=self.id)
        db.session.add(item)
        db.session.commit()
        return item

    def init_budget(self, category="General"):
        if not self.budget:
            budget = Budget(total_planned=0.0, total_spent=0.0, category=category, trip_id=self.id)
            db.session.add(budget)
            db.session.commit()
        return self.budget

    def add_expense(self, amount, category, description, shared_with=None):
        if not self.budget:
            self.init_budget(category=category)

        expense = Expense(
            amount=amount,
            description=description,
            shared_with=",".join(shared_with) if shared_with else None,
            budget_id=self.budget.id
        )
        self.budget.total_spent += amount
        db.session.add(expense)
        db.session.commit()
        return expense

    def share_with(self, user):
        """Add user to trip participants"""
        if user not in self.participants:
            self.participants.append(user)
            db.session.commit()

    def remove_participant(self, user):
        if user in self.participants:
            self.participants.remove(user)
            if not self.participants:  # no one left
                db.session.delete(self)
            db.session.commit()

    def is_participant(self, user):
        return user in self.participants
    
    def delete_trip(self):
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

    def delete_all_trips(self):
        """Delete all trips and their related data for this user."""
        for trip in self.trips:
            trip.delete_trip()  # uses Trip.delete_trip to clean itinerary, budget, expenses

        db.session.commit()

    def __repr__(self):
        return f"<Trip {self.title} to {self.destination}>"


class ItineraryItem(db.Model):
    # Attributes
    __tablename__ = "itinerary_item"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    date = db.Column(db.Date, nullable=False)
    location = db.Column(db.String(150))
    notes = db.Column(db.Text)

    # Relationships
    trip_id = db.Column(db.Integer, db.ForeignKey("trip.id"), nullable=False)

    # Functions

    def update(self, title=None, date=None, location=None, notes=None):
        if title: self.title = title
        if date: self.date = date
        if location: self.location = location
        if notes: self.notes = notes
        db.session.commit()
        return self

    def delete(self):
        db.session.delete(self)
        db.session.commit()

    def __repr__(self):
        return f"<ItineraryItem {self.title} on {self.date}>"


class Budget(db.Model):
    # Attributes
    __tablename__ = "budget"
    id = db.Column(db.Integer, primary_key=True)
    total_planned = db.Column(db.Float, default=0.0)
    total_spent = db.Column(db.Float, default=0.0)
    category = db.Column(db.String(50), nullable=False) 

    # Relationships
    trip_id = db.Column(db.Integer, db.ForeignKey("trip.id"), nullable=False)
    expenses = db.relationship("Expense", backref="budget", lazy=True, cascade="all, delete-orphan")

    # Functions
    def add_expense(self, amount, description, shared_with=None):
        expense = Expense(amount=amount, description=description, shared_with=shared_with, budget_id=self.id)
        self.total_spent += amount
        db.session.add(expense)
        db.session.commit()
        return expense

    def calculate_remaining(self):
        return self.total_planned - self.total_spent
    
    def __repr__(self):
        return f"<Budget Planned={self.total_planned}, Spent={self.total_spent}>"

class Expense(db.Model):
    # Attributes
    __tablename__ = "expense"
    id = db.Column(db.Integer, primary_key=True)
    amount = db.Column(db.Float, nullable=False)
    description = db.Column(db.String(200))
    shared_with = db.Column(db.String(200))
    status = db.Column(db.String(20), default="Unshared")  # Unshared, Shared, Accepted, Rejected 

    # Relationships
    budget_id = db.Column(db.Integer, db.ForeignKey("budget.id"), nullable=False)

    # Functions
    def update_details(self, amount=None, description=None, shared_with=None):
        """Update an expense details."""
        if amount is not None:
            self.amount = float(amount)
        if description is not None:
            self.description = description
        if shared_with is not None:
            self.shared_with = shared_with

        db.session.commit()
        return self

    def delete_expense(self):
        """Delete this expense from DB."""
        db.session.delete(self)
        db.session.commit()

    def split_with(self, usernames):
        self.shared_with = ",".join(usernames)
        self.status = "Pending"
        db.session.commit()
        return self

    def update_status(self, response):
        self.status = response
        if response == "Rejected":
            self.shared_with = None
        db.session.commit()
        return self
    
    def __repr__(self):
        return f"<Expense {self.amount} - {self.description}>"
    

class NotificationService:
    """Abstract parent class for all notifications."""

    def __init__(self, sender, receiver, message):
        self.sender = sender
        self.receiver = receiver
        self.message = message
        self.status = "Pending"  # default for all notifications

    def send(self):
        raise NotImplementedError("Subclasses must implement this method")

    def respond(self, response):
        """Accept / Reject / Mark as Read."""
        self.status = response
        return self.status
    

class ExpenseShareNotification(NotificationService):
    def __init__(self, sender, receiver, expense):
        message = f"{sender.username} wants to share expense '{expense.description}' with you."
        super().__init__(sender, receiver, message)
        self.expense = expense

    def send(self):
        # Logic to store in DB or notify user
        print(f"Notification sent to {self.receiver.username}: {self.message}")


class TripShareNotification(NotificationService):
    def __init__(self, sender, receiver, trip):
        message = f"{sender.username} wants to share trip '{trip.title}' with you."
        super().__init__(sender, receiver, message)
        self.trip = trip

    def send(self):
        # 🔹 For now just print, but you can later extend to DB storage
        print(f"Notification sent to {self.receiver.username}: {self.message}")
        # e.g. save to Notification table if you want persistence
