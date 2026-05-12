from app import create_app
from app.extensions import db
from app.models.nasa_fire import FireIncident
from app.models.fire_events import FireEvent
from app.models.resources import Station, Resource
from app.models.commander_logs import CommandLog
from app.services.seed_resources import seed_real_israel_stations

app = create_app()


def initialize_database():
    with app.app_context():
        print("🗑️ Dropping all existing tables (cleaning the slate)...")
        db.drop_all()

        print("🏗️ Creating database tables from scratch...")
        db.create_all()

        print("🌱 Seeding database with initial stations and resources...")
        seed_real_israel_stations()

        print("✅ Database initialization complete!")


if __name__ == "__main__":
    initialize_database()