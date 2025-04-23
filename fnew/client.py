# client.py

from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO

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

# 🔐 Generate certs if missing
if not (os.path.exists('cert.pem') and os.path.exists('key.pem')):
    print("🔐 Generating self-signed certificates...")
    generate_self_signed_cert()

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins='*')

# Global client state
client_state = {
    'name': '',
    'server_ip': '127.0.0.1',
    'control_socket': None,
    'video_socket': None,
    'audio_socket': None,
    'current_call': None,
    'stream': None,
    'audio_stream': None
}

# Audio settings
CHUNK = 1024
FORMAT = pyaudio.paFloat32
CHANNELS = 1
RATE = 44100

def create_ssl_context():
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.load_verify_locations('cert.pem')
    return context

def connect_control(server_ip):
    """Establish control connection with SSL"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        secure_sock = create_ssl_context().wrap_socket(sock, server_hostname=server_ip)
        secure_sock.connect((server_ip, 5000))
        return secure_sock
    except Exception as e:
        print(f"Control connection error: {e}")
        return None

def handle_control_messages():
    """Handle incoming control messages"""
    while True:
        try:
            if not client_state['control_socket']:
                time.sleep(1)
                continue

            data = client_state['control_socket'].recv(1024).decode()
            if not data:
                break

            print(f"📥 Received control message: {data}")

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

        except Exception as e:
            print(f"Control message error: {e}")
            break

    # Connection lost
    client_state['control_socket'] = None
    socketio.emit('disconnected')

def setup_video_socket():
    """Setup UDP socket for video transmission"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(('0.0.0.0', 0))  # Let OS choose port
        return sock
    except Exception as e:
        print(f"Video socket error: {e}")
        return None

def setup_audio_socket():
    """Setup UDP socket for audio transmission"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(('0.0.0.0', 0))  # Let OS choose port
        return sock
    except Exception as e:
        print(f"Audio socket error: {e}")
        return None

def start_media_stream():
    """Start capturing and sending media"""
    if client_state['stream']:
        return

    try:
        # Initialize video capture
        cap = cv2.VideoCapture(0)
        client_state['stream'] = cap

        # Initialize audio
        audio = pyaudio.PyAudio()
        stream = audio.open(format=FORMAT,
                          channels=CHANNELS,
                          rate=RATE,
                          input=True,
                          frames_per_buffer=CHUNK)
        client_state['audio_stream'] = stream

        def send_media():
            while client_state['stream'] and client_state['current_call']:
                try:
                    # Send video
                    ret, frame = cap.read()
                    if ret:
                        # Compress frame
                        _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 60])
                        data = buffer.tobytes()
                        if client_state['video_socket']:
                            client_state['video_socket'].sendto(data, 
                                (client_state['server_ip'], 6000))

                    # Send audio
                    audio_data = stream.read(CHUNK, exception_on_overflow=False)
                    if client_state['audio_socket']:
                        client_state['audio_socket'].sendto(audio_data,
                            (client_state['server_ip'], 6001))

                    time.sleep(1/30)  # Limit to ~30fps

                except Exception as e:
                    print(f"Media streaming error: {e}")
                    break

        threading.Thread(target=send_media, daemon=True).start()

    except Exception as e:
        print(f"Media setup error: {e}")
        stop_media_stream()

def stop_media_stream():
    """Stop media streaming"""
    if client_state['stream']:
        client_state['stream'].release()
        client_state['stream'] = None

    if client_state['audio_stream']:
        client_state['audio_stream'].stop_stream()
        client_state['audio_stream'].close()
        client_state['audio_stream'] = None

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
    client_state['video_socket'] = setup_video_socket()
    client_state['audio_socket'] = setup_audio_socket()

    # Register with server
    control_socket.send(f"REGISTER|{data['name']}".encode())

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

    client_state['control_socket'].send(f"CALL|{data['target']}".encode())
    client_state['current_call'] = {'target': data['target'], 'status': 'calling'}
    return jsonify({"status": "calling"})

@app.route('/accept_call', methods=['POST'])
def accept_call():
    if not client_state['control_socket']:
        return jsonify({"error": "Not connected to server"}), 400

    data = request.json
    if not data or 'caller' not in data:
        return jsonify({"error": "Caller name required"}), 400

    client_state['control_socket'].send(f"ACCEPT|{data['caller']}".encode())
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

    client_state['control_socket'].send(f"REJECT|{data['caller']}".encode())
    return jsonify({"status": "rejected"})

@app.route('/end_call', methods=['POST'])
def end_call():
    if not client_state['control_socket'] or not client_state['current_call']:
        return jsonify({"error": "No active call"}), 400

    client_state['control_socket'].send(f"END|{client_state['current_call']['target']}".encode())
    stop_media_stream()
    client_state['current_call'] = None
    return jsonify({"status": "ended"})

if __name__ == '__main__':
    print("🎬 Starting client...")
    socketio.run(app, host='0.0.0.0', port=8080, ssl_context=('cert.pem', 'key.pem'))