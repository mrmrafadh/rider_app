from flask import Flask, request
from flask_socketio import SocketIO, emit
from flask_cors import CORS
import time
import sys

print("=" * 60)
print("SIMPLE CHAT SERVER")
print("=" * 60)

app = Flask(__name__)
CORS(app)

# IMPORTANT: Use async_mode='threading' to avoid eventlet dependency
socketio = SocketIO(app,
                    cors_allowed_origins="*",
                    async_mode='threading')

users = {}


@socketio.on('connect')
def connect():
    print(f"\n✅ New connection: {request.sid}")


@socketio.on('disconnect')
def disconnect():
    print(f"\n❌ Disconnected: {request.sid}")
    for user, sid in list(users.items()):
        if sid == request.sid:
            del users[user]
            print(f"   Removed user: {user}")
            break


@socketio.on('join')
def join(data):
    username = data.get('username', '').strip()
    if username:
        users[username] = request.sid
        print(f"\n👤 {username} joined")
        print(f"   Online: {list(users.keys())}")

        emit('joined', {
            'username': username,
            'message': f'Welcome {username}!',
            'users': list(users.keys())
        })


@socketio.on('send_message')
def send_message(data):
    sender = data.get('sender', '').strip()
    receiver = data.get('receiver', '').strip()
    message = data.get('message', '').strip()

    print(f"\n✉️ {sender} -> {receiver}: {message}")

    if receiver in users:
        emit('receive_message', {
            'sender': sender,
            'message': message,
            'time': time.strftime('%H:%M:%S')
        }, room=users[receiver])
        print(f"   ✅ Delivered to {receiver}")
    else:
        print(f"   ❌ {receiver} not found")

    # Confirm to sender
    emit('sent_confirm', {
        'to': receiver,
        'success': receiver in users
    })


if __name__ == '__main__':
    print("\n" + "=" * 60)
    print("SERVER STARTING...")
    print("Listening on: http://localhost:5000")
    print("=" * 60 + "\n")

    try:
        socketio.run(app,
                     host='0.0.0.0',
                     port=5000,
                     debug=True,
                     allow_unsafe_werkzeug=True)
    except KeyboardInterrupt:
        print("\n\nServer stopped by user")
        sys.exit(0)