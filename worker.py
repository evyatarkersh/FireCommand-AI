import time
from dotenv import load_dotenv

load_dotenv()

from app import create_app
from app.api.routes import run_full_system_sync  # ודא שזה הנתיב הנכון!

# מקימים את האפליקציה כדי שה-Worker יכיר את מסד הנתונים
app = create_app()


def start_worker():
    print("🤖 Background Worker Started!")

    # הלולאה הנצחית של ה-Worker
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
    # השהיה קלה בהתחלה כדי לתת לשרת ה-Web לעלות קודם
    time.sleep(10)
    start_worker()