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
trip_users = db.Table(
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

# Association table (Many to Many) between Users and Favorite Destinations
user_favorite_destinations = db.Table(
    "user_favorite_destinations",
    db.Column("user_id", db.Integer, db.ForeignKey("user.id"), primary_key=True),
    db.Column("destination_id", db.Integer, db.ForeignKey("favorite_destination.id"), primary_key=True),
    db.Column("added_at", db.DateTime, default=datetime.utcnow)
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
        token = secrets.token_urlsafe(32)
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
        if not self.is_valid():
            raise ValueError("Token is invalid or expired.")

        self.user.password = generate_password_hash(new_password)
        self.mark_as_used()
        db.session.commit()

    def send_email(to_email, subject, body):
        msg = Message(subject=subject, recipients=[to_email], body=body, sender=current_app.config['MAIL_USERNAME'])
        mail.send(msg)

#==========================================================================================================

class User(db.Model):
    # Attributes
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)

    # Relationships
    shared_expenses = db.relationship("Expense", secondary=expense_shared, backref="users_shared")
    favorite_destinations = db.relationship(
        "FavoriteDestination", 
        secondary=user_favorite_destinations, 
        backref=db.backref("users_who_favorited", lazy="dynamic")
    )
    reviews = db.relationship("Review", backref="user", lazy=True, cascade="all, delete-orphan")

    # Functions
    @classmethod
    def register(cls, username, email, password):
        if cls.query.filter_by(email=email).first():
            return None
        
        hashed_password = generate_password_hash(password)
        user = cls(username=username, email=email, password=hashed_password)
        db.session.add(user)
        db.session.commit()
        return user
    
    @classmethod
    def authenticate(cls, email, password):
        user = cls.query.filter_by(email=email).first()
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

    def add_favorite_destination(self, name, country=None, description=None, image_url=None):
        """Add a destination to user's favorites"""
        # Check if destination already exists
        destination = FavoriteDestination.query.filter_by(name=name).first()
        
        if not destination:
            destination = FavoriteDestination(
                name=name,
                country=country,
                description=description,
                image_url=image_url
            )
            db.session.add(destination)
            db.session.flush()
        
        # Check if user already has this destination favorited
        if destination not in self.favorite_destinations:
            self.favorite_destinations.append(destination)
            db.session.commit()
            return destination
        return None

    def remove_favorite_destination(self, destination):
        """Remove a destination from user's favorites"""
        if destination in self.favorite_destinations:
            self.favorite_destinations.remove(destination)
            db.session.commit()
            return True
        return False

    def is_destination_favorited(self, destination_name):
        """Check if a destination is in user's favorites"""
        return any(dest.name.lower() == destination_name.lower() for dest in self.favorite_destinations)

    def get_favorite_destinations(self):
        """Get all favorite destinations for this user"""
        return self.favorite_destinations

    def __repr__(self):
        return f"<User {self.username}>"

#==========================================================================================================

class FavoriteDestination(db.Model):
    """Represents a destination that users can favorite"""
    __tablename__ = "favorite_destination"
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(250), nullable=False, unique=True)
    country = db.Column(db.String(100))
    description = db.Column(db.Text)
    image_url = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def update_details(self, name=None, country=None, description=None, image_url=None):
        """Update destination details"""
        if name:
            self.name = name
        if country:
            self.country = country
        if description:
            self.description = description
        if image_url:
            self.image_url = image_url
        db.session.commit()
        return self

    def get_favorite_count(self):
        """Get the number of users who favorited this destination"""
        return self.users_who_favorited.count()

    @classmethod
    def get_popular_destinations(cls, limit=10):
        """Get most favorited destinations"""
        destinations = cls.query.all()
        sorted_destinations = sorted(
            destinations, 
            key=lambda d: d.get_favorite_count(), 
            reverse=True
        )
        return sorted_destinations[:limit]

    @classmethod
    def search_destinations(cls, query):
        """Search destinations by name or country"""
        return cls.query.filter(
            db.or_(
                cls.name.ilike(f"%{query}%"),
                cls.country.ilike(f"%{query}%")
            )
        ).all()

    def __repr__(self):
        return f"<FavoriteDestination {self.name}>"

#==========================================================================================================

class Task(db.Model):
    # Attributes
    __tablename__ = 'task'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    due_date = db.Column(db.Date, nullable=True)
    due_time = db.Column(db.Time, nullable=True)
    status = db.Column(db.String(20), default="Pending")
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))

    # Functions
    @classmethod
    def create(cls, title, user_id, due_date, due_time):
        task = cls(title=title, user_id=user_id, due_date=due_date, due_time=due_time)
        db.session.add(task)
        db.session.commit()
        return task
    
    def update(self, title=None, due_date=None, due_time=None):
        if title: self.title = title
        if due_date: self.due_date = due_date
        if due_time: self.due_time = due_time
        db.session.commit()
        return self
    
    def toggle_status(self):
        if self.status == 'Pending':
            self.status = 'Working'
        elif self.status == 'Working':
            self.status = 'Done'
        else:
            self.status = 'Pending'
        db.session.commit()

    def delete(self):
        db.session.delete(self)
        db.session.commit()

    @classmethod
    def clear_user_tasks(cls, user_id):
        cls.query.filter_by(user_id=user_id).delete()
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
    reviews = db.relationship("Review", backref="trip", lazy=True, cascade="all, delete-orphan")

    # Functions 
    @classmethod
    def create(cls, title, destinations, start_date, end_date, description, participant):
        trip = cls(
            title=title,
            start_date=start_date,
            end_date=end_date,
            description=description
        )
        db.session.add(trip)
        db.session.flush()

        for dest in destinations:
            if dest.strip():
                trip.destinations.append(TripDestination(name=dest.strip()))

        trip.participants.append(participant)
        db.session.commit()
        return trip
    
    def update_details(self, title=None, destinations=None, start_date=None, end_date=None, description=None):
        if title: 
            self.title = title
        if destinations:
            self.destinations = []
            for dest in destinations:
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

    def add_itinerary_item(self, title, date, location=None, notes=None, time=None):
        item = ItineraryItem(title=title, date=date, location=location, notes=notes, time=time, trip_id=self.id)
        db.session.add(item)
        db.session.commit()
        return item

    def init_budget(self):
        if not self.budget:
            budget = Budget(total_planned=0.0, total_spent=0.0, trip_id=self.id)
            db.session.add(budget)
            db.session.commit()
        return self.budget

    def add_expense(self, amount, category, description, shared_friends=None):
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

    def share_with(self, user):
        if user not in self.participants:
            self.participants.append(user)
            db.session.commit()

    def remove_participant(self, user):
        if user in self.participants:
            self.participants.remove(user)
            if not self.participants:
                db.session.delete(self)
            db.session.commit()

    def get_participant_ids(self):
        return [user.id for user in self.participants]
    
    def delete_trip(self):
        for item in self.itinerary:
            db.session.delete(item)

        if self.budget:
            for expense in self.budget.expenses:
                db.session.delete(expense)
            db.session.delete(self.budget)

        db.session.delete(self)
        db.session.commit()

    def delete_all_trips(self):
        for trip in self.trips:
            trip.delete_trip()  
        db.session.commit()

    def add_destination(self, name: str):
        self.destinations.append(TripDestination(name=name))

    def get_average_rating(self):
        """Calculate average rating for this trip"""
        if not self.reviews:
            return 0
        total = sum(review.rating for review in self.reviews)
        return round(total / len(self.reviews), 1)

    def get_review_count(self):
        """Get total number of reviews"""
        return len(self.reviews)

    def __repr__(self):
        return f"<Trip {self.title}>"

#==========================================================================================================

class TripDestination(db.Model):
    # Attributes
    __tablename__ = "trip_destination"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(250), nullable=False)
    trip_id = db.Column(db.Integer, db.ForeignKey("trip.id"), nullable=False)
    is_favorited = db.Column(db.Boolean, default=False)  # Track if this destination is favorited
    
    def mark_as_favorite(self, user):
        """Mark this trip destination as favorite and add to user's favorites"""
        self.is_favorited = True
        user.add_favorite_destination(self.name)
        db.session.commit()
        return self

    def unmark_as_favorite(self, user):
        """Unmark this trip destination as favorite"""
        self.is_favorited = False
        # Find the favorite destination and remove it from user's favorites
        fav_dest = FavoriteDestination.query.filter_by(name=self.name).first()
        if fav_dest:
            user.remove_favorite_destination(fav_dest)
        db.session.commit()
        return self

    def toggle_favorite(self, user):
        """Toggle favorite status for this destination"""
        if self.is_favorited:
            return self.unmark_as_favorite(user)
        else:
            return self.mark_as_favorite(user)

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
    def update(self, title=None, date=None, location=None, notes=None, time=None):
        if title: self.title = title
        if date: self.date = date
        if location: self.location = location
        if notes: self.notes = notes
        if time: self.time = time
        db.session.commit()
        return self

    def delete(self):
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

    def calculate_remaining(self):
        return self.total_planned - self.total_spent
    
    def update_totals(self):
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

    def update_budget(self, new_amount, new_category):
        self.amount = float(new_amount)
        self.category = new_category
        db.session.commit()
        self.budget.update_totals()
        return self

    def delete_planned_budget(self):
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
    status = db.Column(db.String(20), default="Unshared")

    # Relationships
    budget_id = db.Column(db.Integer, db.ForeignKey("budget.id"), nullable=False)
    shared_users = db.relationship("User", secondary=expense_shared, backref="expenses_shared_with_me")

    # Functions
    def update_details(self, amount=None, description=None, category=None, shared_friends=None):
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
    
    def leave_expense(self, user):
        if user in self.shared_users and user.id == session.get('user_id'):
            self.shared_users.remove(user)
            db.session.commit()

        if not self.shared_users:
            db.session.delete(self)
            db.session.commit()
        
    def remove_all_shared_users(self):
        for user in self.shared_users:
            self.shared_users.remove(user)
        db.session.commit()

    def delete_expense(self):
        self.remove_all_shared_users()
        db.session.delete(self)
        db.session.commit()
        self.budget.update_totals()

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

#==========================================================================================================

class Review(db.Model):
    """Trip reviews with ratings"""
    __tablename__ = "review"
    
    id = db.Column(db.Integer, primary_key=True)
    rating = db.Column(db.Integer, nullable=False)  # 1-5 stars
    comment = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    trip_id = db.Column(db.Integer, db.ForeignKey("trip.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    
    # Unique constraint: one review per user per trip
    __table_args__ = (db.UniqueConstraint('trip_id', 'user_id', name='unique_trip_user_review'),)
    
    @classmethod
    def create(cls, trip_id, user_id, rating, comment=None):
        """Create a new review"""
        if rating < 1 or rating > 5:
            raise ValueError("Rating must be between 1 and 5")
        
        review = cls(
            trip_id=trip_id,
            user_id=user_id,
            rating=rating,
            comment=comment
        )
        db.session.add(review)
        db.session.commit()
        return review
    
    def update(self, rating=None, comment=None):
        """Update review details"""
        if rating is not None:
            if rating < 1 or rating > 5:
                raise ValueError("Rating must be between 1 and 5")
            self.rating = rating
        if comment is not None:
            self.comment = comment
        self.updated_at = datetime.utcnow()
        db.session.commit()
        return self
    
    def delete(self):
        """Delete review"""
        db.session.delete(self)
        db.session.commit()
    
    def get_star_display(self):
        """Get star display string"""
        return "★" * self.rating + "☆" * (5 - self.rating)
    
    def __repr__(self):
        return f"<Review Trip:{self.trip_id} User:{self.user_id} Rating:{self.rating}>"