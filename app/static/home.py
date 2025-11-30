from flask import Blueprint, render_template, session

view_bp = Blueprint('view', __name__)

# Logged-in user's real homepage (dashboard)
@view_bp.route("/home")
def user_home():
    return render_template('home.html')

# Landing page for non-logged-in users
@view_bp.route("/")
def landing():
    if "user_id" not in session:
        return render_template("hello.html")
    return render_template("home.html")   # logged-in users go here