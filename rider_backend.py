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
# In your main Python file (app.py, main.py, etc.)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),  # This sends to Azure logs
        logging.FileHandler('app.log')      # Optional: local file
    ]
)

logger = logging.getLogger(__name__)

app = Flask(__name__)

CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

load_dotenv()  # loads variables from .env

DB_CONFIG = {
    'host': os.environ.get('DB_HOST'),
    'port': int(os.environ.get('DB_PORT', 5432)),
    'database': os.environ.get('DB_NAME'),
    'user': os.environ.get('DB_USER'),
    'password': os.environ.get('DB_PASSWORD')
}

# Active riders dictionary to track Socket.IO connections
active_riders = {}


def get_db_connection():
    """Create and return a PostgreSQL database connection"""
    try:
        connection = psycopg2.connect(**DB_CONFIG, cursor_factory=RealDictCursor, sslmode='require')
        print("rafath")
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
    try:
        data = request.get_json()
        print(f"[DEBUG UPDATE_STATUS] Request data: {data}")

        rider_id = data.get('rider_id')
        is_online_param = data.get('is_online')

        print(f"[DEBUG] rider_id: {rider_id}, is_online_param: {is_online_param}, type: {type(is_online_param)}")

        if rider_id is None:
            return jsonify({'success': False, 'message': 'Missing rider_id'}), 400

        if is_online_param is None:
            return jsonify({'success': False, 'message': 'Missing is_online'}), 400

        # Convert to boolean - handle both integer and string
        if isinstance(is_online_param, int):
            is_online_bool = True if is_online_param == 1 else False
        elif isinstance(is_online_param, str):
            is_online_bool = True if is_online_param.lower() in ['true', '1', 'yes'] else False
        else:
            is_online_bool = bool(is_online_param)

        print(f"[DEBUG] Converted is_online_bool: {is_online_bool}")

        conn = get_db_connection()
        cursor = conn.cursor()

        # First, check current status
        cursor.execute("SELECT rider_name, is_online FROM riders WHERE rider_id = %s", (rider_id,))
        current_data = cursor.fetchone()

        if not current_data:
            cursor.close()
            conn.close()
            return jsonify({'success': False, 'message': 'Rider not found'}), 404

        print(f"[DEBUG] Current data: {current_data}")

        # Update the status
        update_query = """
        UPDATE riders 
        SET is_online = %s, 
            last_activity = NOW()
        WHERE rider_id = %s
        RETURNING rider_id, rider_name, is_online;
        """

        print(f"[DEBUG] Executing: {update_query}")
        print(f"[DEBUG] With values: ({is_online_bool}, {rider_id})")

        cursor.execute(update_query, (is_online_bool, rider_id))
        updated_row = cursor.fetchone()

        print(f"[DEBUG] Updated row: {updated_row}")

        conn.commit()

        # Verify the update
        cursor.execute("SELECT rider_name, is_online FROM riders WHERE rider_id = %s", (rider_id,))
        verified_data = cursor.fetchone()
        print(f"[DEBUG] Verified data after update: {verified_data}")

        cursor.close()
        conn.close()

        if updated_row:
            return jsonify({
                'success': True,
                'message': f"Status updated to {'online' if is_online_bool else 'offline'}",
                'rider_id': updated_row['rider_id'],
                'rider_name': updated_row['rider_name'],
                'is_online': updated_row['is_online']
            })
        else:
            return jsonify({'success': False, 'message': 'Update failed - no rows affected'}), 500

    except Exception as e:
        print(f"[ERROR] Exception in update_status: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'Server error: {str(e)}'
        }), 500


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
    try:
        print("[DEBUG GET_ONLINE_RIDERS] Received request")

        conn = get_db_connection()
        cursor = conn.cursor()

        # First, check if the riders table has is_online column
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'riders' AND column_name = 'is_online';
        """)
        has_is_online = cursor.fetchone()
        print(f"[DEBUG] Has is_online column: {has_is_online}")

        # Simple query to get all online riders
        query = """
        SELECT 
            rider_id,
            rider_name,
            is_online,
            last_activity
        FROM riders 
        WHERE is_online = TRUE
        ORDER BY rider_id;
        """

        print(f"[DEBUG] Executing query: {query}")
        cursor.execute(query)
        riders = cursor.fetchall()

        print(f"[DEBUG] Found {len(riders)} online riders")
        for rider in riders:
            print(f"[DEBUG] Rider: {rider}")

        # Get locations for these riders
        riders_with_locations = []
        for rider in riders:
            # Get latest location for each rider
            cursor.execute("""
                SELECT latitude, longitude, last_updated
                FROM rider_locations 
                WHERE rider_id = %s
                ORDER BY last_updated DESC
                LIMIT 1;
            """, (rider['rider_id'],))

            location = cursor.fetchone()

            riders_with_locations.append({
                'rider_id': rider['rider_id'],
                'rider_name': rider['rider_name'],
                'latitude': float(location['latitude']) if location and location['latitude'] else None,
                'longitude': float(location['longitude']) if location and location['longitude'] else None,
                'last_updated': location['last_updated'].isoformat() if location and location['last_updated'] else None,
                'is_online': rider['is_online'],
                'last_activity': rider['last_activity'].isoformat() if rider['last_activity'] else None
            })

        cursor.close()
        conn.close()

        return jsonify({
            'success': True,
            'count': len(riders_with_locations),
            'riders': riders_with_locations
        })

    except Exception as e:
        print(f"[ERROR] Exception in get_online_riders: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'Server error: {str(e)}'
        }), 500

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
        # Emit offline status
        socketio.emit('rider_status_changed', {
            'rider_id': rider_id,
            'is_online': False,
            'timestamp': datetime.now().isoformat()
        }, broadcast=True)

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
    return jsonify({
        'status': 'running',
        'message': 'Rider API Server is running',
        'active_riders': len(active_riders),
        'version': '1.0'
    })

@app.route('/health')
def health_check():
    """Health check endpoint for Azure App Service"""
    return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()}), 200

# ==================== AZURE APP SERVICE FIXES ====================
# This variable is required for Azure App Service to find the Flask app
# When gunicorn runs with rider_backend:application, it looks for this variable
application = app

if __name__ == '__main__':
    print("Starting Rider API Server...")
    # For local development
    socketio.run(app, host='0.0.0.0', port=5000, debug=True, allow_unsafe_werkzeug=True)