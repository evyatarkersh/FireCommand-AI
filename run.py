import gevent.monkey

gevent.monkey.patch_all()

from dotenv import load_dotenv  # <--- New addition
from app.extensions import socketio

load_dotenv()
from app import create_app

app = create_app()

if __name__ == '__main__':
    # For local execution only
    socketio.run(app, debug=False, port=5000)
