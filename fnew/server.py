# server.py

from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO
import socket
import ssl
import threading
import os
from utils.ssl_helper import generate_self_signed_cert

# 🔐 Generate certs if missing
if not (os.path.exists('cert.pem') and os.path.exists('key.pem')):
    print("🔐 Generating self-signed certificates...")
    generate_self_signed_cert()

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins='*')

# SSL Context Setup
def create_ssl_context():
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain('cert.pem', 'key.pem')
    return context

# Control Channel (TCP 5000)
def control_server():
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        secure_sock = create_ssl_context().wrap_socket(sock, server_side=True)
        secure_sock.bind(('0.0.0.0', 5000))
        secure_sock.listen(5)
        print("🛠️ Control server running on port 5000...")

        while True:
            conn, addr = secure_sock.accept()
            threading.Thread(target=handle_control, args=(conn, addr)).start()
    except Exception as e:
        print(f"[Control Server] Error: {e}")

def handle_control(conn, addr):
    try:
        data = conn.recv(1024).decode()
        if data.startswith("CALL|"):
            print(f"📞 Call request received: {data}")
            # Implement call routing logic
    finally:
        conn.close()

# Video Channel (UDP 6000)
def video_server():
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(('0.0.0.0', 6000))
        print("🎥 Video server listening on port 6000...")
    except OSError as e:
        print(f"[Video Server] Port bind failed: {e}")
        return

    while True:
        data, addr = sock.recvfrom(65536)
        # Process video frames
        print(f"📦 Video packet received from {addr}")

@app.route('/')
def index():
    return render_template('client.html')

@app.route('/connect', methods=['POST'])
def connect():
    return jsonify({"status": "connected"})

@socketio.on('test')
def handle_test(data):
    print(f"🧪 Test received: {data}")
    socketio.emit('response', {'message': 'Hello from secure server!'})

if __name__ == "__main__":
    threading.Thread(target=control_server, daemon=True).start()
    threading.Thread(target=video_server, daemon=True).start()

    print("🚀 Starting Flask-SocketIO server...")
    socketio.run(app, host='0.0.0.0', port=8080, ssl_context=('cert.pem', 'key.pem'))


# from flask import Flask, render_template, request, jsonify
# import socket
# import ssl
# import threading
# from cryptography import x509
# from cryptography.hazmat.backends import default_backend
# from flask_socketio import SocketIO

# from flask import Flask, render_template, request, jsonify
# from flask_socketio import SocketIO  # ✅ Add this
# from video_channel import VideoChannel
# from audio_channel import AudioChannel
# from control_protocol import ControlProtocol
# import threading
# import webbrowser
# import os
# import cv2
# import numpy as np
# import base64


# app = Flask(__name__)
# socketio = SocketIO(app, cors_allowed_origins='*')

# # SSL Context Setup
# def create_ssl_context():
#     context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
#     context.load_cert_chain('cert.pem', 'key.pem')
#     return context

# # Control Channel (TCP 5000)
# def control_server():
#     sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
#     sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
#     secure_sock = create_ssl_context().wrap_socket(sock, server_side=True)
#     secure_sock.bind(('0.0.0.0', 5000))
#     secure_sock.listen(5)
    
#     while True:
#         conn, addr = secure_sock.accept()
#         threading.Thread(target=handle_control, args=(conn, addr)).start()

# def handle_control(conn, addr):
#     try:
#         data = conn.recv(1024).decode()
#         if data.startswith("CALL|"):
#             # Implement call routing logic
#             pass
#     finally:
#         conn.close()

# # Video Channel (UDP 6000)
# def video_server():
#     sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
#     sock.bind(('0.0.0.0', 6000))
    
#     while True:
#         data, addr = sock.recvfrom(65536)
#         # Process video frames

# @app.route('/')
# def index():
#     return render_template('client.html')

# @app.route('/connect', methods=['POST'])
# def connect():
#     # Implement connection logic
#     return jsonify({"status": "connected"})

# if __name__ == "__main__":
#     threading.Thread(target=control_server, daemon=True).start()
#     threading.Thread(target=video_server, daemon=True).start()
#     socketio.run(app, host='0.0.0.0', port=8080, ssl_context=('cert.pem', 'key.pem'))