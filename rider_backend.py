# IMPORTANT: Add eventlet monkey patching FIRST
import eventlet

eventlet.monkey_patch()

from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit
from flask_cors import CORS
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
import os
from dotenv import load_dotenv
import logging
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('app.log')
    ]
)

logger = logging.getLogger(__name__)

app = Flask(__name__)

CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

load_dotenv()

DB_CONFIG = {
    'host': os.environ.get('DB_HOST'),
    'port': int(os.environ.get('DB_PORT', 5432)),
    'database': os.environ.get('DB_NAME'),
    'user': os.environ.get('DB_USER'),
    'password': os.environ.get('DB_PASSWORD')
}

# Active users dictionary to track Socket.IO connections
active_users = {}


def get_db_connection():
    """Create and return a PostgreSQL database connection"""
    try:
        connection = psycopg2.connect(**DB_CONFIG, cursor_factory=RealDictCursor, sslmode='require')
        logger.info("Database connection established")
        return connection
    except Exception as e:
        logger.error(f"Error connecting to PostgreSQL: {e}")
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
    """Login endpoint for user authentication"""
    connection = None
    cursor = None
    try:
        data = request.get_json()
        username = data.get('username')  # Changed from rider_name
        password = data.get('password')

        if not username or not password:
            return jsonify({'success': False, 'message': 'Username and password are required'}), 400

        connection = get_db_connection()
        if not connection:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500

        cursor = connection.cursor()

        # Updated Query for 'users' table
        cursor.execute("SELECT user_id, username, password, role FROM users WHERE username = %s", (username,))
        user = cursor.fetchone()

        if user and user['password'] == password:
            # Get online status
            cursor.execute("SELECT is_online FROM rider_status WHERE user_id = %s", (user['user_id'],))
            status = cursor.fetchone()

            response = {
                'success': True,
                'user_id': user['user_id'],
                'username': user['username'],
                'role': user['role'],  # Return the role
                'is_online': status['is_online'] if status else False,
                'message': 'Login successful'
            }
            close_db_connection(connection, cursor)
            return jsonify(response), 200
        else:
            close_db_connection(connection, cursor)
            return jsonify({'success': False, 'message': 'Invalid username or password'}), 401

    except Exception as e:
        logger.error(f"Login error: {e}")
        if connection:
            close_db_connection(connection, cursor)
        return jsonify({'success': False, 'message': f'Server error: {str(e)}'}), 500


@app.route('/api/update_status', methods=['POST'])
def update_status():
    """Update user online/offline status"""
    connection = None
    cursor = None
    try:
        data = request.get_json()
        user_id = data.get('user_id')  # Changed from rider_id
        is_online = data.get('is_online')

        if user_id is None:
            return jsonify({'success': False, 'message': 'User ID is required'}), 400

        if is_online is None:
            return jsonify({'success': False, 'message': 'Status is required'}), 400

        # Handle boolean conversion
        if isinstance(is_online, int):
            is_online = bool(is_online)
        elif isinstance(is_online, str):
            is_online = is_online.lower() == 'true'

        connection = get_db_connection()
        if not connection:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500

        cursor = connection.cursor()

        # Verify user exists
        cursor.execute("SELECT user_id FROM users WHERE user_id = %s", (user_id,))
        user_exists = cursor.fetchone()

        if not user_exists:
            close_db_connection(connection, cursor)
            return jsonify({'success': False, 'message': 'User not found'}), 404

        # Check status existence
        cursor.execute("SELECT status_id FROM rider_status WHERE user_id = %s", (user_id,))
        status_exists = cursor.fetchone()

        if status_exists:
            cursor.execute("""
                UPDATE rider_status
                SET is_online = %s, last_updated = NOW()
                WHERE user_id = %s
            """, (is_online, user_id))
        else:
            cursor.execute("""
                INSERT INTO rider_status (user_id, is_online, last_updated)
                VALUES (%s, %s, NOW())
            """, (user_id, is_online))

        connection.commit()

        logger.info(f"✓ Status updated for user {user_id}: is_online={is_online}")

        # Emit status change with new key names
        socketio.emit('rider_status_changed', {
            'user_id': user_id,
            'rider_id': user_id,  # Keep for backward compatibility if needed temporarily
            'is_online': is_online,
            'timestamp': datetime.now().isoformat()
        })

        close_db_connection(connection, cursor)
        return jsonify({
            'success': True,
            'message': 'Status updated successfully',
            'user_id': user_id,
            'is_online': is_online
        }), 200

    except Exception as e:
        if connection:
            connection.rollback()
        logger.error(f"Status update error: {e}")
        if connection:
            close_db_connection(connection, cursor)
        return jsonify({'success': False, 'message': f'Server error: {str(e)}'}), 500


@app.route('/api/update_location', methods=['POST'])
def update_location():
    """Update user location"""
    connection = None
    cursor = None
    try:
        data = request.get_json()
        user_id = data.get('user_id')  # Changed from rider_id
        latitude = data.get('latitude')
        longitude = data.get('longitude')
        device_timestamp = data.get('timestamp')

        if user_id is None or latitude is None or longitude is None:
            return jsonify({'success': False, 'message': 'User ID, latitude, and longitude are required'}), 400

        # Validate lat/lng
        try:
            lat = float(latitude)
            lng = float(longitude)
        except (ValueError, TypeError):
            return jsonify({'success': False, 'message': 'Invalid coordinates'}), 400

        # Parse timestamp
        location_time = datetime.now()
        if device_timestamp:
            try:
                location_time = datetime.fromisoformat(device_timestamp.replace('Z', '+00:00'))
            except:
                pass

        connection = get_db_connection()
        if not connection:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500

        cursor = connection.cursor()

        # Check if location record exists
        cursor.execute("""
            SELECT location_id FROM rider_location 
            WHERE user_id = %s 
            ORDER BY location_time DESC 
            LIMIT 1
        """, (user_id,))

        existing_location = cursor.fetchone()

        if existing_location:
            cursor.execute("""
                UPDATE rider_location 
                SET latitude = %s, longitude = %s, location_time = %s
                WHERE location_id = %s
            """, (lat, lng, location_time, existing_location['location_id']))
        else:
            cursor.execute("""
                INSERT INTO rider_location (user_id, latitude, longitude, location_time)
                VALUES (%s, %s, %s, %s)
            """, (user_id, lat, lng, location_time))

        connection.commit()

        # Emit Socket event - IMPORTANT: Sending 'update_location_realtime' as requested by client mismatch check
        # But wait, the client LISTENS to 'update_location_realtime' from the server?
        # Usually client EMITS 'update_location_realtime' and server EMITS 'rider_location_updated'.
        # I will emit BOTH to be safe based on your previous debugging.

        payload = {
            'user_id': user_id,
            'rider_id': user_id,  # Backward compatibility
            'latitude': lat,
            'longitude': lng,
            'timestamp': location_time.isoformat()
        }

        # Standard event
        socketio.emit('rider_location_updated', payload)
        # The one you fixed in the Flutter Admin Dashboard
        socketio.emit('update_location_realtime', payload)

        close_db_connection(connection, cursor)
        return jsonify({
            'success': True,
            'message': 'Location updated successfully',
            'timestamp': location_time.isoformat()
        }), 200

    except Exception as e:
        logger.error(f"Update location error: {e}")
        if connection:
            close_db_connection(connection, cursor)
        return jsonify({'success': False, 'message': f'Server error: {str(e)}'}), 500


@app.route('/api/riders/online', methods=['GET'])
def get_online_users():
    """Get all online USERS (riders)"""
    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        if not connection:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500

        cursor = connection.cursor()

        # Updated query to use 'users' table and 'user_id'
        # Added filter WHERE role = 'rider' so admins don't show up on the map
        cursor.execute("""
            SELECT
                u.user_id,
                u.username,
                u.role,
                COALESCE(rs.is_online, FALSE) as is_online,
                rs.last_updated,
                rl_latest.latitude,
                rl_latest.longitude,
                rl_latest.location_time as last_location_time
            FROM users u
            LEFT JOIN rider_status rs ON u.user_id = rs.user_id
            LEFT JOIN LATERAL (
                SELECT latitude, longitude, location_time
                FROM rider_location
                WHERE user_id = u.user_id
                ORDER BY location_time DESC
                LIMIT 1
            ) rl_latest ON TRUE
            WHERE rs.is_online = TRUE AND u.role = 'rider'
        """)
        users = cursor.fetchall()
        close_db_connection(connection, cursor)

        riders_list = []
        for user in users:
            u_dict = dict(user)
            # Map new DB columns to expected Frontend JSON keys if needed
            u_dict['rider_id'] = u_dict['user_id']  # Add alias for compatibility
            u_dict['rider_name'] = u_dict['username']  # Add alias for compatibility

            if u_dict['latitude'] is not None:
                u_dict['latitude'] = float(u_dict['latitude'])
            if u_dict['longitude'] is not None:
                u_dict['longitude'] = float(u_dict['longitude'])
            if u_dict['last_updated']:
                u_dict['last_updated'] = u_dict['last_updated'].isoformat()
            if u_dict['last_location_time']:
                u_dict['last_location_time'] = u_dict['last_location_time'].isoformat()
            riders_list.append(u_dict)

        return jsonify({'success': True, 'count': len(riders_list), 'riders': riders_list}), 200

    except Exception as e:
        logger.error(f"Get online users error: {e}")
        if connection:
            close_db_connection(connection, cursor)
        return jsonify({'success': False, 'message': f'Server error: {str(e)}'}), 500


# ------------------- Socket.IO Events ------------------- #

@socketio.on('connect')
def handle_connect():
    logger.info(f'Client connected: {request.sid}')
    emit('connection_response', {'status': 'connected', 'sid': request.sid})


@socketio.on('disconnect')
def handle_disconnect():
    user_id = None
    for uid, sid in active_users.items():
        if sid == request.sid:
            user_id = uid
            break
    if user_id:
        del active_users[user_id]
        logger.info(f'User {user_id} disconnected')
        socketio.emit('rider_status_changed', {
            'user_id': user_id,
            'rider_id': user_id,
            'is_online': False,
            'timestamp': datetime.now().isoformat()
        }, broadcast=True)


# Handle Realtime location from Frontend Socket
@socketio.on('update_location_realtime')
def handle_location_update(data):
    # Support both key styles
    user_id = data.get('user_id') or data.get('rider_id')
    latitude = data.get('latitude')
    longitude = data.get('longitude')

    if user_id and latitude and longitude:
        payload = {
            'user_id': user_id,
            'rider_id': user_id,
            'latitude': latitude,
            'longitude': longitude,
            'timestamp': datetime.now().isoformat()
        }
        # Emit back to Admin Dashboard
        # Admin is listening to 'update_location_realtime' based on your fix
        emit('update_location_realtime', payload, broadcast=True)
        # Emit standard event too
        emit('rider_location_updated', payload, broadcast=True)


@app.route('/')
def index():
    return jsonify({
        'status': 'running',
        'message': 'Rider API Server is running (Schema Updated)',
        'active_users': len(active_users),
        'version': '2.0'
    })


@app.route('/health')
def health_check():
    connection = None
    try:
        connection = get_db_connection()
        if connection:
            cursor = connection.cursor()
            cursor.execute("SELECT 1")
            cursor.fetchone()
            close_db_connection(connection, cursor)
            db_status = 'connected'
        else:
            db_status = 'disconnected'
    except Exception as e:
        db_status = f'error: {str(e)}'
        if connection:
            close_db_connection(connection)

    return jsonify({
        'status': 'healthy',
        'database': db_status,
        'timestamp': datetime.now().isoformat()
    }), 200


application = app

if __name__ == '__main__':
    logger.info("Starting API Server...")
    socketio.run(app, host='0.0.0.0', port=5000, debug=True, allow_unsafe_werkzeug=True)