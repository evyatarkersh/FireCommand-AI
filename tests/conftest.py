import os
import pytest
from app import create_app
from app.extensions import db

# --- התוספת שלנו שפותרת את בעיית ה-JSONB בטסטים ---
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.dialects.postgresql import JSONB


@compiles(JSONB, 'sqlite')
def compile_jsonb_sqlite(type_, compiler, **kw):
    """ אומר ל-SQLite להתייחס ל-JSONB כאל JSON רגיל במהלך הטסטים """
    return "JSON"


# ---------------------------------------------------

@pytest.fixture
def app():
    # הגדרת משתנה סביבה שמצביע על דאטה-בייס טסטים
    os.environ['DATABASE_URL'] = 'sqlite:///:memory:'

    app = create_app()
    app.config.update({
        "TESTING": True,
    })

    # אתחול ה-DB לפני כל טסט
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def runner(app):
    return app.test_cli_runner()

@pytest.fixture
def socket_client(app):
    from app.extensions import socketio
    return socketio.test_client(app)