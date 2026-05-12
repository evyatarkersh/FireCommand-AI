import os
from flask import Flask
from app.extensions import db, socketio
from app.api.routes import api
from flask_cors import CORS

def create_app():
    app = Flask(__name__)

    # תיקון קטן לכתובת של Neon (הם נותנים postgres:// אבל SQLAlchemy רוצה postgresql://)
    db_url = os.environ.get('DATABASE_URL')
    if db_url and db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)

    app.config['SQLALCHEMY_DATABASE_URI'] = db_url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # אתחול ה-DB
    CORS(app)
    db.init_app(app)
    socketio.init_app(app)

    # רישום ה-Routes
    app.register_blueprint(api)

    return app