from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit
from flask_cors import CORS
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# Database configuration (PostgreSQL)
DB_CONFIG = {
    'host': 'localhost',      # or Azure host
    'port': 5432,
    'database': 'rider_info',
    'user': 'riderapp',
    'password': 'StrongPass123'
}

# Active riders dictionary to track Socket.IO connections
active_riders = {}


def get_db_connection():
    """Create and return a PostgreSQL database connection"""
    try:
        connection = psycopg2.connect(**DB_CONFIG, cursor_factory=RealDictCursor)
        return connection
    except Exception as e:
        print(f"Error connecting to PostgreSQL: {e}")
        return None


def close_db_connection(connection, cursor=None):
    """Close database connection and cursor"""
    if cursor:
        cursor.close()
    if connection:
        connection.close()


# ------------------- REST API Endpoints ------------------- #

@app.route('/api/login', methods=['POST'])
def login():
    """Login endpoint for rider authentication"""
    try:
        data = request.get_json()
        rider_name = data.get('rider_name')
        password = data.get('password')

        if not rider_name or not password:
            return jsonify({'success': False, 'message': 'Username and password are required'}), 400

        connection = get_db_connection()
        if not connection:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500

        cursor = connection.cursor()

        # PostgreSQL uses %s for parameterized queries
        cursor.execute("SELECT rider_id, rider_name, password FROM riders WHERE rider_name = %s", (rider_name,))
        rider = cursor.fetchone()

        if rider and rider['password'] == password:
            cursor.execute("SELECT is_online FROM rider_status WHERE rider_id = %s", (rider['rider_id'],))
            status = cursor.fetchone()

            response = {
                'success': True,
                'rider_id': rider['rider_id'],
                'rider_name': rider['rider_name'],
                'is_online': status['is_online'] if status else False,
                'message': 'Login successful'
            }
            close_db_connection(connection, cursor)
            return jsonify(response), 200
        else:
            close_db_connection(connection, cursor)
            return jsonify({'success': False, 'message': 'Invalid username or password'}), 401

    except Exception as e:
        print(f"Login error: {e}")
        return jsonify({'success': False, 'message': f'Server error: {str(e)}'}), 500


@app.route('/api/update_status', methods=['POST'])
def update_status():
    """Update rider online/offline status"""
    try:
        data = request.get_json()
        rider_id = data.get('rider_id')
        is_online = data.get('is_online')

        if rider_id is None or is_online is None:
            return jsonify({'success': False, 'message': 'Rider ID and status are required'}), 400

        connection = get_db_connection()
        if not connection:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500

        cursor = connection.cursor()

        # Check if status record exists
        cursor.execute("SELECT status_id FROM rider_status WHERE rider_id = %s", (rider_id,))
        existing = cursor.fetchone()

        if existing:
            # Update existing status
            cursor.execute("""
                UPDATE rider_status
                SET is_online = %s, last_updated = NOW()
                WHERE rider_id = %s
            """, (is_online, rider_id))
        else:
            # Insert new status
            cursor.execute("""
                INSERT INTO rider_status (rider_id, is_online)
                VALUES (%s, %s)
            """, (rider_id, is_online))

        connection.commit()

        # Emit status change to all connected clients
        socketio.emit('rider_status_changed', {
            'rider_id': rider_id,
            'is_online': is_online,
            'timestamp': datetime.now().isoformat()
        })

        close_db_connection(connection, cursor)
        return jsonify({'success': True, 'message': 'Status updated successfully'}), 200

    except Exception as e:
        print(f"Update status error: {e}")
        return jsonify({'success': False, 'message': f'Server error: {str(e)}'}), 500


@app.route('/api/update_location', methods=['POST'])
def update_location():
    """Update rider location"""
    try:
        data = request.get_json()
        rider_id = data.get('rider_id')
        latitude = data.get('latitude')
        longitude = data.get('longitude')

        if rider_id is None or latitude is None or longitude is None:
            return jsonify({'success': False, 'message': 'Rider ID, latitude, and longitude are required'}), 400

        connection = get_db_connection()
        if not connection:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500

        cursor = connection.cursor()
        cursor.execute("""
            INSERT INTO rider_location (rider_id, latitude, longitude, location_time)
            VALUES (%s, %s, %s, NOW())
        """, (rider_id, latitude, longitude))
        connection.commit()

        socketio.emit('rider_location_updated', {
            'rider_id': rider_id,
            'latitude': latitude,
            'longitude': longitude,
            'timestamp': datetime.now().isoformat()
        })

        close_db_connection(connection, cursor)
        return jsonify({'success': True, 'message': 'Location updated successfully'}), 200

    except Exception as e:
        print(f"Update location error: {e}")
        return jsonify({'success': False, 'message': f'Server error: {str(e)}'}), 500


@app.route('/api/rider/<int:rider_id>/location', methods=['GET'])
def get_rider_location(rider_id):
    """Get the latest location of a rider"""
    try:
        connection = get_db_connection()
        if not connection:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500

        cursor = connection.cursor()
        cursor.execute("""
            SELECT latitude, longitude, location_time
            FROM rider_location
            WHERE rider_id = %s
            ORDER BY location_time DESC
            LIMIT 1
        """, (rider_id,))
        location = cursor.fetchone()

        close_db_connection(connection, cursor)

        if location:
            return jsonify({
                'success': True,
                'rider_id': rider_id,
                'latitude': float(location['latitude']),
                'longitude': float(location['longitude']),
                'location_time': location['location_time'].isoformat()
            }), 200
        else:
            return jsonify({'success': False, 'message': 'No location found for this rider'}), 404

    except Exception as e:
        print(f"Get location error: {e}")
        return jsonify({'success': False, 'message': f'Server error: {str(e)}'}), 500


@app.route('/api/riders/online', methods=['GET'])
def get_online_riders():
    """Get all online riders with their latest locations"""
    try:
        connection = get_db_connection()
        if not connection:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500

        cursor = connection.cursor()
        cursor.execute("""
            SELECT
                r.rider_id,
                r.rider_name,
                rs.is_online,
                rs.last_updated,
                (SELECT latitude FROM rider_location
                 WHERE rider_id = r.rider_id
                 ORDER BY location_time DESC LIMIT 1) as latitude,
                (SELECT longitude FROM rider_location
                 WHERE rider_id = r.rider_id
                 ORDER BY location_time DESC LIMIT 1) as longitude,
                (SELECT location_time FROM rider_location
                 WHERE rider_id = r.rider_id
                 ORDER BY location_time DESC LIMIT 1) as last_location_time
            FROM riders r
            LEFT JOIN rider_status rs ON r.rider_id = rs.rider_id
            WHERE rs.is_online = TRUE
        """)
        riders = cursor.fetchall()
        close_db_connection(connection, cursor)

        for rider in riders:
            if rider['latitude']:
                rider['latitude'] = float(rider['latitude'])
            if rider['longitude']:
                rider['longitude'] = float(rider['longitude'])
            if rider['last_updated']:
                rider['last_updated'] = rider['last_updated'].isoformat()
            if rider['last_location_time']:
                rider['last_location_time'] = rider['last_location_time'].isoformat()

        return jsonify({'success': True, 'count': len(riders), 'riders': riders}), 200

    except Exception as e:
        print(f"Get online riders error: {e}")
        return jsonify({'success': False, 'message': f'Server error: {str(e)}'}), 500

# ------------------- Socket.IO Events ------------------- #

@socketio.on('connect')
def handle_connect():
    print(f'Client connected: {request.sid}')
    emit('connection_response', {'status': 'connected', 'sid': request.sid})

@socketio.on('disconnect')
def handle_disconnect():
    rider_id = None
    for rid, sid in active_riders.items():
        if sid == request.sid:
            rider_id = rid
            break
    if rider_id:
        del active_riders[rider_id]
        print(f'Rider {rider_id} disconnected')

@socketio.on('rider_online')
def handle_rider_online(data):
    rider_id = data.get('rider_id')
    if rider_id:
        active_riders[rider_id] = request.sid
        emit('rider_status_changed', {
            'rider_id': rider_id,
            'is_online': True,
            'timestamp': datetime.now().isoformat()
        }, broadcast=True)

@socketio.on('rider_offline')
def handle_rider_offline(data):
    rider_id = data.get('rider_id')
    if rider_id and rider_id in active_riders:
        del active_riders[rider_id]
        emit('rider_status_changed', {
            'rider_id': rider_id,
            'is_online': False,
            'timestamp': datetime.now().isoformat()
        }, broadcast=True)

@socketio.on('update_location_realtime')
def handle_location_update(data):
    rider_id = data.get('rider_id')
    latitude = data.get('latitude')
    longitude = data.get('longitude')
    if rider_id and latitude and longitude:
        emit('rider_location_updated', {
            'rider_id': rider_id,
            'latitude': latitude,
            'longitude': longitude,
            'timestamp': datetime.now().isoformat()
        }, broadcast=True)

@app.route('/')
def index():
    return jsonify({'status': 'running', 'message': 'Rider API Server is running', 'active_riders': len(active_riders)})

if __name__ == '__main__':
    print("Starting Rider API Server...")
    socketio.run(app, host='0.0.0.0', port=5000, debug=True, allow_unsafe_werkzeug=True)