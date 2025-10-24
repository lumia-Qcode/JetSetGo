from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail

# create database object globally to be used in models and routes across the app
db = SQLAlchemy()
mail = Mail()

def create_app():
    app = Flask(__name__)       # create Flask app instance

    # --- Basic Flask Configuration ---
    app.config['SECRET_KEY'] = 'your-secret-key'      # Secret key is used for securely signing the session cookie and other data
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///todo.db'  # Database URI for SQLite database named 'todo.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False    # Disables event notifications from SQLAlchemy (saves resources)

    # connect app to db
    db.init_app(app)

    # Import models here to ensure they are registered with SQLAlchemy
    from app.routes.auth import auth_bp
    from app.routes.tasks import tasks_bp
    from app.static.about import main_bp
    from app.static.home import view_bp
    from app.routes.trips import trips_bp

    # Register blueprints for modular route management
    app.register_blueprint(auth_bp)
    app.register_blueprint(tasks_bp)
    app.register_blueprint(view_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(trips_bp)

    app.config.update(
        MAIL_SERVER='smtp.gmail.com',
        MAIL_PORT=587,
        MAIL_USE_TLS=True,
        MAIL_USE_SSL=False,
        MAIL_USERNAME='your@gmail.com',
        MAIL_PASSWORD='your-email-password'
    )
    mail.init_app(app)

    return app
