from flask import Blueprint, render_template, url_for, flash, request, session, redirect, Flask
from app.models import User, PasswordResetToken

auth_bp = Blueprint('auth', __name__)   # create Blueprint for auth routes
app = Flask(__name__)   # Create Flask instance (used here only for session secret key — not typically needed in blueprints)
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
            return redirect(url_for('view.home'))
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
    return redirect(url_for("auth.login"))

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
        email = request.form.get("email")
        user = User.query.filter_by(email=email).first()
        if user:
            token = PasswordResetToken.generate_token(user)
            reset_url = url_for("auth.reset_password", token=token, _external=True)
            
            # Send email using your email service
            print(f"Reset link for {user.email}: {reset_url}")
            PasswordResetToken.send_email(user.email, "Reset Password", f"Click to reset: {reset_url}")

        flash("If your email exists, a reset link has been sent.", "info")
        return redirect(url_for("auth.login"))

    return render_template("forgot_password.html")

#===================================================================================================================
@auth_bp.route("/reset_password/<token>", methods=["GET", "POST"])
def reset_password(token):
    reset_token = PasswordResetToken.query.filter_by(token=token).first_or_404()

    if not reset_token.is_valid():
        flash("Invalid or expired token.", "danger")
        return redirect(url_for("auth.forgot_password"))

    if request.method == "POST":
        new_password = request.form.get("password")
        confirm_password = request.form.get("confirm_password")

        if new_password != confirm_password:
            flash("Passwords do not match.", "danger")
            return redirect(url_for("auth.reset_password", token=token))

        try:
            reset_token.reset_password(new_password)
            flash("Password updated successfully!", "success")
        except ValueError:
            flash("Invalid or expired token.", "danger")
            return redirect(url_for("auth.forgot_password"))

        return redirect(url_for("auth.login"))

    return render_template("reset_password.html", token=token)

