"""
Flask extension initialization module for database and real-time communication.
This module configures SQLAlchemy for database operations and SocketIO for WebSocket connections,
with support for both local development and production deployment using Redis message queues.
"""

import os

from flask_socketio import SocketIO
from flask_sqlalchemy import SQLAlchemy

# Initialize SQLAlchemy instance for database operations
db = SQLAlchemy()

# Retrieve the Redis URL from environment variables for production deployment
redis_url = os.environ.get('REDIS_URL')

# Configure SocketIO with Redis message queue support for multi-process environments
if redis_url:
    # Initialize SocketIO with Redis message queue for production (Gunicorn multi-worker setup)
    socketio = SocketIO(
        cors_allowed_origins="*",
        async_mode='gevent',
        message_queue=redis_url
    )
    print(f"🌐 [PID {os.getpid()}] SocketIO initialized with Redis Message Queue")
else:
    # Initialize SocketIO in local mode for development (single-process environment)
    socketio = SocketIO(cors_allowed_origins="*", async_mode='gevent')
    print(f"🏠 [PID {os.getpid()}] SocketIO initialized in local mode (no Redis)")
