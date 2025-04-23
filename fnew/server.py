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

# Global state
connected_clients = {}  # name → conn
active_calls = {}  # caller → callee

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
    client_name = None
    try:
        while True:
            data = conn.recv(1024).decode()
            if not data:
                break

            print(f"[Control] From {addr}: {data}")

            if data.startswith("REGISTER|"):
                name = data.split('|')[1]
                if name in connected_clients:
                    conn.send("ERROR|Name already taken".encode())
                else:
                    client_name = name
                    connected_clients[name] = conn
                    print(f"✅ Registered client: {name}")
                    conn.send("SUCCESS|Registered".encode())
                    # Notify all clients about the new user
                    broadcast_user_list()

            elif data.startswith("CALL|"):
                caller = get_name_from_conn(conn)
                target = data.split('|')[1]

                if not caller:
                    conn.send("ERROR|Not registered".encode())
                    continue

                print(f"📞 {caller} wants to call {target}")

                if target in connected_clients:
                    if target in active_calls.values() or caller in active_calls:
                        conn.send(f"ERROR|User is busy".encode())
                    else:
                        target_conn = connected_clients[target]
                        target_conn.send(f"INCOMING|{caller}".encode())
                        active_calls[caller] = target
                        print(f"📤 Forwarded call request to {target}")
                else:
                    conn.send(f"ERROR|User {target} not found".encode())

            elif data.startswith("ACCEPT|"):
                caller = data.split('|')[1]
                accepter = get_name_from_conn(conn)
                
                if caller in active_calls and active_calls[caller] == accepter:
                    connected_clients[caller].send(f"ACCEPTED|{accepter}".encode())
                    print(f"✅ {accepter} accepted call from {caller}")
                else:
                    conn.send("ERROR|Invalid call acceptance".encode())

            elif data.startswith("REJECT|"):
                caller = data.split('|')[1]
                rejecter = get_name_from_conn(conn)
                
                if caller in active_calls and active_calls[caller] == rejecter:
                    connected_clients[caller].send(f"REJECTED|{rejecter}".encode())
                    del active_calls[caller]
                    print(f"❌ {rejecter} rejected call from {caller}")

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
        print(f"❌ Error in control handler: {e}")
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

# Video Channel (UDP 6000)
def video_server():
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(('0.0.0.0', 6000))
        print("🎥 Video server listening on port 6000...")

        while True:
            data, addr = sock.recvfrom(65536)
            # Forward video data to the appropriate recipient
            try:
                sender_addr = addr[0]
                sender = None
                recipient = None

                # Find sender and recipient
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
                print(f"Error forwarding video: {e}")

    except Exception as e:
        print(f"[Video Server] Error: {e}")

@app.route('/')
def index():
    return render_template('client.html')

@app.route('/connect', methods=['POST'])
def connect():
    data = request.json
    if not data or 'name' not in data:
        return jsonify({"error": "Name is required"}), 400
    
    name = data['name']
    if name in connected_clients:
        return jsonify({"error": "Name already taken"}), 400

    return jsonify({"status": "connected", "message": f"Welcome {name}!"})

@socketio.on('test')
def handle_test(data):
    print(f"🧪 Test received: {data}")
    socketio.emit('response', {'message': 'Hello from secure server!'})

if __name__ == "__main__":
    threading.Thread(target=control_server, daemon=True).start()
    threading.Thread(target=video_server, daemon=True).start()

    print("🚀 Starting Flask-SocketIO server...")
    socketio.run(app, host='0.0.0.0', port=8080, ssl_context=('cert.pem', 'key.pem'))