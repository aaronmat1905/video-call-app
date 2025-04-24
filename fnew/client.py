# client.py

import eventlet
eventlet.monkey_patch()  # Must be called before any other imports

import os
import ssl
from flask import Flask, render_template, request, jsonify, session
from flask_socketio import SocketIO, emit, disconnect
import threading
import webbrowser
import cv2
import base64
from utils.ssl_helper import get_local_ip, generate_self_signed_cert

# Initialize Flask and get local IP
app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)  # Generate a random secret key
socketio = SocketIO(app, 
                   cors_allowed_origins='*', 
                   logger=True, 
                   engineio_logger=True,
                   ping_timeout=60,
                   ping_interval=25)

# Store connected users and their sessions
connected_users = {}  # {username: sid}
user_sessions = {}   # {sid: username}
active_calls = {}    # {caller_sid: callee_sid}

with app.app_context():
    local_ip = get_local_ip()

    # Generate SSL certificates if they don't exist
    if not os.path.exists('cert.pem') or not os.path.exists('key.pem'):
        print("🔒 Generating SSL certificates...")
        generate_self_signed_cert()

    # Global client state
    client_state = {
        'name': '',
        'server_ip': local_ip,
        'target_user': '',
        'control_conn': None,
        'video_channel': None,
        'audio_channel': None,
        'active_call': False
    }

    # Now import and initialize components that might need app context
    from video_channel import VideoChannel
    from audio_channel import AudioChannel
    from control_protocol import ControlProtocol

    client_state['video_channel'] = VideoChannel(port=6002)
    client_state['audio_channel'] = AudioChannel(port=6003)

@socketio.on('connect')
def handle_connect():
    print(f"🔌 Client connected: {request.sid}")

@socketio.on('disconnect')
def handle_disconnect():
    sid = request.sid
    username = user_sessions.get(sid)
    if username:
        # End any active calls
        if sid in active_calls:
            other_sid = active_calls[sid]
            emit('call_ended', room=other_sid)
            del active_calls[sid]
            if other_sid in active_calls:
                del active_calls[other_sid]
        
        # Clean up user data
        del connected_users[username]
        del user_sessions[sid]
        print(f"👋 User disconnected: {username}")
        # Notify all clients about updated user list
        emit('user_list', list(connected_users.keys()), broadcast=True)

@socketio.on('register')
def handle_register(data):
    username = data.get('username')
    if username:
        # Store user data
        connected_users[username] = request.sid
        user_sessions[request.sid] = username
        print(f"✨ User registered: {username}")
        # Send updated user list to all clients
        emit('user_list', list(connected_users.keys()), broadcast=True)

@socketio.on('call_user')
def handle_call_user(data):
    target = data.get('target')
    target_sid = connected_users.get(target)
    caller = user_sessions.get(request.sid)
    
    if target_sid and caller:
        # Check if target user is already in a call
        if target_sid in active_calls:
            emit('call_rejected', {'message': 'User is busy'}, room=request.sid)
            return
        
        print(f"📞 Call from {caller} to {target}")
        emit('incoming_call', {
            'caller': caller,
            'offer': data.get('offer')
        }, room=target_sid)

@socketio.on('make_answer')
def handle_make_answer(data):
    target = data.get('target')
    target_sid = connected_users.get(target)
    if target_sid:
        # Record the active call
        active_calls[request.sid] = target_sid
        active_calls[target_sid] = request.sid
        
        emit('call_answered', {
            'answer': data.get('answer')
        }, room=target_sid)

@socketio.on('ice_candidate')
def handle_ice_candidate(data):
    target = data.get('target')
    target_sid = connected_users.get(target)
    if target_sid:
        emit('ice_candidate', {
            'candidate': data.get('candidate')
        }, room=target_sid)

@socketio.on('call_rejected')
def handle_call_rejected(data):
    target = data.get('target')
    target_sid = connected_users.get(target)
    if target_sid:
        emit('call_rejected', room=target_sid)

@socketio.on('end_call')
def handle_end_call(data):
    target = data.get('target')
    target_sid = connected_users.get(target)
    
    if target_sid:
        # Clean up active calls
        if request.sid in active_calls:
            del active_calls[request.sid]
        if target_sid in active_calls:
            del active_calls[target_sid]
            
        emit('call_ended', room=target_sid)

@app.route('/')
def index():
    return render_template('client.html')

@app.route('/users')
def get_users():
    return jsonify(list(connected_users.keys()))

@app.route('/connect', methods=['POST'])
def connect():
    data = request.json
    client_state['name'] = data['name']
    client_state['server_ip'] = data['server_ip']
    
    try:
        control = ControlProtocol()
        client_state['control_conn'] = control.connect(client_state['server_ip'])
        client_state['control_conn'].register(client_state['name'])

        # Start listening for incoming signals
        def handle_signal(signal, payload):
            print(f"📩 Received: {signal} | {payload}")

            if signal == "CALL":
                print(f"📞 Incoming call from {payload}")
                client_state['target_user'] = payload
                client_state['active_call'] = True
                client_state['control_conn'].send_signal("ANSWER", payload)

            elif signal == "ANSWER":
                print(f"✅ {payload} accepted the call!")

            elif signal == "END":
                print("🔚 Call ended.")
                client_state['active_call'] = False

        client_state['control_conn'].listen_for_signals(handle_signal)

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
        # Use HTTPS with the local IP address
        webbrowser.open_new(f'https://{local_ip}:8081')

    threading.Thread(target=launch_browser).start()

    print("🎬 Client Flask-SocketIO app running...")
    
    # Create SSL context
    ssl_context = (
        'cert.pem',  # certificate path
        'key.pem'    # private key path
    )
    
    # Enable debug mode for more detailed error messages
    app.debug = True
    
    # Run with eventlet and SSL
    socketio.run(
        app,
        host='0.0.0.0',
        port=8081,
        certfile='cert.pem',
        keyfile='key.pem',
        debug=True,
        use_reloader=False  # Disable reloader in debug mode
    )


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