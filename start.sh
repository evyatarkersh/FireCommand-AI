#!/bin/bash

echo "🏗️ Initializing Database..."
python init_db.py

echo "🚀 Starting Background Worker..."
# The & at the end runs the operation in the background without blocking the rest of the code
python worker.py &

echo "🌐 Starting Web Server..."
# Runs Gunicorn for the Web server
gunicorn -k geventwebsocket.gunicorn.workers.GeventWebSocketWorker -w 1 run:app