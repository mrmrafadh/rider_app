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

# Active riders dictionary to track Socket.IO connections
active_riders = {}


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
    """Login endpoint for rider authentication"""
    connection = None
    cursor = None
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
            # FIX 1: Get status from rider_status table (not is_online column directly)
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
        logger.error(f"Login error: {e}")
        if connection:
            close_db_connection(connection, cursor)
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

        # Validate input
        if rider_id is None:
            return jsonify({'success': False, 'message': 'Rider ID is required'}), 400

        if is_online is None:
            return jsonify({'success': False, 'message': 'Status is required'}), 400

        # FIX 2: Handle both integer (0/1) and boolean values from Flutter
        if isinstance(is_online, int):
            is_online = bool(is_online)
        elif isinstance(is_online, str):
            is_online = is_online.lower() == 'true'
        # If already boolean, leave as is

        connection = get_db_connection()
        if not connection:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500

        cursor = connection.cursor()

        # Verify rider exists
        cursor.execute("SELECT rider_id FROM riders WHERE rider_id = %s", (rider_id,))
        rider_exists = cursor.fetchone()

        if not rider_exists:
            close_db_connection(connection, cursor)
            return jsonify({'success': False, 'message': 'Rider not found'}), 404

        # FIX 3: Check if status record exists first
        cursor.execute("SELECT status_id FROM rider_status WHERE rider_id = %s", (rider_id,))
        status_exists = cursor.fetchone()

        if status_exists:
            # Update existing record
            cursor.execute("""
                UPDATE rider_status
                SET is_online = %s, last_updated = NOW()
                WHERE rider_id = %s
            """, (is_online, rider_id))
        else:
            # Insert new record
            cursor.execute("""
                INSERT INTO rider_status (rider_id, is_online, last_updated)
                VALUES (%s, %s, NOW())
            """, (rider_id, is_online))

        connection.commit()

        logger.info(f"✓ Status updated for rider {rider_id}: is_online={is_online}")

        # Emit status change to all connected clients
        socketio.emit('rider_status_changed', {
            'rider_id': rider_id,
            'is_online': is_online,
            'timestamp': datetime.now().isoformat()
        })

        close_db_connection(connection, cursor)
        return jsonify({
            'success': True,
            'message': 'Status updated successfully',
            'rider_id': rider_id,
            'is_online': is_online
        }), 200

    except psycopg2.Error as e:
        if connection:
            connection.rollback()
        logger.error(f"=== DATABASE ERROR in update_status ===")
        logger.error(f"Error: {e}")
        logger.error(f"Error code: {e.pgcode}")
        logger.error(f"Error message: {e.pgerror}")
        logger.error(f"Rider ID: {rider_id if 'rider_id' in locals() else 'N/A'}")
        close_db_connection(connection, cursor)
        return jsonify({
            'success': False,
            'message': f'Database error: {str(e)}'
        }), 500

    except Exception as e:
        if connection:
            connection.rollback()
        logger.error(f"=== GENERAL ERROR in update_status ===")
        logger.error(f"Error: {e}")
        logger.error(f"Error type: {type(e).__name__}")
        import traceback
        traceback.print_exc()
        close_db_connection(connection, cursor)
        return jsonify({
            'success': False,
            'message': f'Server error: {str(e)}'
        }), 500


@app.route('/api/update_location', methods=['POST'])
def update_location():
    """Update rider location - upsert with device timestamp"""
    connection = None
    cursor = None
    try:
        data = request.get_json()
        rider_id = data.get('rider_id')
        latitude = data.get('latitude')
        longitude = data.get('longitude')
        device_timestamp = data.get('timestamp')  # Get device timestamp from request

        if rider_id is None or latitude is None or longitude is None:
            return jsonify({'success': False, 'message': 'Rider ID, latitude, and longitude are required'}), 400

        # Validate latitude and longitude ranges
        try:
            lat = float(latitude)
            lng = float(longitude)
            if not (-90 <= lat <= 90) or not (-180 <= lng <= 180):
                return jsonify({'success': False, 'message': 'Invalid latitude or longitude values'}), 400
        except (ValueError, TypeError):
            return jsonify({'success': False, 'message': 'Latitude and longitude must be valid numbers'}), 400

        # Parse device timestamp or use current time
        location_time = None
        if device_timestamp:
            try:
                # Parse ISO 8601 timestamp from device
                location_time = datetime.fromisoformat(device_timestamp.replace('Z', '+00:00'))
            except (ValueError, AttributeError):
                logger.warning(f"Invalid timestamp format: {device_timestamp}, using server time")
                location_time = datetime.now()
        else:
            location_time = datetime.now()

        connection = get_db_connection()
        if not connection:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500

        cursor = connection.cursor()

        # Verify rider exists
        cursor.execute("SELECT rider_id FROM riders WHERE rider_id = %s", (rider_id,))
        if not cursor.fetchone():
            close_db_connection(connection, cursor)
            return jsonify({'success': False, 'message': 'Rider not found'}), 404

        # Check if location record exists for this rider
        cursor.execute("""
            SELECT location_id FROM rider_location 
            WHERE rider_id = %s 
            ORDER BY location_time DESC 
            LIMIT 1
        """, (rider_id,))

        existing_location = cursor.fetchone()

        if existing_location:
            # UPDATE existing record with latest location
            cursor.execute("""
                UPDATE rider_location 
                SET latitude = %s, 
                    longitude = %s, 
                    location_time = %s
                WHERE location_id = %s
            """, (lat, lng, location_time, existing_location['location_id']))
            logger.info(f"Updated location for rider {rider_id}")
        else:
            # INSERT new record (first time for this rider)
            cursor.execute("""
                INSERT INTO rider_location (rider_id, latitude, longitude, location_time)
                VALUES (%s, %s, %s, %s)
            """, (rider_id, lat, lng, location_time))
            logger.info(f"Inserted first location for rider {rider_id}")

        connection.commit()

        # Emit Socket.IO event with device timestamp
        socketio.emit('rider_location_updated', {
            'rider_id': rider_id,
            'latitude': lat,
            'longitude': lng,
            'timestamp': location_time.isoformat()
        })

        close_db_connection(connection, cursor)
        return jsonify({
            'success': True,
            'message': 'Location updated successfully',
            'timestamp': location_time.isoformat()
        }), 200

    except psycopg2.Error as e:
        if connection:
            connection.rollback()
        logger.error(f"Database error in update_location: {e}")
        close_db_connection(connection, cursor)
        return jsonify({'success': False, 'message': f'Database error: {str(e)}'}), 500
    except Exception as e:
        logger.error(f"Update location error: {e}")
        if connection:
            close_db_connection(connection, cursor)
        return jsonify({'success': False, 'message': f'Server error: {str(e)}'}), 500


@app.route('/api/rider/<int:rider_id>/location', methods=['GET'])
def get_rider_location(rider_id):
    """Get the latest location of a rider"""
    connection = None
    cursor = None
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
        logger.error(f"Get location error: {e}")
        if connection:
            close_db_connection(connection, cursor)
        return jsonify({'success': False, 'message': f'Server error: {str(e)}'}), 500


@app.route('/api/riders/online', methods=['GET'])
def get_online_riders():
    """Get all online riders with their latest locations"""
    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        if not connection:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500

        cursor = connection.cursor()
        # FIX 6: Added proper NULL handling and COALESCE for cleaner data
        cursor.execute("""
            SELECT
                r.rider_id,
                r.rider_name,
                COALESCE(rs.is_online, FALSE) as is_online,
                rs.last_updated,
                rl_latest.latitude,
                rl_latest.longitude,
                rl_latest.location_time as last_location_time
            FROM riders r
            LEFT JOIN rider_status rs ON r.rider_id = rs.rider_id
            LEFT JOIN LATERAL (
                SELECT latitude, longitude, location_time
                FROM rider_location
                WHERE rider_id = r.rider_id
                ORDER BY location_time DESC
                LIMIT 1
            ) rl_latest ON TRUE
            WHERE rs.is_online = TRUE
        """)
        riders = cursor.fetchall()
        close_db_connection(connection, cursor)

        # FIX 7: Proper type conversion and None handling
        riders_list = []
        for rider in riders:
            rider_dict = dict(rider)
            if rider_dict['latitude'] is not None:
                rider_dict['latitude'] = float(rider_dict['latitude'])
            if rider_dict['longitude'] is not None:
                rider_dict['longitude'] = float(rider_dict['longitude'])
            if rider_dict['last_updated']:
                rider_dict['last_updated'] = rider_dict['last_updated'].isoformat()
            if rider_dict['last_location_time']:
                rider_dict['last_location_time'] = rider_dict['last_location_time'].isoformat()
            riders_list.append(rider_dict)

        logger.info(f"Found {len(riders_list)} online riders")

        return jsonify({'success': True, 'count': len(riders_list), 'riders': riders_list}), 200

    except Exception as e:
        logger.error(f"Get online riders error: {e}")
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
    rider_id = None
    for rid, sid in active_riders.items():
        if sid == request.sid:
            rider_id = rid
            break
    if rider_id:
        del active_riders[rider_id]
        logger.info(f'Rider {rider_id} disconnected')
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
        logger.info(f'Rider {rider_id} marked as online via Socket.IO')
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
        logger.info(f'Rider {rider_id} marked as offline via Socket.IO')
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
        logger.info(f'Real-time location update for rider {rider_id}')
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
    connection = None
    try:
        # FIX 8: Added database health check
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


# ==================== AZURE APP SERVICE FIXES ====================
application = app

if __name__ == '__main__':
    logger.info("Starting Rider API Server...")
    socketio.run(app, host='0.0.0.0', port=5000, debug=True, allow_unsafe_werkzeug=True)