from flask import Blueprint, render_template

view_bp = Blueprint('view', __name__)
@view_bp.route("/home")
def home():
    return render_template('home.html')   