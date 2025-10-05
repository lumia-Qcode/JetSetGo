from flask import Flask
from flask_sqlalchemy import SQLAlchemy

# create database object globally
db = SQLAlchemy()

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'your-secret-key'
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///todo.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # connect app to db
    db.init_app(app)

    from app.routes.auth import auth_bp
    from app.routes.tasks import tasks_bp
    from app.static.about import main_bp
    from app.static.home import view_bp
    from app.routes.trips import trips_bp
    app.register_blueprint(auth_bp)
    app.register_blueprint(tasks_bp)
    app.register_blueprint(view_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(trips_bp)

    return app
