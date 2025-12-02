from datetime import datetime, timedelta
import secrets
from werkzeug.security import generate_password_hash, check_password_hash
from flask import session, current_app
from flask_mail import Message

from app import db, mail

# ----------------------------
# Association tables
# ----------------------------
post_likes = db.Table(
    "post_likes",
    db.Column("user_id", db.Integer, db.ForeignKey("user.id"), primary_key=True),
    db.Column("post_id", db.Integer, db.ForeignKey("post.id"), primary_key=True)
)

trip_users = db.Table(
    "trip_users",
    db.Column("user_id", db.Integer, db.ForeignKey("user.id"), primary_key=True),
    db.Column("trip_id", db.Integer, db.ForeignKey("trip.id"), primary_key=True)
)

expense_shared = db.Table(
    "expense_shared",
    db.Column("expense_id", db.Integer, db.ForeignKey("expense.id"), primary_key=True),
    db.Column("user_id", db.Integer, db.ForeignKey("user.id"), primary_key=True)
)

user_favorite_destinations = db.Table(
    "user_favorite_destinations",
    db.Column("user_id", db.Integer, db.ForeignKey("user.id"), primary_key=True),
    db.Column("destination_id", db.Integer, db.ForeignKey("favorite_destination.id"), primary_key=True),
    db.Column("added_at", db.DateTime, default=datetime.utcnow)
)

# ----------------------------
# Models (fields + thin compatibility methods)
# ----------------------------

class UserStats(db.Model):
    __tablename__ = "user_stats"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), unique=True, nullable=False)
    total_xp = db.Column(db.Integer, default=0)
    tasks_completed = db.Column(db.Integer, default=0)
    theme = db.Column(db.String(10), default="dark")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = db.relationship("User", backref=db.backref("stats", uselist=False))
    badges = db.relationship("Badge", backref="user_stats", lazy=True, cascade="all, delete-orphan")

    # Compatibility methods delegate to StatsService
    def add_xp(self, amount=10):
        return StatsService.add_xp(self, amount)

    def increment_tasks(self):
        return StatsService.complete_task(self)

    def get_level(self):
        return StatsService.get_level(self)

    def get_level_progress(self):
        return StatsService.get_level_progress(self)

    def check_and_award_badges(self):
        return BadgeService.award_badges_for_tasks(self)

    def set_theme(self, theme):
        return StatsService.set_theme(self, theme)

    def __repr__(self):
        return f"<UserStats User:{self.user_id} XP:{self.total_xp} Level:{self.get_level()}>"


class Badge(db.Model):
    __tablename__ = "badge"
    id = db.Column(db.Integer, primary_key=True)
    user_stats_id = db.Column(db.Integer, db.ForeignKey("user_stats.id"), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    icon = db.Column(db.String(10), nullable=False)
    description = db.Column(db.String(250), nullable=False)
    threshold = db.Column(db.Integer, nullable=False)
    earned_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Badge {self.name}>"


class Post(db.Model):
    __tablename__ = "post"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    content = db.Column(db.Text, nullable=False)
    image_url = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = db.relationship("User", backref=db.backref("posts", lazy=True, cascade="all, delete-orphan"))
    comments = db.relationship("Comment", backref="post", lazy=True, cascade="all, delete-orphan")
    likes = db.relationship("User", secondary=post_likes, backref=db.backref("liked_posts", lazy=True))

    # Keep compatibility: these methods preserve original names and high-level behaviour
    @classmethod
    def create(cls, user_id, content, image_url=None):
        return PostService.create_post(user_id, content, image_url)

    def add_like(self, user):
        return PostService.add_like(self, user)

    def remove_like(self, user):
        return PostService.remove_like(self, user)

    def toggle_like(self, user):
        return PostService.toggle_like(self, user)

    def get_like_count(self):
        return len(self.likes)

    def is_liked_by(self, user):
        return user in self.likes

    def update_content(self, content):
        return PostService.update_post(self, content)

    def delete(self):
        return PostService.delete_post(self)

    def __repr__(self):
        return f"<Post {self.id} by User:{self.user_id}>"


class Comment(db.Model):
    __tablename__ = "comment"
    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey("post.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = db.relationship("User", backref=db.backref("comments", lazy=True, cascade="all, delete-orphan"))

    @classmethod
    def create(cls, post_id, user_id, content):
        return CommentService.create_comment(post_id, user_id, content)

    def update(self, content):
        return CommentService.update_comment(self, content)

    def delete(self):
        return CommentService.delete_comment(self)

    def __repr__(self):
        return f"<Comment {self.id} on Post:{self.post_id}>"


class User(db.Model):
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)

    shared_expenses = db.relationship("Expense", secondary=expense_shared, backref="users_shared")
    favorite_destinations = db.relationship(
        "FavoriteDestination",
        secondary=user_favorite_destinations,
        backref=db.backref("users_who_favorited", lazy="dynamic")
    )
    reviews = db.relationship("Review", backref="user", lazy=True, cascade="all, delete-orphan")

    # Preserve original APIs but delegate to services
    @classmethod
    def register(cls, username, email, password):
        return AuthService.register(username, email, password)

    def ensure_stats(self):
        return ensure_user_stats(self)

    @classmethod
    def authenticate(cls, email, password):
        return AuthService.authenticate(email, password)

    def login(self):
        # Keep session behaviour (web-layer responsibility) but keep minimal coupling
        session['user_id'] = self.id
        session['user_email'] = self.email
        session['user_name'] = self.username

    @staticmethod
    def logout():
        session.pop('user_id', None)
        session.pop('user_name', None)
        session.pop('user_email', None)

    def add_favorite_destination(self, name, country=None, description=None, image_url=None):
        return FavoriteService.add_favorite_destination(self, name, country, description, image_url)

    def remove_favorite_destination(self, destination):
        return FavoriteService.remove_favorite_destination(self, destination)

    def is_destination_favorited(self, destination_name):
        return FavoriteService.is_favorited(self, destination_name)

    def get_favorite_destinations(self):
        return FavoriteService.get_favorites(self)

    def __repr__(self):
        return f"<User {self.username}>"


class PasswordResetToken(db.Model):
    __tablename__ = "password_reset_tokens"
    id = db.Column(db.Integer, primary_key=True)
    token = db.Column(db.String(100), unique=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=False)
    used = db.Column(db.Boolean, default=False)

    user = db.relationship("User", backref=db.backref("reset_tokens", lazy=True))

    # Compatibility delegations
    @classmethod
    def generate_token(cls, user, expires_in=3600):
        prt = PasswordResetService.generate_token_for_user(user, expires_in)
        return prt.token

    def is_valid(self):
        return PasswordResetService.validate_token_instance(self)

    def mark_as_used(self):
        return PasswordResetService.mark_token_used(self)

    def reset_password(self, new_password):
        return PasswordResetService.consume_token_and_reset(self, new_password)

    def send_email(self, to_email, subject, body):
        return PasswordResetService.send_reset_email(to_email, subject, body)

    def __repr__(self):
        return f"<PasswordResetToken user:{self.user_id} used:{self.used}>"


class FavoriteDestination(db.Model):
    __tablename__ = "favorite_destination"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(250), nullable=False, unique=True)
    country = db.Column(db.String(100))
    description = db.Column(db.Text)
    image_url = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def update_details(self, name=None, country=None, description=None, image_url=None):
        return FavoriteService.update_details(self, name, country, description, image_url)

    def get_favorite_count(self):
        return FavoriteService.get_favorite_count(self)

    @classmethod
    def get_popular_destinations(cls, limit=10):
        return FavoriteService.get_popular_destinations(limit)

    @classmethod
    def search_destinations(cls, query):
        return FavoriteService.search_destinations(query)

    def __repr__(self):
        return f"<FavoriteDestination {self.name}>"


class Task(db.Model):
    __tablename__ = 'task'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    due_date = db.Column(db.Date, nullable=True)
    due_time = db.Column(db.Time, nullable=True)
    status = db.Column(db.String(20), default="Pending")
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    due_today_notified = db.Column(db.Boolean, default=False)
    overdue_notified = db.Column(db.Boolean, default=False)

    @classmethod
    def create(cls, title, user_id, due_date=None, due_time=None, due_today_notified=False, overdue_notified=False):
        return TaskService.create_task(title, user_id, due_date, due_time, due_today_notified, overdue_notified)

    def update(self, title=None, due_date=None, due_time=None):
        return TaskService.update_task(self, title, due_date, due_time)

    def toggle_status(self):
        return TaskService.toggle_status(self)

    def delete(self):
        return TaskService.delete_task(self)

    @classmethod
    def clear_user_tasks(cls, user_id):
        return TaskService.clear_user_tasks(user_id)

    def __repr__(self):
        return f"<Task {self.title} ({self.status})>"


class Trip(db.Model):
    __tablename__ = 'trip'
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
    itinerary = db.relationship("ItineraryItem", backref="trip", lazy=True, cascade="all, delete-orphan")
    budget = db.relationship("Budget", backref="trip", uselist=False, cascade="all, delete-orphan")
    participants = db.relationship("User", secondary=trip_users, backref=db.backref("trips", lazy="dynamic"))
    reviews = db.relationship("Review", backref="trip", lazy=True, cascade="all, delete-orphan")

    @classmethod
    def create(cls, title, destinations, start_date, end_date, description, participant):
        return TripService.create_trip(title, destinations, start_date, end_date, description, participant)

    def update_details(self, title=None, destinations=None, start_date=None, end_date=None, description=None):
        return TripService.update_trip(self, title, destinations, start_date, end_date, description)

    def add_itinerary_item(self, title, date, location=None, notes=None, time=None):
        return TripService.add_itinerary_item(self, title, date, location, notes, time)

    def init_budget(self):
        return BudgetService.init_budget_for_trip(self)

    def add_expense(self, amount, category, description, shared_friends=None):
        actor_id = session.get("user_id")
        return ExpenseService.add_expense(self, amount, category, description, shared_friends, actor_user_id=actor_id)

    def share_with(self, user):
        return TripService.add_participant(self, user)

    def remove_participant(self, user):
        return TripService.remove_participant(self, user)

    def get_participant_ids(self):
        return [user.id for user in self.participants]

    def delete_trip(self):
        return TripService.delete_trip(self)

    def delete_all_trips(self):
        # kept for compatibility; operates on self's owner's trips if needed at service layer
        return TripService.delete_all_trips(self)

    def add_destination(self, name: str):
        return TripService.add_destination(self, name)

    def get_average_rating(self):
        return TripService.get_average_rating(self)

    def get_review_count(self):
        return len(self.reviews)

    def __repr__(self):
        return f"<Trip {self.title}>"


class TripDestination(db.Model):
    __tablename__ = "trip_destination"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(250), nullable=False)
    trip_id = db.Column(db.Integer, db.ForeignKey("trip.id"), nullable=False)
    is_favorited = db.Column(db.Boolean, default=False)

    def mark_as_favorite(self, user):
        return FavoriteService.mark_trip_destination_as_favorite(self, user)

    def unmark_as_favorite(self, user):
        return FavoriteService.unmark_trip_destination_as_favorite(self, user)

    def toggle_favorite(self, user):
        return FavoriteService.toggle_trip_destination_favorite(self, user)

    def __repr__(self):
        return f"<Destination {self.name}>"


class ItineraryItem(db.Model):
    __tablename__ = "itinerary_item"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    date = db.Column(db.Date, nullable=False)
    location = db.Column(db.String(150))
    notes = db.Column(db.Text)
    time = db.Column(db.Time)

    trip_id = db.Column(db.Integer, db.ForeignKey("trip.id"), nullable=False)

    def update(self, title=None, date=None, location=None, notes=None, time=None):
        return ItineraryService.update_item(self, title, date, location, notes, time)

    def delete(self):
        return ItineraryService.delete_item(self)

    def __repr__(self):
        return f"<ItineraryItem {self.title}>"


class Budget(db.Model):
    __tablename__ = "budget"
    id = db.Column(db.Integer, primary_key=True)
    total_planned = db.Column(db.Float, default=0.0)
    total_spent = db.Column(db.Float, default=0.0)

    trip_id = db.Column(db.Integer, db.ForeignKey("trip.id"), nullable=False)
    expenses = db.relationship("Expense", backref="budget", lazy=True, cascade="all, delete-orphan")
    planned_budgets = db.relationship("PlannedBudget", backref="budget", cascade="all, delete-orphan")

    def add_expense(self, amount, description, shared_with=None):
        return BudgetService.add_expense(self, amount, description, shared_with)

    def add_planned_budget(self, amount, category):
        return BudgetService.add_planned_budget(self, amount, category)

    def calculate_remaining(self):
        return self.total_planned - self.total_spent

    def update_totals(self):
        return BudgetService.recalculate(self)

    def __repr__(self):
        return f"<Budget Planned={self.total_planned}, Spent={self.total_spent}>"


class PlannedBudget(db.Model):
    __tablename__ = "planned_budget"
    id = db.Column(db.Integer, primary_key=True)
    amount = db.Column(db.Float, nullable=False)
    category = db.Column(db.String(50), nullable=False)
    budget_id = db.Column(db.Integer, db.ForeignKey("budget.id"), nullable=False)

    def update_budget(self, new_amount, new_category):
        return BudgetService.update_planned_budget(self, new_amount, new_category)

    def delete_planned_budget(self):
        return BudgetService.delete_planned_budget(self)

    def __repr__(self):
        return f"<PlannedBudget {self.category}: {self.amount}>"


class Expense(db.Model):
    __tablename__ = "expense"
    id = db.Column(db.Integer, primary_key=True)
    amount = db.Column(db.Float, nullable=False)
    description = db.Column(db.String(200))
    category = db.Column(db.String(50), default="General")
    status = db.Column(db.String(20), default="Unshared")

    budget_id = db.Column(db.Integer, db.ForeignKey("budget.id"), nullable=False)
    shared_users = db.relationship("User", secondary=expense_shared, backref="expenses_shared_with_me")

    def update_details(self, amount=None, description=None, category=None, shared_friends=None):
        actor_id = session.get('user_id')
        return ExpenseService.update_expense(self, amount, description, category, shared_friends, actor_user_id=actor_id)

    def leave_expense(self, user):
        return ExpenseService.leave_expense(self, user)

    def remove_all_shared_users(self):
        return ExpenseService.remove_all_shared_users(self)

    def delete_expense(self):
        return ExpenseService.delete_expense(self)

    def __repr__(self):
        return f"<Expense {self.amount} - {self.description}>"


class Review(db.Model):
    __tablename__ = "review"
    id = db.Column(db.Integer, primary_key=True)
    rating = db.Column(db.Integer, nullable=False)
    comment = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    trip_id = db.Column(db.Integer, db.ForeignKey("trip.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    photos = db.relationship("ReviewPhoto", backref="review", lazy=True, cascade="all, delete-orphan")

    __table_args__ = (db.UniqueConstraint('trip_id', 'user_id', name='unique_trip_user_review'),)

    @classmethod
    def create(cls, trip_id, user_id, rating, comment=None):
        return ReviewService.create_review(trip_id, user_id, rating, comment)

    def update(self, rating=None, comment=None):
        return ReviewService.update_review(self, rating, comment)

    def delete(self):
        return ReviewService.delete_review(self)

    def add_photo(self, photo_url, caption=None):
        return ReviewService.add_photo(self, photo_url, caption)

    def get_star_display(self):
        return ReviewService.get_star_display(self)

    def __repr__(self):
        return f"<Review Trip:{self.trip_id} User:{self.user_id} Rating:{self.rating}>"


class ReviewPhoto(db.Model):
    __tablename__ = "review_photo"
    id = db.Column(db.Integer, primary_key=True)
    photo_url = db.Column(db.String(500), nullable=False)
    caption = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    review_id = db.Column(db.Integer, db.ForeignKey("review.id"), nullable=False)

    def delete(self):
        return ReviewService.delete_photo(self)

    def __repr__(self):
        return f"<ReviewPhoto {self.id} for Review {self.review_id}>"


class Notification(db.Model):
    __tablename__ = "notification"
    id = db.Column(db.Integer, primary_key=True)
    receiver_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    sender_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    type = db.Column(db.String(50), nullable=False)
    message = db.Column(db.String(300), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_read = db.Column(db.Boolean, default=False)
    trip_id = db.Column(db.Integer, db.ForeignKey("trip.id"), nullable=True)
    expense_id = db.Column(db.Integer, nullable=True)

    receiver = db.relationship("User", foreign_keys=[receiver_id], backref="notifications_received")
    sender = db.relationship("User", foreign_keys=[sender_id], backref="notifications_sent")

    @classmethod
    def send(cls, receiver_id, sender_id=None, type=None, message=None, trip_id=None, expense_id=None):
        return NotificationService.send(receiver_id, sender_id, type, message, trip_id, expense_id)

    @classmethod
    def unread_count(cls, user_id):
        return NotificationService.unread_count(user_id)

    def __repr__(self):
        return f"<Notification to:{self.receiver_id} type:{self.type}>"

# ----------------------------
# Services (business logic moved here)
# ----------------------------

class NotificationService:
    @staticmethod
    def send(receiver_id, sender_id, type_, message, trip_id=None, expense_id=None):
        notif = Notification(
            receiver_id=receiver_id,
            sender_id=sender_id,
            type=type_,
            message=message,
            trip_id=trip_id,
            expense_id=expense_id
        )
        db.session.add(notif)
        db.session.commit()
        return notif

    @staticmethod
    def unread_count(user_id):
        return Notification.query.filter_by(receiver_id=user_id, is_read=False).count()


class BadgeService:
    DEFAULT_RULES = [
        (5, "Task Starter", "🎯", "Completed 5 tasks"),
        (10, "Task Master", "🏆", "Completed 10 tasks"),
        (25, "Task Legend", "👑", "Completed 25 tasks"),
        (50, "Ultimate Traveler", "✈️", "Completed 50 tasks"),
    ]

    @classmethod
    def award_badges_for_tasks(cls, user_stats):
        new_badges = []
        for threshold, name, icon, description in cls.DEFAULT_RULES:
            exists = Badge.query.filter_by(user_stats_id=user_stats.id, name=name).first()
            if not exists and user_stats.tasks_completed >= threshold:
                badge = Badge(user_stats_id=user_stats.id, name=name, icon=icon, description=description, threshold=threshold)
                db.session.add(badge)
                new_badges.append(badge)
        if new_badges:
            db.session.commit()
        return new_badges


class StatsService:
    XP_PER_TASK = 10

    @staticmethod
    def add_xp(user_stats, amount=10):
        user_stats.total_xp += int(amount)
        user_stats.updated_at = datetime.utcnow()
        db.session.commit()
        return user_stats.total_xp

    @staticmethod
    def complete_task(user_stats):
        user_stats.tasks_completed += 1
        user_stats.total_xp += StatsService.XP_PER_TASK
        user_stats.updated_at = datetime.utcnow()
        db.session.commit()
        BadgeService.award_badges_for_tasks(user_stats)
        return user_stats

    @staticmethod
    def get_level(user_stats):
        return max(1, user_stats.total_xp // 50)

    @staticmethod
    def get_level_progress(user_stats):
        current_level = StatsService.get_level(user_stats)
        current_level_xp = current_level * 50
        next_level_xp = (current_level + 1) * 50
        progress = 0
        if next_level_xp != current_level_xp:
            progress = ((user_stats.total_xp - current_level_xp) / (next_level_xp - current_level_xp)) * 100
        return min(100, max(0, progress))

    @staticmethod
    def set_theme(user_stats, theme):
        if theme in ["light", "dark"]:
            user_stats.theme = theme
            user_stats.updated_at = datetime.utcnow()
            db.session.commit()
            return True
        return False


class AuthService:
    @staticmethod
    def register(username, email, password):
        if User.query.filter_by(email=email).first():
            return None
        hashed = generate_password_hash(password)
        user = User(username=username, email=email, password=hashed)
        db.session.add(user)
        db.session.flush()
        stats = UserStats(user_id=user.id)
        db.session.add(stats)
        db.session.commit()
        return user

    @staticmethod
    def authenticate(email, password):
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            return user
        return None


class FavoriteService:
    @staticmethod
    def add_favorite_destination(user, name, country=None, description=None, image_url=None):
        dest = FavoriteDestination.query.filter_by(name=name).first()
        if not dest:
            dest = FavoriteDestination(name=name, country=country, description=description, image_url=image_url)
            db.session.add(dest)
            db.session.flush()
        if dest not in user.favorite_destinations:
            user.favorite_destinations.append(dest)
            db.session.commit()
            return dest
        return None

    @staticmethod
    def remove_favorite_destination(user, destination):
        if destination in user.favorite_destinations:
            user.favorite_destinations.remove(destination)
            db.session.commit()
            return True
        return False

    @staticmethod
    def is_favorited(user, destination_name):
        return any(dest.name.lower() == destination_name.lower() for dest in user.favorite_destinations)

    @staticmethod
    def get_favorites(user):
        return user.favorite_destinations

    @staticmethod
    def mark_trip_destination_as_favorite(trip_destination, user):
        trip_destination.is_favorited = True
        FavoriteService.add_favorite_destination(user, trip_destination.name)
        db.session.commit()
        return trip_destination

    @staticmethod
    def unmark_trip_destination_as_favorite(trip_destination, user):
        trip_destination.is_favorited = False
        fav = FavoriteDestination.query.filter_by(name=trip_destination.name).first()
        if fav:
            FavoriteService.remove_favorite_destination(user, fav)
        db.session.commit()
        return trip_destination

    @staticmethod
    def toggle_trip_destination_favorite(trip_destination, user):
        if trip_destination.is_favorited:
            return FavoriteService.unmark_trip_destination_as_favorite(trip_destination, user)
        return FavoriteService.mark_trip_destination_as_favorite(trip_destination, user)

    @staticmethod
    def update_details(fav_dest, name=None, country=None, description=None, image_url=None):
        if name:
            fav_dest.name = name
        if country:
            fav_dest.country = country
        if description:
            fav_dest.description = description
        if image_url:
            fav_dest.image_url = image_url
        db.session.commit()
        return fav_dest

    @staticmethod
    def get_favorite_count(fav_dest):
        return fav_dest.users_who_favorited.count()

    @staticmethod
    def get_popular_destinations(limit=10):
        dests = FavoriteDestination.query.all()
        sorted_dest = sorted(dests, key=lambda d: d.users_who_favorited.count(), reverse=True)
        return sorted_dest[:limit]

    @staticmethod
    def search_destinations(query):
        return FavoriteDestination.query.filter(
            db.or_(
                FavoriteDestination.name.ilike(f"%{query}%"),
                FavoriteDestination.country.ilike(f"%{query}%")
            )
        ).all()


class PostService:
    @staticmethod
    def create_post(user_id, content, image_url=None):
        post = Post(user_id=user_id, content=content, image_url=image_url)
        db.session.add(post)
        db.session.commit()
        return post

    @staticmethod
    def add_like(post, user):
        if user not in post.likes:
            post.likes.append(user)
            db.session.commit()
        return post

    @staticmethod
    def remove_like(post, user):
        if user in post.likes:
            post.likes.remove(user)
            db.session.commit()
        return post

    @staticmethod
    def toggle_like(post, user):
        if user in post.likes:
            post.likes.remove(user)
            db.session.commit()
            return False
        else:
            post.likes.append(user)
            db.session.commit()
            return True

    @staticmethod
    def update_post(post, content):
        post.content = content
        post.updated_at = datetime.utcnow()
        db.session.commit()
        return post

    @staticmethod
    def delete_post(post):
        db.session.delete(post)
        db.session.commit()


class CommentService:
    @staticmethod
    def create_comment(post_id, user_id, content):
        comment = Comment(post_id=post_id, user_id=user_id, content=content)
        db.session.add(comment)
        db.session.commit()
        return comment

    @staticmethod
    def update_comment(comment, content):
        comment.content = content
        comment.updated_at = datetime.utcnow()
        db.session.commit()
        return comment

    @staticmethod
    def delete_comment(comment):
        db.session.delete(comment)
        db.session.commit()


class TaskService:
    @staticmethod
    def create_task(title, user_id, due_date=None, due_time=None, due_today_notified=False, overdue_notified=False):
        task = Task(title=title, user_id=user_id, due_date=due_date, due_time=due_time,)
        db.session.add(task)
        db.session.commit()
        return task

    @staticmethod
    def update_task(task, title=None, due_date=None, due_time=None):
        if title: task.title = title
        if due_date: task.due_date = due_date
        if due_time: task.due_time = due_time
        db.session.commit()
        return task

    @staticmethod
    def toggle_status(task):
        if task.status == 'Pending':
            task.status = 'Working'
        elif task.status == 'Working':
            task.status = 'Done'
        else:
            task.status = 'Pending'
        db.session.commit()
        return task

    @staticmethod
    def delete_task(task):
        db.session.delete(task)
        db.session.commit()

    @staticmethod
    def clear_user_tasks(user_id):
        Task.query.filter_by(user_id=user_id).delete()
        db.session.commit()


class BudgetService:
    @staticmethod
    def init_budget_for_trip(trip):
        if not trip.budget:
            budget = Budget(total_planned=0.0, total_spent=0.0, trip_id=trip.id)
            db.session.add(budget)
            db.session.commit()
            return budget
        return trip.budget

    @staticmethod
    def add_expense(budget, amount, description, shared_with=None):
        expense = Expense(amount=amount, description=description, budget_id=budget.id)
        db.session.add(expense)
        budget.total_spent += float(amount)
        db.session.commit()
        return expense

    @staticmethod
    def add_planned_budget(budget, amount, category):
        pb = PlannedBudget(amount=amount, category=category, budget_id=budget.id)
        db.session.add(pb)
        budget.total_planned += float(amount)
        db.session.commit()
        return pb

    @staticmethod
    def recalculate(budget):
        budget.total_planned = sum((pb.amount for pb in budget.planned_budgets), 0.0)
        budget.total_spent = sum((exp.amount for exp in budget.expenses), 0.0)
        db.session.commit()
        return budget

    @staticmethod
    def update_planned_budget(planned_budget, new_amount, new_category):
        planned_budget.amount = float(new_amount)
        planned_budget.category = new_category
        db.session.commit()
        if planned_budget.budget:
            BudgetService.recalculate(planned_budget.budget)
        return planned_budget

    @staticmethod
    def delete_planned_budget(planned_budget):
        budget = planned_budget.budget
        db.session.delete(planned_budget)
        db.session.commit()
        if budget:
            BudgetService.recalculate(budget)


class ExpenseService:
    @staticmethod
    def add_expense(trip, amount, category, description, shared_user_ids=None, actor_user_id=None):
        budget = trip.budget or BudgetService.init_budget_for_trip(trip)
        expense = Expense(amount=float(amount), description=description, budget_id=budget.id, category=category)
        db.session.add(expense)
        db.session.flush()
        if shared_user_ids:
            for uid in shared_user_ids:
                if isinstance(uid,User):
                    user = uid.id
                if user and user in trip.participants:
                    expense.shared_users.append(user)
                    NotificationService.send(
                        receiver_id=user.id,
                        sender_id=actor_user_id,
                        type_='expense_shared',
                        message=f"{session.get('user_name', 'Someone')} shared an expense in trip '{trip.title}'.",
                        trip_id=trip.id,
                        expense_id=expense.id
                    )
        budget.total_spent += float(amount)
        db.session.commit()
        return expense

    @staticmethod
    def update_expense(expense, amount=None, description=None, category=None, shared_friends=None, actor_user_id=None):
        if amount is not None:
            old_amount = expense.amount
            expense.amount = float(amount)
            if expense.budget:
                expense.budget.total_spent += expense.amount - old_amount
        if description is not None:
            expense.description = description
        if category is not None:
            expense.category = category
        if shared_friends is not None:
            expense.shared_users = []
            for user in shared_friends:
                if user in expense.budget.trip.participants:
                    expense.shared_users.append(user)
                    NotificationService.send(
                        receiver_id=user.id,
                        sender_id=actor_user_id,
                        type_='expense_shared',
                        message=f"{session.get('user_name', 'Someone')} updated an expense in trip '{expense.budget.trip.title}'.",
                        trip_id=expense.budget.trip.id,
                        expense_id=expense.id
                    )
        db.session.commit()
        if expense.budget:
            BudgetService.recalculate(expense.budget)
        return expense

    @staticmethod
    # def leave_expense(expense, user):
    #     if user in expense.shared_users and user.id == session.get('user_id'):
    #         expense.shared_users.remove(user)
    #         db.session.commit()
    #     if not expense.shared_users:
    #         db.session.delete(expense)
    #         db.session.commit()
    #     if expense.budget:
    #         BudgetService.recalculate(expense.budget)

    def leave_expense(self, user):
        if user in self.shared_users and user.id == session.get('user_id'):
            self.shared_users.remove(user)
            db.session.commit()

        if not self.shared_users:
            db.session.delete(self)
            db.session.commit()

    @staticmethod
    def remove_all_shared_users(expense):
        expense.shared_users = []
        db.session.commit()

    @staticmethod
    def delete_expense(expense):
        budget = expense.budget
        ExpenseService.remove_all_shared_users(expense)
        db.session.delete(expense)
        db.session.commit()
        if budget:
            BudgetService.recalculate(budget)

    def delete_expense(self):
        budget = self.budget
        self.remove_all_shared_users()
        db.session.delete(self)
        db.session.commit()
        BudgetService.recalculate(budget)


class TripService:
    @staticmethod
    def create_trip(title, destinations, start_date, end_date, description, participant):
        trip = Trip(title=title, start_date=start_date, end_date=end_date, description=description)
        db.session.add(trip)
        db.session.flush()
        for dest in destinations:
            if dest and dest.strip():
                td = TripDestination(name=dest.strip(), trip_id=trip.id)
                db.session.add(td)
        if participant:
            trip.participants.append(participant)
        db.session.commit()
        return trip

    @staticmethod
    def update_trip(trip, title=None, destinations=None, start_date=None, end_date=None, description=None):
        if title:
            trip.title = title
        if destinations is not None:
            # reset destinations
            for d in list(trip.destinations):
                db.session.delete(d)
            for dest in destinations:
                if dest and dest.strip():
                    td = TripDestination(name=dest.strip(), trip_id=trip.id)
                    db.session.add(td)
        if start_date:
            trip.start_date = start_date
        if end_date:
            trip.end_date = end_date
        if description is not None:
            trip.description = description
        db.session.commit()
        return trip

    @staticmethod
    def add_itinerary_item(trip, title, date, location=None, notes=None, time=None):
        item = ItineraryItem(title=title, date=date, location=location, notes=notes, time=time, trip_id=trip.id)
        db.session.add(item)
        db.session.commit()
        return item

    @staticmethod
    def add_participant(trip, user):
        if user not in trip.participants:
            trip.participants.append(user)
            db.session.commit()
            NotificationService.send(receiver_id=user.id, sender_id=None, type_='trip_invite', message=f"You were added to trip '{trip.title}'", trip_id=trip.id)
        return trip

    @staticmethod
    def remove_participant(trip, user):
        if user in trip.participants:
            trip.participants.remove(user)
            if not trip.participants:
                db.session.delete(trip)
            db.session.commit()

    @staticmethod
    def delete_trip(trip):
        db.session.delete(trip)
        db.session.commit()

    @staticmethod
    def delete_all_trips(trip_owner):
        # expects a Trip or a User; kept minimal to avoid changing original signature too much
        if isinstance(trip_owner, User):
            for trip in list(trip_owner.trips):
                TripService.delete_trip(trip)
        elif isinstance(trip_owner, Trip):
            TripService.delete_trip(trip_owner)

    @staticmethod
    def add_destination(trip, name: str):
        td = TripDestination(name=name, trip_id=trip.id)
        db.session.add(td)
        db.session.commit()
        return td

    @staticmethod
    def get_average_rating(trip):
        if not trip.reviews:
            return 0
        total = sum((r.rating for r in trip.reviews), 0)
        return round(total / len(trip.reviews), 1)


class ItineraryService:
    @staticmethod
    def update_item(item, title=None, date=None, location=None, notes=None, time=None):
        if title: item.title = title
        if date: item.date = date
        if location: item.location = location
        if notes: item.notes = notes
        if time: item.time = time
        db.session.commit()
        return item

    @staticmethod
    def delete_item(item):
        db.session.delete(item)
        db.session.commit()


class ReviewService:
    @staticmethod
    def create_review(trip_id, user_id, rating, comment=None):
        if rating < 1 or rating > 5:
            raise ValueError("Rating must be between 1 and 5")
        existing = Review.query.filter_by(trip_id=trip_id, user_id=user_id).first()
        if existing:
            raise ValueError("User has already reviewed this trip")
        review = Review(trip_id=trip_id, user_id=user_id, rating=rating, comment=comment)
        db.session.add(review)
        db.session.commit()
        return review

    @staticmethod
    def update_review(review, rating=None, comment=None):
        if rating is not None:
            if rating < 1 or rating > 5:
                raise ValueError("Rating must be between 1 and 5")
            review.rating = rating
        if comment is not None:
            review.comment = comment
        review.updated_at = datetime.utcnow()
        db.session.commit()
        return review

    @staticmethod
    def delete_review(review):
        db.session.delete(review)
        db.session.commit()

    @staticmethod
    def add_photo(review, photo_url, caption=None):
        photo = ReviewPhoto(photo_url=photo_url, caption=caption, review_id=review.id)
        db.session.add(photo)
        db.session.commit()
        return photo

    @staticmethod
    def get_star_display(review):
        return "★" * review.rating + "☆" * (5 - review.rating)

    @staticmethod
    def delete_photo(photo):
        db.session.delete(photo)
        db.session.commit()


class PasswordResetService:
    @staticmethod
    def generate_token_for_user(user, expires_in=3600):
        token = secrets.token_urlsafe(32)
        expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
        prt = PasswordResetToken(token=token, user_id=user.id, expires_at=expires_at)
        db.session.add(prt)
        db.session.commit()
        return prt

    @staticmethod
    def validate_token(token_str):
        prt = PasswordResetToken.query.filter_by(token=token_str).first()
        if not prt or prt.used or datetime.utcnow() >= prt.expires_at:
            return None
        return prt

    @staticmethod
    def validate_token_instance(prt):
        return (prt is not None) and (not prt.used) and (datetime.utcnow() < prt.expires_at)

    @staticmethod
    def mark_token_used(prt):
        prt.used = True
        db.session.commit()
        return True

    @staticmethod
    def consume_token_and_reset(prt, new_password):
        if not PasswordResetService.validate_token_instance(prt):
            raise ValueError("Token invalid or expired")
        user = prt.user
        user.password = generate_password_hash(new_password)
        prt.used = True
        db.session.commit()
        return True

    @staticmethod
    def send_reset_email(to_email, subject, body):
        msg = Message(subject=subject, recipients=[to_email], body=body, sender=current_app.config.get('MAIL_USERNAME'))
        mail.send(msg)


# ----------------------------
# Utility / compatibility
# ----------------------------

def ensure_user_stats(user):
    if not user.stats:
        stats = UserStats(user_id=user.id)
        db.session.add(stats)
        db.session.commit()
        return stats
    return user.stats


# End of module
