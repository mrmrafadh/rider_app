from flask import Flask
from flask_socketio import SocketIO, send, emit

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app, cors_allowed_origins="*")

@socketio.on('message')
def handle_message(msg):
    print('Received: ' + msg)
    emit('message', 'Echo: ' + msg, broadcast=True)

@socketio.on('message1')
def handle_message1(msg):
    print('Received: ' + msg)
    if msg == 'Ping from Flutter':
        emit('message1','Pong from Python', broadcast=True)
    else:
        emit('message1', 'Echo: ' + msg, broadcast=True)

if __name__ == '__main__':
    socketio.run(app, host="127.0.0.1", port=5000, allow_unsafe_werkzeug=True)
