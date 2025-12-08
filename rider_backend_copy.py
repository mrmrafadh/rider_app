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
import json
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
    """Update rider online/offline status"""
    connection = None
    cursor = None
    try:
        data = request.get_json()
        rider_id = data.get('rider_id')
        is_online = data.get('is_online')

        print(f"[DEBUG UPDATE_STATUS] Received request: rider_id={rider_id}, is_online={is_online}")

        # Validate input
        if rider_id is None:
            return jsonify({'success': False, 'message': 'Rider ID is required'}), 400

        if is_online is None:
            return jsonify({'success': False, 'message': 'Status is required'}), 400

        # Convert to boolean
        if isinstance(is_online, bool):
            is_online_bool = is_online
        elif isinstance(is_online, int):
            is_online_bool = bool(is_online)
        elif isinstance(is_online, str):
            is_online_bool = is_online.lower() in ['true', '1', 'yes']
        else:
            is_online_bool = bool(is_online)

        print(f"[DEBUG] Converted is_online to boolean: {is_online_bool}")

        connection = get_db_connection()
        if not connection:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500

        cursor = connection.cursor()

        # Verify rider exists
        cursor.execute("SELECT rider_id, rider_name FROM riders WHERE rider_id = %s", (rider_id,))
        rider_exists = cursor.fetchone()

        if not rider_exists:
            close_db_connection(connection, cursor)
            return jsonify({'success': False, 'message': 'Rider not found'}), 404

        print(f"[DEBUG] Rider found: {rider_exists['rider_name']} (ID: {rider_exists['rider_id']})")

        # Check current status
        cursor.execute("SELECT is_online FROM rider_status WHERE rider_id = %s", (rider_id,))
        current_status = cursor.fetchone()
        print(f"[DEBUG] Current status: {current_status}")

        # Update status
        print(f"[DEBUG] Updating status to: {is_online_bool}")
        cursor.execute("""
            INSERT INTO rider_status (rider_id, is_online, last_updated)
            VALUES (%s, %s, NOW())
            ON CONFLICT (rider_id)
            DO UPDATE SET
                is_online = EXCLUDED.is_online,
                last_updated = NOW()
            RETURNING is_online
        """, (rider_id, is_online_bool))

        updated_status = cursor.fetchone()
        print(f"[DEBUG] Updated status returned: {updated_status}")

        connection.commit()

        # Verify the update
        cursor.execute("SELECT is_online FROM rider_status WHERE rider_id = %s", (rider_id,))
        verified_status = cursor.fetchone()
        print(f"[DEBUG] Verified status: {verified_status}")

        # Get rider name for response
        cursor.execute("SELECT rider_name FROM riders WHERE rider_id = %s", (rider_id,))
        rider_name_result = cursor.fetchone()
        rider_name = rider_name_result['rider_name'] if rider_name_result else "Unknown"

        print(f"✓ Status updated for rider {rider_id} ({rider_name}): is_online={is_online_bool}")


        close_db_connection(connection, cursor)
        return jsonify({
            'success': True,
            'message': 'Status updated successfully',
            'rider_id': rider_id,
            'rider_name': rider_name,
            'is_online': is_online_bool
        }), 200

    except psycopg2.Error as e:
        if connection:
            connection.rollback()
        print(f"=== DATABASE ERROR in update_status ===")
        print(f"Error: {e}")
        print(f"Error code: {e.pgcode}")
        print(f"Error message: {e.pgerror}")
        close_db_connection(connection, cursor)
        return jsonify({
            'success': False,
            'message': f'Database error: {str(e)}'
        }), 500

    except Exception as e:
        if connection:
            connection.rollback()
        print(f"=== GENERAL ERROR in update_status ===")
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        close_db_connection(connection, cursor)
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
    """Get all online riders with their latest locations"""
    connection = None
    cursor = None
    try:
        print("[DEBUG] Fetching online riders...")

        connection = get_db_connection()
        if not connection:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500

        cursor = connection.cursor()

        # First, let's check what's in the tables
        print("[DEBUG] Checking rider_status table...")
        cursor.execute("SELECT rider_id, is_online, last_updated FROM rider_status ORDER BY rider_id")
        status_rows = cursor.fetchall()
        print(f"[DEBUG] Found {len(status_rows)} rows in rider_status:")
        for row in status_rows:
            print(f"  Rider {row['rider_id']}: is_online={row['is_online']}, last_updated={row['last_updated']}")

        print("[DEBUG] Checking riders table...")
        cursor.execute("SELECT rider_id, rider_name FROM riders ORDER BY rider_id")
        all_riders = cursor.fetchall()
        print(f"[DEBUG] Found {len(all_riders)} total riders")

        # Now the main query - FIXED VERSION
        print("[DEBUG] Executing main query for online riders...")
        query = """
        SELECT
            r.rider_id,
            r.rider_name,
            COALESCE(rs.is_online, FALSE) as is_online,
            rs.last_updated,
            rl.latitude,
            rl.longitude,
            rl.location_time as last_location_time
        FROM riders r
        LEFT JOIN rider_status rs ON r.rider_id = rs.rider_id
        LEFT JOIN (
            SELECT DISTINCT ON (rider_id) 
                rider_id, 
                latitude, 
                longitude, 
                location_time
            FROM rider_location
            ORDER BY rider_id, location_time DESC
        ) rl ON r.rider_id = rl.rider_id
        WHERE COALESCE(rs.is_online, FALSE) = TRUE
        ORDER BY r.rider_id
        """

        print(f"[DEBUG] Query: {query}")
        cursor.execute(query)
        riders = cursor.fetchall()

        print(f"[DEBUG] Query returned {len(riders)} riders")

        # If no riders returned but we know some should be online, check manually
        if len(riders) == 0 and len(status_rows) > 0:
            print("[DEBUG] No riders returned from main query, checking manually...")
            # Get riders who should be online
            cursor.execute("""
                SELECT r.rider_id, r.rider_name 
                FROM riders r
                JOIN rider_status rs ON r.rider_id = rs.rider_id
                WHERE rs.is_online = TRUE
            """)
            online_ids = cursor.fetchall()
            print(f"[DEBUG] Manual check found {len(online_ids)} online riders: {online_ids}")

            # Try a simpler query
            cursor.execute("""
                SELECT r.rider_id, r.rider_name, rs.is_online, rs.last_updated
                FROM riders r
                JOIN rider_status rs ON r.rider_id = rs.rider_id
                WHERE rs.is_online = TRUE
            """)
            simple_result = cursor.fetchall()
            print(f"[DEBUG] Simple query result: {simple_result}")

            # Use the simple result
            riders = simple_result

        close_db_connection(connection, cursor)

        # Format the response
        riders_list = []
        for rider in riders:
            rider_data = {
                'rider_id': rider['rider_id'],
                'rider_name': rider['rider_name'],
                'is_online': bool(rider['is_online']),
            }

            # Add last_updated if available
            if rider.get('last_updated'):
                rider_data['last_updated'] = rider['last_updated'].isoformat()

            # Add location if available
            if rider.get('latitude') is not None:
                rider_data['latitude'] = float(rider['latitude'])
            if rider.get('longitude') is not None:
                rider_data['longitude'] = float(rider['longitude'])
            if rider.get('last_location_time'):
                rider_data['location_time'] = rider['last_location_time'].isoformat()

            riders_list.append(rider_data)

        print(
            f"[DEBUG] Final response: {json.dumps({'success': True, 'count': len(riders_list), 'riders': riders_list}, indent=2)}")

        return jsonify({
            'success': True,
            'count': len(riders_list),
            'riders': riders_list
        }), 200

    except Exception as e:
        print(f"[ERROR] Get online riders error: {e}")
        import traceback
        traceback.print_exc()
        if connection:
            close_db_connection(connection, cursor)
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