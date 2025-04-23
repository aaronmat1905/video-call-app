# server.py

import eventlet
eventlet.monkey_patch()

from flask import Flask, render_template, request, jsonify, send_from_directory, session
from flask_socketio import SocketIO, emit
from flask_cors import CORS
import socket
import ssl
import threading
import os
import logging
from utils.ssl_helper import generate_self_signed_cert
import time
import sys
import signal

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Global state
connected_clients = {}  # name → conn
active_calls = {}  # caller → callee
server_sockets = []  # Keep track of all server sockets

def cleanup_sockets():
    """Clean up all server sockets"""
    logger.info("Cleaning up server sockets...")
    for sock in server_sockets:
        try:
            sock.close()
        except Exception as e:
            logger.error(f"Error closing socket: {e}")
    server_sockets.clear()

def signal_handler(signum, frame):
    """Handle shutdown signals"""
    logger.info(f"Received signal {signum}. Shutting down...")
    cleanup_sockets()
    sys.exit(0)

# Register signal handlers
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

# 🔐 Generate certs if missing
if not (os.path.exists('cert.pem') and os.path.exists('key.pem')):
    logger.info("🔐 Generating self-signed certificates...")
    generate_self_signed_cert()

def is_port_in_use(port):
    """Check if a port is in use"""
    try:
        # Try TCP socket
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('0.0.0.0', port))
            # If we get here, port was not in use for TCP
            # Now try UDP socket
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as u:
                u.bind(('0.0.0.0', port))
                return False
    except socket.error:
        return True

def find_free_port(start_port, max_port=65535):
    """Find a free port starting from start_port"""
    current_port = start_port
    while current_port <= max_port:
        if not is_port_in_use(current_port):
            # Double check with a small delay to avoid race conditions
            time.sleep(0.1)
            if not is_port_in_use(current_port):
                return current_port
        current_port += 1
    raise RuntimeError(f"No free ports available in range {start_port}-{max_port}")

app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)
CORS(app, resources={
    r"/*": {
        "origins": "*",
        "allow_headers": ["Content-Type"],
        "methods": ["GET", "POST", "OPTIONS"]
    }
})

# Configure Socket.IO
socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    async_mode='eventlet',
    logger=True,
    engineio_logger=True,
    ping_timeout=60,
    ping_interval=25,
    max_http_buffer_size=1e8
)

# SSL Context Setup
def create_ssl_context():
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain('cert.pem', 'key.pem')
    return context

@app.route('/')
def index():
    """Serve the main page"""
    logger.info("Serving index page")
    return render_template('client.html')

@app.route('/static/<path:path>')
def serve_static(path):
    """Serve static files"""
    return send_from_directory('static', path)

@app.route('/connect', methods=['POST'])
def connect():
    """Handle initial HTTP connection"""
    try:
        if not request.is_json:
            logger.warning("Invalid connect request - not JSON")
            return jsonify({"error": "Content-Type must be application/json"}), 400

        data = request.get_json()
        logger.info(f"Connect request received: {data}")
        
        if not data or 'name' not in data:
            logger.warning("Invalid connect request - missing data")
            return jsonify({"error": "Name is required"}), 400
        
        name = data['name']
        if name in connected_clients:
            logger.warning(f"Name already taken: {name}")
            return jsonify({"error": "Name already taken"}), 400

        # Reserve the name but don't set the connection yet
        connected_clients[name] = None
        logger.info(f"User {name} connected successfully")
        return jsonify({"status": "success", "message": f"Welcome {name}!"})
    except Exception as e:
        logger.error(f"Error in connect: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@app.route('/call', methods=['POST'])
def call():
    try:
        data = request.get_json()
        logger.info(f"Call request received: {data}")
        
        if not data or 'target' not in data or 'caller' not in data:
            logger.warning("Invalid call request - missing data")
            return jsonify({"error": "Target and caller names required"}), 400

        caller = data['caller']
        target = data['target']

        # Verify caller exists and is connected
        if caller not in connected_clients or connected_clients[caller] is None:
            logger.warning(f"Unauthorized call attempt from {caller}")
            return jsonify({"error": "Not authorized"}), 401

        # Check if target exists and is connected
        if target not in connected_clients:
            logger.warning(f"Call target not found: {target}")
            return jsonify({"error": "User not found"}), 404

        target_sid = connected_clients[target]
        if not target_sid:
            logger.warning(f"Call target not connected: {target}")
            return jsonify({"error": "User is offline"}), 400

        # Check if either user is already in a call
        if target in active_calls.values() or caller in active_calls:
            logger.warning(f"Call failed - user busy")
            return jsonify({"error": "User is busy"}), 400

        # Emit incoming call event to target
        socketio.emit('incoming_call', {'caller': caller}, room=target_sid)
        logger.info(f"Call initiated from {caller} to {target}")
        
        return jsonify({"status": "success", "message": "Call initiated"})
    except Exception as e:
        logger.error(f"Error in call: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@app.route('/accept_call', methods=['POST'])
def accept_call():
    try:
        data = request.get_json()
        logger.info(f"Accept call request received: {data}")
        
        if not data or 'caller' not in data:
            logger.warning("Invalid accept request - missing caller")
            return jsonify({"error": "Caller name required"}), 400

        logger.info(f"Call accepted from {data['caller']}")
        return jsonify({"status": "success", "message": "Call accepted"})
    except Exception as e:
        logger.error(f"Error in accept_call: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@app.route('/reject_call', methods=['POST'])
def reject_call():
    try:
        data = request.get_json()
        logger.info(f"Reject call request received: {data}")
        
        if not data or 'caller' not in data:
            logger.warning("Invalid reject request - missing caller")
            return jsonify({"error": "Caller name required"}), 400

        logger.info(f"Call rejected from {data['caller']}")
        return jsonify({"status": "success", "message": "Call rejected"})
    except Exception as e:
        logger.error(f"Error in reject_call: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@app.route('/end_call', methods=['POST'])
def end_call():
    try:
        data = request.get_json()
        logger.info(f"End call request received: {data}")
        
        if not data or 'target' not in data:
            logger.warning("Invalid end request - missing target")
            return jsonify({"error": "Target name required"}), 400

        logger.info(f"Call ended with {data['target']}")
        return jsonify({"status": "success", "message": "Call ended"})
    except Exception as e:
        logger.error(f"Error in end_call: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500

# Control Channel
def control_server():
    try:
        control_port = find_free_port(31768)
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        secure_sock = create_ssl_context().wrap_socket(sock, server_side=True)
        secure_sock.bind(('0.0.0.0', control_port))
        secure_sock.listen(5)
        server_sockets.append(secure_sock)
        logger.info(f"🛠️ Control server running on port {control_port}...")

        while True:
            conn, addr = secure_sock.accept()
            threading.Thread(target=handle_control, args=(conn, addr)).start()
    except Exception as e:
        logger.error(f"[Control Server] Error: {e}")

def handle_control(conn, addr):
    client_name = None
    try:
        while True:
            data = conn.recv(1024).decode()
            if not data:
                break

            logger.info(f"[Control] From {addr}: {data}")

            if data.startswith("REGISTER|"):
                name = data.split('|')[1]
                if name in connected_clients:
                    conn.send("ERROR|Name already taken".encode())
                else:
                    client_name = name
                    connected_clients[name] = conn
                    logger.info(f"✅ Registered client: {name}")
                    conn.send("SUCCESS|Registered".encode())
                    broadcast_user_list()

            elif data.startswith("CALL|"):
                caller = get_name_from_conn(conn)
                target = data.split('|')[1]

                if not caller:
                    conn.send("ERROR|Not registered".encode())
                    continue

                logger.info(f"📞 {caller} wants to call {target}")

                if target in connected_clients:
                    if target in active_calls.values() or caller in active_calls:
                        conn.send(f"ERROR|User is busy".encode())
                    else:
                        target_conn = connected_clients[target]
                        target_conn.send(f"INCOMING|{caller}".encode())
                        active_calls[caller] = target
                        logger.info(f"📤 Forwarded call request to {target}")
                else:
                    conn.send(f"ERROR|User {target} not found".encode())

            elif data.startswith("ACCEPT|"):
                caller = data.split('|')[1]
                accepter = get_name_from_conn(conn)
                
                if caller in active_calls and active_calls[caller] == accepter:
                    connected_clients[caller].send(f"ACCEPTED|{accepter}".encode())
                    logger.info(f"✅ {accepter} accepted call from {caller}")
                else:
                    conn.send("ERROR|Invalid call acceptance".encode())

            elif data.startswith("REJECT|"):
                caller = data.split('|')[1]
                rejecter = get_name_from_conn(conn)
                
                if caller in active_calls and active_calls[caller] == rejecter:
                    connected_clients[caller].send(f"REJECTED|{rejecter}".encode())
                    del active_calls[caller]
                    logger.info(f"❌ {rejecter} rejected call from {caller}")

            elif data.startswith("END|"):
                ender = get_name_from_conn(conn)
                if ender in active_calls:
                    target = active_calls[ender]
                    connected_clients[target].send(f"END|{ender}".encode())
                    del active_calls[ender]
                else:
                    for caller, target in active_calls.items():
                        if target == ender:
                            connected_clients[caller].send(f"END|{ender}".encode())
                            del active_calls[caller]
                            break

    except Exception as e:
        logger.error(f"❌ Error in control handler: {e}")
    finally:
        if client_name:
            del connected_clients[client_name]
            broadcast_user_list()
        conn.close()

def broadcast_user_list():
    """Send updated user list to all connected clients"""
    user_list = list(connected_clients.keys())
    message = f"USERS|{','.join(user_list)}"
    for conn in connected_clients.values():
        try:
            conn.send(message.encode())
        except:
            pass

def get_name_from_conn(conn):
    """Get client name from connection object"""
    for name, c in connected_clients.items():
        if c == conn:
            return name
    return None

# Video Channel
def video_server():
    try:
        video_port = find_free_port(31769)  # Start after control port
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(('0.0.0.0', video_port))
        server_sockets.append(sock)
        logger.info(f"🎥 Video server listening on port {video_port}...")

        while True:
            data, addr = sock.recvfrom(65536)
            try:
                sender_addr = addr[0]
                sender = None
                recipient = None

                for name, client_addr in connected_clients.items():
                    if client_addr[0] == sender_addr:
                        sender = name
                        if sender in active_calls:
                            recipient = active_calls[sender]
                        else:
                            for caller, target in active_calls.items():
                                if target == sender:
                                    recipient = caller
                                    break
                        break

                if sender and recipient and recipient in connected_clients:
                    recipient_addr = connected_clients[recipient][1]
                    sock.sendto(data, recipient_addr)
            except Exception as e:
                logger.error(f"Error forwarding video: {e}")

    except Exception as e:
        logger.error(f"[Video Server] Error: {e}")

@socketio.on('test')
def handle_test(data):
    logger.info(f"🧪 Test received: {data}")
    socketio.emit('response', {'message': 'Hello from secure server!'})

@socketio.on('register')
def handle_register(data):
    try:
        name = data.get('name')
        if not name:
            emit('error', {'message': 'Name is required'})
            return
        
        logger.info(f"Socket registration request from {name}")
        
        if name in connected_clients:
            if connected_clients[name] is None:
                # This is a valid registration for a previously HTTP-connected client
                connected_clients[name] = request.sid
                logger.info(f"✅ Registered socket for {name}")
                
                # Send success response to the current client
                emit('registered', {
                    'status': 'success',
                    'users': [n for n, sid in connected_clients.items() if sid is not None]
                })
                
                # Broadcast updated user list to all clients
                broadcast_user_list()
            else:
                logger.warning(f"Duplicate socket registration attempt for {name}")
                emit('error', {'message': 'Already registered'})
        else:
            logger.warning(f"Socket registration attempt without HTTP connection for {name}")
            emit('error', {'message': 'Please connect via web interface first'})
    except Exception as e:
        logger.error(f"Error in socket registration: {e}")
        emit('error', {'message': 'Registration failed'})

@socketio.on('connect')
def handle_connect():
    logger.info(f"Client connected: {request.sid}")
    emit('connect_response', {'status': 'success'})

@socketio.on('disconnect')
def handle_disconnect():
    try:
        # Find the disconnected client
        sid = request.sid
        for name, client_sid in connected_clients.items():
            if client_sid == sid:
                # Mark the client as HTTP-only connected (no socket)
                connected_clients[name] = None
                logger.info(f"Client disconnected: {name}")
                
                # Broadcast updated user list to all remaining clients
                broadcast_user_list()
                break
    except Exception as e:
        logger.error(f"Error in disconnect handler: {e}")

@socketio.on_error_default
def default_error_handler(e):
    logger.error(f"Socket.IO error: {str(e)}")
    emit('error', {'message': str(e)})

if __name__ == "__main__":
    try:
        # Start control and video servers
        threading.Thread(target=control_server, daemon=True).start()
        threading.Thread(target=video_server, daemon=True).start()

        # Try to find an available port for Flask-SocketIO
        port = find_free_port(31770)  # Start after video port
        logger.info(f"🚀 Starting Flask-SocketIO server on port {port}...")
        
        # Create a socket and wrap it with SSL
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        # Create eventlet SSL context
        ssl_context = eventlet.wrap_ssl(
            sock,
            certfile='cert.pem',
            keyfile='key.pem',
            server_side=True
        )
        
        # Add to server sockets for cleanup
        server_sockets.append(sock)
        
        socketio.run(
            app,
            host='0.0.0.0',
            port=port,
            sock=ssl_context
        )
    except Exception as e:
        logger.error(f"Error starting server: {e}")
        if 'sock' in locals():
            try:
                sock.close()
            except:
                pass
    finally:
        cleanup_sockets()