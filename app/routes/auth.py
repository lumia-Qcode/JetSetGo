from flask import Blueprint, render_template, url_for, flash, request, session, redirect, Flask
from app.models import User, PasswordResetToken, UserStats
from werkzeug.security import generate_password_hash
from app import db

auth_bp = Blueprint('auth', __name__)   # create Blueprint for auth routes
app = Flask(__name__)   # Create Flask instance (used here only for session secret key – not typically needed in blueprints)
app.secret_key = 'your-secret-key'  # The secret key ensures secure sessions and message flashing.

#==========================================================================================================

# Handles both displaying and processing the login form.  GET → renders login page.  POST → verifies user credentials and starts a session.
@auth_bp.route("/login", methods = ['GET', 'POST'])
def login():
    if request.method == "POST":
        # Retrieve form data
        email = request.form.get('email')
        password = request.form.get('password')

        # Authenticate if user exists in our database using User model method (defined in app.models)
        user = User.authenticate(email, password)

        if user:    # If authentication is successful, login user and redirect to home page
            user.login()
            flash(f"Welcome {session['user_name']}, Login Successful!", 'success')
            return redirect(url_for('view.user_home'))

        else:       # If authentication fails, flash error message
            flash('Invalid username or password', 'danger')

    # For GET request or failed POST, render login template again
    return render_template("login.html")

#==========================================================================================================

# Logs out the current user by clearing the session and redirects to the login page.
@auth_bp.route("/logout")
def logout():
    User.logout()
    flash('Logged out', 'info')
    return render_template("hello.html")

#==========================================================================================================

# Handles both displaying and processing the login form.  GET → renders login page.  POST → verifies user credentials and starts a session.
@auth_bp.route("/register", methods = ["GET","POST"])
def register():
    if request.method == "POST":
        # Retrieve form data
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.register(username, email, password)     # Register user using User model method (defined in app.models)
       
        if not user:        # If email already exists → show error and redirect to register again
            flash('Email already in use. Please register with another email.', 'danger')
            return redirect(url_for('auth.register'))

        flash('Registered Successfully!', 'success')    #  If registration successful → show success and redirect to login
        return redirect(url_for('auth.login'))
    return render_template('register.html')

#==========================================================================================================

@auth_bp.route("/forgot_password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        # Step 1: Check if email exists
        email = request.form.get("email")
        user = User.query.filter_by(email=email).first()

        if not user:
            flash("Email not found.", "danger")
            return redirect(url_for("auth_bp.forgot_password"))

        # Store user ID in session to allow password reset
        session["reset_user_id"] = user.id
        return redirect(url_for("auth.reset_password"))

    return render_template("forgot_password.html")

#===================================================================================================================

@auth_bp.route("/reset_password", methods=["GET", "POST"])
def reset_password():
    user_id = session.get("reset_user_id")
    if not user_id:
        flash("Unauthorized access.", "danger")
        return redirect(url_for("auth_bp.forgot_password"))

    user = User.query.get(user_id)
    if request.method == "POST":
        new_password = request.form.get("password")
        confirm_password = request.form.get("confirm_password")

        if new_password != confirm_password:
            flash("Passwords do not match.", "danger")
            return redirect(url_for("auth.reset_password"))

        # Update password
        user.password = generate_password_hash(new_password)
        db.session.commit()

        # Clear session
        session.pop("reset_user_id", None)
        flash("Password reset successful. Please login.", "success")
        return redirect(url_for("auth.login"))

    return render_template("reset_password.html")

#==========================================================================================================
@auth_bp.route("/profile")
def profile():
    if 'user_id' not in session:
        flash("Please log in to access your profile.", "danger")
        return redirect(url_for("auth.login"))
    
    user = User.query.get(session['user_id'])
    user_stats = UserStats.query.filter_by(user_id=user.id).first()
    return render_template("profile.html", user=user, user_stats=user_stats)

#==========================================================================================================

@auth_bp.route("/edit-profile", methods=["GET", "POST"])
def edit_profile():
    if 'user_id' not in session:
        flash("Please log in to access your profile.", "danger")
        return redirect(url_for("auth.login"))
    
    user = User.query.get(session['user_id'])

    if request.method == "POST":
        # Update user basic info
        user.username = request.form.get("username")
        user.email = request.form.get("email")
        
        # Get or create user stats
        user_stats = UserStats.query.filter_by(user_id=user.id).first()
        if not user_stats:
            user_stats = UserStats(user_id=user.id)
            db.session.add(user_stats)
        
        # Update theme in UserStats (NOT in User)
        theme = request.form.get("theme", "dark")
        user_stats.set_theme(theme)
        
        try:
            db.session.commit()
            
            # Update session
            session['user_theme'] = theme
            session.modified = True
            
            flash("Profile updated successfully!", "success")
            return redirect(url_for("auth.profile"))
        except Exception as e:
            db.session.rollback()
            print(f"Error updating profile: {e}")
            flash("Error updating profile. Please try again.", "danger")
            return redirect(url_for("auth.edit_profile"))

    return render_template("edit_profile.html", user=user)