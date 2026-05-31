import os

from flask import Flask
from flask_cors import CORS

from app.api.routes import api
from app.extensions import db, socketio


def create_app():
    """Creates and configures the Flask application instance with database, CORS, WebSocket support, and API routes. Returns the fully configured Flask app object ready to run."""
    app = Flask(__name__)

    # Convert Neon database URL from postgres:// to postgresql:// format for SQLAlchemy compatibility
    db_url = os.environ.get('DATABASE_URL')
    if db_url and db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)

    app.config['SQLALCHEMY_DATABASE_URI'] = db_url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # Initialize CORS, database, and WebSocket extensions
    CORS(app)
    db.init_app(app)
    socketio.init_app(app)

    # Register API blueprint with all routes
    app.register_blueprint(api)

    return app
