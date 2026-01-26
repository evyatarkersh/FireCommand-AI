from dotenv import load_dotenv # <--- הוספה חדשה
import os

load_dotenv()
from app import create_app
app = create_app()

if __name__ == '__main__':
    app.run(debug=True, port=5000)