# server.py

from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit
import os
from utils.ssl_helper import get_local_ip

local_ip = get_local_ip()
app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins='*')

# Store connected clients
connected_clients = {}  # username -> sid

@app.route('/')
def index():
    return render_template('client.html')

@socketio.on('connect')
def handle_connect():
    print(f"🔌 Client connected: {request.sid}")

@socketio.on('register')
def handle_register(data):
    username = data.get('username')
    if username:
        connected_clients[username] = request.sid
        # Broadcast updated user list to all clients
        emit('user_list', list(connected_clients.keys()), broadcast=True)
        print(f"✅ User registered: {username}")

@socketio.on('disconnect')
def handle_disconnect():
    # Remove user from connected clients
    username = None
    for user, sid in connected_clients.items():
        if sid == request.sid:
            username = user
            break
    
    if username:
        del connected_clients[username]
        # Broadcast updated user list
        emit('user_list', list(connected_clients.keys()), broadcast=True)
        print(f"❌ User disconnected: {username}")

@socketio.on('call_user')
def handle_call_user(data):
    target = data.get('target')
    if target in connected_clients:
        caller = None
        for user, sid in connected_clients.items():
            if sid == request.sid:
                caller = user
                break
        
        if caller:
            # Forward the call request to target
            target_sid = connected_clients[target]
            emit('incoming_call', {
                'caller': caller,
                'offer': data.get('offer')  # Forward WebRTC offer
            }, room=target_sid)
            print(f"📞 Video call request: {caller} -> {target}")

@socketio.on('make_answer')
def handle_make_answer(data):
    target = data.get('target')
    if target in connected_clients:
        answerer = None
        for user, sid in connected_clients.items():
            if sid == request.sid:
                answerer = user
                break
        
        if answerer:
            # Forward the answer to the caller
            target_sid = connected_clients[target]
            emit('call_answered', {
                'answerer': answerer,
                'answer': data.get('answer')  # Forward WebRTC answer
            }, room=target_sid)
            print(f"📞 Call answered: {answerer} -> {target}")

@socketio.on('ice_candidate')
def handle_ice_candidate(data):
    target = data.get('target')
    if target in connected_clients:
        # Forward ICE candidate to the target peer
        target_sid = connected_clients[target]
        emit('ice_candidate', {
            'candidate': data.get('candidate')
        }, room=target_sid)

@socketio.on('end_call')
def handle_end_call(data):
    target = data.get('target')
    if target in connected_clients:
        sender = None
        for user, sid in connected_clients.items():
            if sid == request.sid:
                sender = user
                break
        
        if sender:
            target_sid = connected_clients[target]
            emit('call_ended', {'user': sender}, room=target_sid)
            print(f"📞 Call ended: {sender} -> {target}")

if __name__ == "__main__":
    print(f"🚀 Starting video chat server on http://{local_ip}:8080")
    socketio.run(app, host='0.0.0.0', port=8080, debug=True)