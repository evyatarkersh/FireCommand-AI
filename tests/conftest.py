import os

import pytest
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles

from app import create_app
from app.extensions import db


@compiles(JSONB, 'sqlite')
def compile_jsonb_sqlite(type_, compiler, **kw):
    """Custom SQLAlchemy compiler that translates PostgreSQL JSONB types to JSON for SQLite compatibility during testing. Returns 'JSON' as the SQLite column type when JSONB is encountered."""
    return "JSON"


@pytest.fixture
def app():
    """Creates and configures a Flask application instance for testing with an in-memory SQLite database. Initializes all database tables, yields the app for test execution, then cleans up by removing the session and dropping all tables."""
    # Set environment variable pointing to test database
    os.environ['DATABASE_URL'] = 'sqlite:///:memory:'

    app = create_app()
    app.config.update({
        "TESTING": True,
    })

    # Initialize DB before each test
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    """Returns a Flask test client for making HTTP requests to the application during tests. Takes the app fixture as input and returns a test client instance."""
    return app.test_client()


@pytest.fixture
def runner(app):
    """Returns a Flask CLI test runner for testing command-line interface commands. Takes the app fixture as input and returns a CLI runner instance."""
    return app.test_cli_runner()


@pytest.fixture
def socket_client(app):
    """Creates and returns a Socket.IO test client for testing WebSocket connections and real-time communication. Takes the app fixture as input and returns a configured Socket.IO test client."""
    from app.extensions import socketio
    return socketio.test_client(app)
