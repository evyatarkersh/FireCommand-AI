import os
from flask import Flask
from app.extensions import db
from app.api.routes import api

def create_app():
    app = Flask(__name__)

    # תיקון קטן לכתובת של Neon (הם נותנים postgres:// אבל SQLAlchemy רוצה postgresql://)
    db_url = os.environ.get('DATABASE_URL')
    if db_url and db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)

    app.config['SQLALCHEMY_DATABASE_URI'] = db_url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # אתחול ה-DB
    db.init_app(app)

    # רישום ה-Routes
    app.register_blueprint(api)

    # יצירת טבלאות אוטומטית (אם לא קיימות)
    with app.app_context():
        from app.models.nasa_fire import FireIncident  # וודא שזה שם הקובץ הנכון
        from app.models.fire_events import FireEvent
        db.create_all()

    return app