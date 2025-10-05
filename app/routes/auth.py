from flask import Blueprint, render_template, url_for, flash, request, session, redirect, Flask
#from app import db
from app.models import User
#from werkzeug.security import generate_password_hash, check_password_hash

auth_bp = Blueprint('auth', __name__)
app = Flask(__name__)
app.secret_key = 'your-secret-key'

@auth_bp.route("/login", methods = ['GET', 'POST'])
def login():
    if request.method == "POST":
        #username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')

        # user = User.query.filter_by(email = email).first()
        user = User.authenticate(email, password)

        # if user and check_password_hash(user.password, password):
        #     session['user_id'] = user.id
        #     session['user_email'] = user.email
        #     session['user_name'] = user.username
        if user:
            user.login()
            flash(f"Welcome {session['user_name']}, Login Successful!", 'success')
            return redirect(url_for('view.home'))
        else:
            flash('Invalid username or password', 'danger')
    return render_template("login.html")

@auth_bp.route("/logout")
def logout():
    # session.pop('user_id', 'None')
    # session.pop('user_name', 'None')
    # session.pop('user_email', 'None')
    User.logout()
    flash('Logged out', 'info')
    return redirect(url_for("auth.login"))

@auth_bp.route("/register", methods = ["GET","POST"])
def register():
    if request.method == "POST":
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')

        #existingUser = User.query.filter_by(email = email).first()
        user = User.register(username, email, password)
        #if existingUser:
        if not user:
            flash('Email already in use. Please register with another email.', 'danger')
            return redirect(url_for('register'))
    
        # hashed_password = generate_password_hash(password)
        # new_user = User(username = username, email = email, password = hashed_password)
        # db.session.add(new_user)
        # db.session.commit()

        flash('Registered Successfully!', 'success')
        return redirect(url_for('auth.login'))
    return render_template('register.html')