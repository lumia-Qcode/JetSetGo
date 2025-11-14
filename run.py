from app import create_app, db

app = create_app()      # Create an instance of the Flask application

# The application context allows you to work with the app’s extensions (like SQLAlchemy)
with app.app_context():
    db.create_all()     # Creates all tables in the database if they don’t already exist

if __name__ == "__main__":
    app.run(debug = True)       # Run the Flask development server with debug mode enabled
                                # Debug mode automatically restarts the server on code changes