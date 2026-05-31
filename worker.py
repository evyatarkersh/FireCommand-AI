import time

from dotenv import load_dotenv

load_dotenv()

from app import create_app
from app.api.routes import run_full_system_sync  # Ensure this is the correct path!

# Initialize the application so the Worker can access the database
app = create_app()


def start_worker():
    print("🤖 Background Worker Started!")

    # The Worker's infinite loop
    while True:
        with app.app_context():
            print("\n🚀 Starting sync cycle...")
            try:
                run_full_system_sync()
                print("✅ Sync cycle finished.")
            except Exception as e:
                print(f"❌ Error during sync: {e}")

        print("💤 Worker sleeping for 5 minutes...")
        time.sleep(300)


if __name__ == "__main__":
    # Small delay at startup to allow the Web server to start first
    time.sleep(10)
    start_worker()
