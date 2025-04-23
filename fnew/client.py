# client.py

from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO
from flask_cors import CORS

import socket
import os
import ssl
import threading
import cv2
import numpy as np
import base64
import pyaudio
import wave
import time
from utils.ssl_helper import generate_self_signed_cert
import logging
import json
import sys

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 🔐 Generate certs if missing
if not (os.path.exists('cert.pem') and os.path.exists('key.pem')):
    logger.info("🔐 Generating self-signed certificates...")
    generate_self_signed_cert()

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes
socketio = SocketIO(app, cors_allowed_origins='*', ping_timeout=10, ping_interval=5)

# Global client state
client_state = {
    'name': '',
    'server_ip': '127.0.0.1',
    'control_socket': None,
    'video_socket': None,
    'audio_socket': None,
    'current_call': None,
    'stream': None,
    'audio_stream': None,
    'connected': False,
    'reconnecting': False
}

# Audio settings
CHUNK = 1024
FORMAT = pyaudio.paFloat32
CHANNELS = 1
RATE = 44100
MAX_RECONNECT_ATTEMPTS = 3
RECONNECT_DELAY = 2  # seconds

def create_ssl_context():
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    # Support TLS 1.2 and 1.3 but prefer 1.3
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.maximum_version = ssl.TLSVersion.TLSv1_3
    # Add more secure ciphers
    context.set_ciphers('ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305')
    return context

def connect_control(server_ip):
    """Establish control connection with SSL"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        context = create_ssl_context()
        secure_sock = context.wrap_socket(sock, server_hostname=server_ip)
        secure_sock.connect((server_ip, 5000))
        logger.info(f"🔒 Connected to control server with {secure_sock.version()}")
        return secure_sock
    except Exception as e:
        logger.error(f"Control connection error: {e}")
        return None

def handle_control_messages():
    """Handle incoming control messages"""
    while True:
        try:
            if not client_state['control_socket']:
                time.sleep(1)
                continue

            try:
                data = client_state['control_socket'].recv(1024).decode()
                if not data:
                    logger.info("Control connection closed by server")
                    break

                logger.info(f"📥 Received control message: {data}")

                if data.startswith("INCOMING|"):
                    caller = data.split('|')[1]
                    socketio.emit('incoming_call', {'caller': caller})

                elif data.startswith("ACCEPTED|"):
                    target = data.split('|')[1]
                    client_state['current_call'] = {'target': target, 'status': 'connected'}
                    socketio.emit('call_accepted', {'target': target})

                elif data.startswith("REJECTED|"):
                    target = data.split('|')[1]
                    client_state['current_call'] = None
                    socketio.emit('call_rejected', {'target': target})

                elif data.startswith("END|"):
                    ender = data.split('|')[1]
                    client_state['current_call'] = None
                    socketio.emit('call_ended', {'ender': ender})

                elif data.startswith("ERROR|"):
                    error = data.split('|')[1]
                    socketio.emit('error', {'message': error})

                elif data.startswith("USERS|"):
                    users = data.split('|')[1].split(',')
                    socketio.emit('user_list', {'users': users})

                elif data.startswith("SUCCESS|"):
                    logger.info(f"✅ {data}")

            except ssl.SSLError as e:
                logger.error(f"SSL Error in control handler: {e}")
                # Try to recover from SSL errors
                time.sleep(1)
                continue
            except Exception as e:
                logger.error(f"Error processing message: {e}")
                break

        except Exception as e:
            logger.error(f"Control message error: {e}")
            break

    # Connection lost
    logger.info("Control connection lost, cleaning up...")
    client_state['control_socket'] = None
    socketio.emit('disconnected')

def setup_media_sockets(server_ip):
    """Setup video and audio sockets with SSL"""
    try:
        # Create SSL context for media sockets
        context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        context.load_cert_chain('cert.pem', 'key.pem')
        
        # Setup video socket
        video_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        video_sock = context.wrap_socket(video_sock)
        video_sock.connect((server_ip, 6000))
        client_state['video_socket'] = video_sock
        
        # Setup audio socket
        audio_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        audio_sock = context.wrap_socket(audio_sock)
        audio_sock.connect((server_ip, 6001))
        client_state['audio_socket'] = audio_sock
        
        logger.info("Media sockets established successfully")
        return True
        
    except Exception as e:
        logger.error(f"Failed to setup media sockets: {e}")
        return False

def close_media_sockets():
    """Close video and audio sockets"""
    try:
        if client_state['video_socket']:
            client_state['video_socket'].close()
            client_state['video_socket'] = None
            
        if client_state['audio_socket']:
            client_state['audio_socket'].close()
            client_state['audio_socket'] = None
            
        logger.info("Media sockets closed")
        
    except Exception as e:
        logger.error(f"Error closing media sockets: {e}")

def register_with_server(username):
    """Register user with the server"""
    if not client_state['control_socket']:
        logger.error("No control connection available")
        return False
        
    try:
        register_msg = json.dumps({
            'type': 'register',
            'username': username
        })
        client_state['control_socket'].sendall(register_msg.encode() + b'\n')
        logger.info(f"Registration request sent for user: {username}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to register with server: {e}")
        return False

def make_call(target_user):
    """Initiate a call to target user"""
    if not client_state['control_socket']:
        logger.error("No control connection available")
        return False
        
    try:
        call_msg = json.dumps({
            'type': 'call',
            'target': target_user
        })
        client_state['control_socket'].sendall(call_msg.encode() + b'\n')
        logger.info(f"Call request sent to user: {target_user}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to initiate call: {e}")
        return False

def handle_call_response(accept, caller=None):
    """Handle accepting or rejecting an incoming call"""
    if not client_state['control_socket']:
        logger.error("No control connection available")
        return False
        
    try:
        response_msg = json.dumps({
            'type': 'call_response',
            'accept': accept,
            'caller': caller
        })
        client_state['control_socket'].sendall(response_msg.encode() + b'\n')
        
        if accept:
            logger.info(f"Call accepted from: {caller}")
        else:
            logger.info(f"Call rejected from: {caller}")
            
        return True
        
    except Exception as e:
        logger.error(f"Failed to send call response: {e}")
        return False

def end_call():
    """End the current call"""
    if not client_state['control_socket']:
        logger.error("No control connection available")
        return False
        
    try:
        end_msg = json.dumps({
            'type': 'end_call'
        })
        client_state['control_socket'].sendall(end_msg.encode() + b'\n')
        
        # Stop media streams and close sockets
        stop_media_stream()
        close_media_sockets()
        
        logger.info("Call ended")
        return True
        
    except Exception as e:
        logger.error(f"Failed to end call: {e}")
        return False

def setupLocalStream():
    """Initialize video and audio capture devices"""
    try:
        # Initialize video capture
        stream = cv2.VideoCapture(0)
        if not stream.isOpened():
            raise Exception("Could not open video device")
        
        # Set video properties
        stream.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        stream.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        stream.set(cv2.CAP_PROP_FPS, 30)
        
        # Initialize audio
        audio = pyaudio.PyAudio()
        audio_stream = audio.open(
            format=FORMAT,
            channels=CHANNELS,
            rate=RATE,
            input=True,
            frames_per_buffer=CHUNK
        )
        
        client_state['stream'] = stream
        client_state['audio_stream'] = audio_stream
        logger.info("Local media streams initialized successfully")
        return True
        
    except Exception as e:
        logger.error(f"Failed to setup local stream: {e}")
        socketio.emit('status', {'message': f'Failed to setup media devices: {str(e)}', 'type': 'error'})
        return False

def start_media_stream():
    """Start streaming video and audio"""
    if not client_state['stream'] or not client_state['audio_stream']:
        if not setupLocalStream():
            return False
    
    def video_stream_thread():
        while client_state['connected'] and client_state['stream']:
            try:
                ret, frame = client_state['stream'].read()
                if not ret:
                    logger.error("Failed to capture video frame")
                    continue
                
                # Compress and encode frame
                _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
                encoded_frame = base64.b64encode(buffer).decode('utf-8')
                
                # Send frame
                if client_state['video_socket']:
                    client_state['video_socket'].sendall(encoded_frame.encode() + b'\n')
                    
            except Exception as e:
                logger.error(f"Video streaming error: {e}")
                time.sleep(0.1)  # Prevent tight loop on error
    
    def audio_stream_thread():
        while client_state['connected'] and client_state['audio_stream']:
            try:
                data = client_state['audio_stream'].read(CHUNK, exception_on_overflow=False)
                if client_state['audio_socket']:
                    client_state['audio_socket'].sendall(data)
                    
            except Exception as e:
                logger.error(f"Audio streaming error: {e}")
                time.sleep(0.1)
    
    # Start streaming threads
    threading.Thread(target=video_stream_thread, daemon=True).start()
    threading.Thread(target=audio_stream_thread, daemon=True).start()
    logger.info("Media streaming started")
    return True

def stop_media_stream():
    """Stop all media streams and release resources"""
    try:
        if client_state['stream']:
            client_state['stream'].release()
            client_state['stream'] = None
            
        if client_state['audio_stream']:
            client_state['audio_stream'].stop_stream()
            client_state['audio_stream'].close()
            client_state['audio_stream'] = None
            
        logger.info("Media streams stopped and resources released")
        
    except Exception as e:
        logger.error(f"Error stopping media streams: {e}")

@app.route('/')
def index():
    return render_template('client.html')

@app.route('/connect', methods=['POST'])
def connect():
    data = request.json
    if not data or 'name' not in data or 'server_ip' not in data:
        return jsonify({"error": "Name and server IP required"}), 400

    client_state['name'] = data['name']
    client_state['server_ip'] = data['server_ip']

    # Setup sockets
    control_socket = connect_control(data['server_ip'])
    if not control_socket:
        return jsonify({"error": "Could not connect to server"}), 500

    client_state['control_socket'] = control_socket
    client_state['video_socket'] = setup_media_sockets(data['server_ip'])
    client_state['audio_socket'] = setup_media_sockets(data['server_ip'])

    # Register with server
    register_with_server(data['name'])

    # Start control message handler
    threading.Thread(target=handle_control_messages, daemon=True).start()

    return jsonify({"status": "connected"})

@app.route('/call', methods=['POST'])
def call():
    if not client_state['control_socket']:
        return jsonify({"error": "Not connected to server"}), 400

    data = request.json
    if not data or 'target' not in data:
        return jsonify({"error": "Target name required"}), 400

    make_call(data['target'])
    client_state['current_call'] = {'target': data['target'], 'status': 'calling'}
    return jsonify({"status": "calling"})

@app.route('/accept_call', methods=['POST'])
def accept_call():
    if not client_state['control_socket']:
        return jsonify({"error": "Not connected to server"}), 400

    data = request.json
    if not data or 'caller' not in data:
        return jsonify({"error": "Caller name required"}), 400

    handle_call_response(True, data['caller'])
    client_state['current_call'] = {'target': data['caller'], 'status': 'connected'}
    start_media_stream()
    return jsonify({"status": "accepted"})

@app.route('/reject_call', methods=['POST'])
def reject_call():
    if not client_state['control_socket']:
        return jsonify({"error": "Not connected to server"}), 400

    data = request.json
    if not data or 'caller' not in data:
        return jsonify({"error": "Caller name required"}), 400

    handle_call_response(False, data['caller'])
    return jsonify({"status": "rejected"})

@app.route('/end_call', methods=['POST'])
def end_call():
    if not client_state['control_socket'] or not client_state['current_call']:
        return jsonify({"error": "No active call"}), 400

    end_call()
    return jsonify({"status": "ended"})

@socketio.on('connect')
def handle_connect():
    logger.info('Client connected to Socket.IO server')
    if not client_state['connected']:
        client_state['connected'] = True
        socketio.emit('status', {'message': 'Connected to server', 'type': 'success'})

@socketio.on('disconnect')
def handle_disconnect():
    logger.info('Client disconnected from Socket.IO server')
    client_state['connected'] = False
    stop_media_stream()
    attempt_reconnection()

@socketio.on('error')
def handle_error(error):
    logger.error(f'Socket.IO error: {error}')
    socketio.emit('status', {'message': f'Connection error: {error}', 'type': 'error'})

def attempt_reconnection():
    """Attempt to reconnect to the server with exponential backoff"""
    if client_state['reconnecting']:
        return

    client_state['reconnecting'] = True
    attempts = 0
    
    while attempts < MAX_RECONNECT_ATTEMPTS and not client_state['connected']:
        try:
            logger.info(f'Attempting reconnection ({attempts + 1}/{MAX_RECONNECT_ATTEMPTS})')
            socketio.emit('status', {
                'message': f'Attempting reconnection ({attempts + 1}/{MAX_RECONNECT_ATTEMPTS})',
                'type': 'warning'
            })
            
            # Try to establish new control connection
            new_socket = connect_control(client_state['server_ip'])
            if new_socket:
                client_state['control_socket'] = new_socket
                client_state['connected'] = True
                socketio.emit('status', {'message': 'Reconnected successfully', 'type': 'success'})
                # Restart control message handler
                threading.Thread(target=handle_control_messages, daemon=True).start()
                break
                
        except Exception as e:
            logger.error(f'Reconnection attempt failed: {e}')
            
        attempts += 1
        time.sleep(RECONNECT_DELAY * (2 ** attempts))  # Exponential backoff
    
    if not client_state['connected']:
        socketio.emit('status', {
            'message': 'Failed to reconnect after multiple attempts',
            'type': 'error'
        })
    
    client_state['reconnecting'] = False

if __name__ == '__main__':
    try:
        # Try to find an available port starting from 31769 (one after server's default)
        port = 31769
        while port < 31789:  # Try 20 ports starting from 31769
            try:
                print(f"🎬 Starting client on port {port}...")
                # Create SSL context
                context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
                context.load_cert_chain('cert.pem', 'key.pem')
                
                socketio.run(
                    app,
                    host='0.0.0.0',
                    port=port,
                    **{'ssl_certfile': 'cert.pem', 'ssl_keyfile': 'key.pem'}
                )
                break
            except OSError as e:
                if e.errno == 10048:  # Port in use
                    print(f"Port {port} is in use, trying next port...")
                    port += 1
                else:
                    raise
        else:
            print("Could not find an available port in range 31769-31788")
            sys.exit(1)
    except Exception as e:
        print(f"Error starting client: {e}")
        sys.exit(1)