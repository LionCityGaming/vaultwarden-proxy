from flask import Flask, jsonify
import requests
import os
import logging
import time
from datetime import datetime, timedelta

app = Flask(__name__)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Vaultwarden configuration from environment variables
VAULTWARDEN_URL = os.environ.get('VAULTWARDEN_URL', 'http://vaultwarden:80')
ADMIN_TOKEN = os.environ.get('ADMIN_TOKEN')
CACHE_TIMEOUT = int(os.environ.get('CACHE_TIMEOUT', 300))  # 5 minutes default

# Session cache
_stats_cache = {
    'stats': None,
    'last_fetch': 0,
    'session_cookie': None,
    'cookie_expiry': 0
}

def get_admin_session():
    """Authenticate with Vaultwarden admin and get session cookie"""
    now = time.time()

    # Check if we have a valid cached session
    if (_stats_cache['session_cookie'] and
        now < _stats_cache['cookie_expiry']):
        logger.info("Using cached admin session")
        return _stats_cache['session_cookie']

    if not ADMIN_TOKEN:
        raise Exception("ADMIN_TOKEN not configured")

    # Authenticate with admin panel
    # Use form data for authentication
    auth_response = requests.post(
        f'{VAULTWARDEN_URL}/admin',
        data={'token': ADMIN_TOKEN},
        headers={'Content-Type': 'application/x-www-form-urlencoded'},
        timeout=10,
        allow_redirects=False
    )

    if auth_response.status_code not in [200, 302]:
        logger.error(f"Auth response status: {auth_response.status_code}")
        logger.error(f"Auth response body: {auth_response.text[:200]}")
        raise Exception(f"Admin authentication failed: {auth_response.status_code}")

    # Extract session cookie (VW_ADMIN)
    session_cookie = auth_response.cookies.get_dict()
    if not session_cookie or 'VW_ADMIN' not in session_cookie:
        logger.error(f"Cookies received: {session_cookie}")
        raise Exception("No VW_ADMIN cookie received from Vaultwarden")

    # Cache the session for 1 hour
    _stats_cache['session_cookie'] = session_cookie
    _stats_cache['cookie_expiry'] = now + 3600

    logger.info("Successfully authenticated with Vaultwarden admin")
    return session_cookie

def get_vaultwarden_stats():
    """Fetch statistics from Vaultwarden admin API"""
    # Check cache first
    now = time.time()
    if (_stats_cache['stats'] and
        now - _stats_cache['last_fetch'] < CACHE_TIMEOUT):
        logger.info("Returning cached stats")
        return _stats_cache['stats']

    # Get authenticated session
    cookies = get_admin_session()

    try:
        # Get users data
        users_response = requests.get(
            f'{VAULTWARDEN_URL}/admin/users',
            cookies=cookies,
            timeout=10
        )
        users_response.raise_for_status()
        users_data = users_response.json()

        # Calculate statistics
        total_users = len(users_data)

        # Log first user structure for debugging
        if users_data and len(users_data) > 0:
            logger.info(f"Sample user fields: {list(users_data[0].keys())}")

        # Count active users (logged in within last 30 days)
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        active_users = 0

        # Aggregate item counts
        total_items = 0
        items_by_type = {
            'logins': 0,
            'notes': 0,
            'cards': 0,
            'identities': 0
        }

        for user in users_data:
            # Check if user is active (try both field name variations)
            last_active = user.get('lastActive') or user.get('_LastActive')
            if last_active:
                try:
                    # Parse the timestamp - Vaultwarden format: "2026-01-15 07:58:02 +08"
                    # Remove timezone info for simplicity and parse
                    last_active_str = last_active.split('+')[0].strip()
                    last_active_dt = datetime.strptime(last_active_str, '%Y-%m-%d %H:%M:%S')
                    if last_active_dt > thirty_days_ago:
                        active_users += 1
                except (ValueError, AttributeError) as e:
                    logger.debug(f"Error parsing last active date for user {user.get('email')}: {e} - raw value: {last_active}")
                    pass

            # Count user's cipher items (Vaultwarden may not include this in basic user list)
            # Try different possible field names
            cipher_count = user.get('CipherCount', 0) or user.get('cipher_count', 0) or user.get('items_count', 0)
            total_items += cipher_count

        # Note: Vaultwarden admin API doesn't expose item type breakdown per user
        # We'll need to get this from a different endpoint if available
        # For now, we'll try the /admin/diagnostics endpoint for additional data

        try:
            diag_response = requests.get(
                f'{VAULTWARDEN_URL}/admin/diagnostics',
                cookies=cookies,
                timeout=10
            )
            if diag_response.status_code == 200:
                diag_data = diag_response.json()
                logger.debug(f"Diagnostics data available: {diag_data.keys()}")
        except Exception as e:
            logger.debug(f"Could not fetch diagnostics: {e}")

        result = {
            'total_users': total_users,
            'active_users': active_users,
            'total_items': total_items,
            'logins': items_by_type['logins'],
            'notes': items_by_type['notes'],
            'cards': items_by_type['cards'],
            'identities': items_by_type['identities']
        }

        # Update cache
        _stats_cache['stats'] = result
        _stats_cache['last_fetch'] = now

        logger.info(f"Fetched stats: {result}")
        return result

    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching Vaultwarden stats: {e}")
        raise

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return 'OK', 200

@app.route('/stats', methods=['GET'])
def stats():
    """Get Vaultwarden statistics"""
    try:
        if not ADMIN_TOKEN:
            return jsonify({
                'error': 'ADMIN_TOKEN environment variable is required'
            }), 500

        stats_data = get_vaultwarden_stats()
        return jsonify(stats_data), 200
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching Vaultwarden stats: {e}")
        return jsonify({'error': str(e)}), 500
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
