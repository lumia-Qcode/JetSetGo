from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail
from flask_migrate import Migrate
from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask, render_template, session, redirect, url_for
from app.routes.social import social_bp


# --- Global objects ---
db = SQLAlchemy()
migrate = Migrate()
mail = Mail()


def create_app():
    app = Flask(__name__)

    # --- Config ---
    app.config['SECRET_KEY'] = 'your-secret-key'
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///todo.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    db.init_app(app)
    migrate.init_app(app, db)

    # --- Mail setup ---
    app.config.update(
        MAIL_SERVER='smtp.gmail.com',
        MAIL_PORT=587,
        MAIL_USE_TLS=True,
        MAIL_USE_SSL=False,
        MAIL_USERNAME='lumiaqureshi796@gmail.com',
        MAIL_PASSWORD='hhvd rhwm kbvf fmsa'
    )
    mail.init_app(app)

    # --- Blueprints ---
    from app.routes.auth import auth_bp
    from app.routes.tasks import tasks_bp, send_daily_task_notifications, reset_task_notifications
    from app.static.about import main_bp
    from app.static.home import view_bp
    from app.routes.trips import trips_bp
    from app.routes.notif import notif_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(tasks_bp)
    app.register_blueprint(view_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(trips_bp)
    app.register_blueprint(notif_bp)
    app.register_blueprint(social_bp, url_prefix='/social')
    
    # --- APScheduler ---
    scheduler = BackgroundScheduler()
    # Move this import **here**, after db is ready
    from app.routes.sys_notif import start_system_notifications_scheduler
    start_system_notifications_scheduler(scheduler)
    scheduler.add_job(reset_task_notifications, 'cron', hour=0)
    scheduler.start()
    @app.route('/')
    @app.route('/')
    def hello():
        if 'user_id' in session:
            return redirect(url_for('view.home'))  # Redirect logged in users to home
        return render_template('hello.html')


    return app
