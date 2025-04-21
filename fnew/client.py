# client.py

from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO
from video_channel import VideoChannel
from audio_channel import AudioChannel
from control_protocol import ControlProtocol
from utils.ssl_helper import generate_self_signed_cert

import threading
import webbrowser
import os
import cv2
import base64

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
    'target_user': '',
    'control_conn': None,
    'video_channel': VideoChannel(port=6002),
    'audio_channel': AudioChannel(port=6003),
    'active_call': False
}

@app.route('/')
def index():
    return render_template('client.html')

@app.route('/connect', methods=['POST'])
def connect():
    data = request.json
    client_state['name'] = data['name']
    client_state['server_ip'] = data['server_ip']
    
    try:
        control = ControlProtocol()
        client_state['control_conn'] = control.connect(client_state['server_ip'])

        # Start media receivers
        client_state['video_channel'].start_receiver(process_video_frame)
        client_state['audio_channel'].start_receiver(process_audio_frame)

        return jsonify({'status': 'connected'})
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/call', methods=['POST'])
def call():
    if not client_state['control_conn']:
        return jsonify({'error': 'Not connected'}), 400
    
    target = request.json['target']
    client_state['target_user'] = target
    client_state['control_conn'].send_signal('CALL', target)
    client_state['active_call'] = True
    return jsonify({'status': 'calling'})

@app.route('/end_call', methods=['POST'])
def end_call():
    if client_state['control_conn']:
        client_state['control_conn'].send_signal('END', client_state['name'])
        client_state['active_call'] = False
    return jsonify({'status': 'call_ended'})

def process_video_frame(frame):
    if client_state['active_call']:
        client_state['video_channel'].send_frame(frame, client_state['server_ip'])

    _, buffer = cv2.imencode('.jpg', frame)
    frame_base64 = base64.b64encode(buffer).decode('utf-8')
    socketio.emit('video_frame', {'frame': frame_base64})

def process_audio_frame(frame):
    if client_state['active_call']:
        # Placeholder: You can use pyaudio here to play received audio
        pass

@socketio.on('test')
def handle_test(data):
    print(f"🧪 Test message from frontend: {data}")
    socketio.emit('response', {'message': 'Client backend active'})

if __name__ == '__main__':
    def launch_browser():
        import time
        time.sleep(1)
        webbrowser.open_new('https://localhost:8080')

    threading.Thread(target=launch_browser).start()

    print("🎬 Client Flask-SocketIO app running...")
    socketio.run(app, host='0.0.0.0', port=8080, ssl_context=('cert.pem', 'key.pem'))


# from flask import Flask, render_template, request, jsonify
# from control_protocol import ControlProtocol
# from video_channel import VideoChannel
# from audio_channel import AudioChannel
# import threading
# import cv2
# import numpy as np
# import base64

# from flask import Flask, render_template, request, jsonify
# import threading
# import webbrowser
# import os
# import socket
# from video_channel import VideoChannel
# from audio_channel import AudioChannel
# from control_protocol import ControlProtocol
# from flask_socketio import SocketIO

# socketio = SocketIO(app)

# app = Flask(__name__)

# # Global state
# client_state = {
#     'name': '',
#     'server_ip': '127.0.0.1',
#     'target_user': '',
#     'control_conn': None,
#     'video_channel': VideoChannel(port=6002),  # Explicit port
#     'audio_channel': AudioChannel(port=6003),
#     'active_call': False  # Added this flag
# }

# def run_flask():
#     app.run(host='0.0.0.0', port=8080, ssl_context=('cert.pem', 'key.pem'), debug=False)

# @app.route('/')
# def index():
#     return render_template('client.html')

# @app.route('/connect', methods=['POST'])
# def connect():
#     data = request.json
#     client_state['name'] = data['name']
#     client_state['server_ip'] = data['server_ip']
    
#     try:
#         # Establish control channel connection
#         control = ControlProtocol()
#         client_state['control_conn'] = control.connect(client_state['server_ip'])
        
#         # Start media receivers
#         client_state['video_channel'].start_receiver(process_video_frame)
#         client_state['audio_channel'].start_receiver(process_audio_frame)
        
#         return jsonify({'status': 'connected'})
#     except Exception as e:
#         return jsonify({'error': str(e)}), 400

# @app.route('/call', methods=['POST'])
# def call():
#     if not client_state['control_conn']:
#         return jsonify({'error': 'Not connected'}), 400
    
#     target = request.json['target']
#     client_state['control_conn'].send_signal('CALL', target)
#     client_state['active_call'] = True
#     return jsonify({'status': 'calling'})

# @app.route('/end_call', methods=['POST'])
# def end_call():
#     if client_state['control_conn']:
#         client_state['control_conn'].send_signal('END', client_state['name'])
#         client_state['active_call'] = False
#     return jsonify({'status': 'call_ended'})

# def process_video_frame(frame):
#     """Send video frames to all connected peers"""
#     if client_state['active_call']:
#         # For demo: Send to server (in real app, use peer IP)
#         client_state['video_channel'].send_frame(frame, client_state['server_ip'])
    
#     # Convert frame for web display
#     _, buffer = cv2.imencode('.jpg', frame)
#     frame_base64 = base64.b64encode(buffer).decode('utf-8')
#     socketio.emit('video_frame', {'frame': frame_base64})

# def process_audio_frame(frame):
#     """Handle incoming audio frames"""
#     if client_state['active_call']:
#         # Process audio (play or forward)
#         pass

# if __name__ == '__main__':
#     # Start Flask in a separate thread
#     flask_thread = threading.Thread(target=run_flask)
#     flask_thread.daemon = True
#     flask_thread.start()

#     # Auto-launch browser after 1 second
#     def launch_browser():
#         import time
#         time.sleep(1)
#         webbrowser.open_new('https://localhost:8080')
    
#     threading.Thread(target=launch_browser).start()

#     # Start video capture (keep your existing code)
#     # Replace the video_capture function with this:
#     def video_capture():
#         cap = cv2.VideoCapture(0)
#         try:
#             while True:
#                 ret, frame = cap.read()
#                 if ret and client_state.get('active_call', False):
#                     # Use send_frame instead of process_frame
#                     client_state['video_channel'].send_frame(
#                         frame, 
#                         client_state['server_ip']
#                     )
#                 # Small delay to prevent 100% CPU usage
#                 cv2.waitKey(1)
#         finally:
#             cap.release()
    
#     threading.Thread(target=video_capture, daemon=True).start()