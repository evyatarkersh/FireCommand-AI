#!/bin/bash

echo "🏗️ Initializing Database..."
python init_db.py

echo "🚀 Starting Background Worker..."
# ה-& בסוף מריץ את הפעולה ברקע בלי לחסום את שאר הקוד
python worker.py &

echo "🌐 Starting Web Server..."
# מריץ את Gunicorn עבור שרת ה-Web
gunicorn -k geventwebsocket.gunicorn.workers.GeventWebSocketWorker -w 1 run:app