from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit
from common import get_local_ip, create_ssl_context
from video_stream import send_video, receive_video
import socket, threading

app = Flask(__name__)
socketio = SocketIO(app)

# Global state (minimal version)
client_socket = None
client_name = None
server_ip = None

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/connect", methods=["POST"])
def connect_to_server():
    global client_socket, client_name, server_ip
    data = request.json
    client_name = data["name"]
    server_ip = data["server_ip"]

    context = create_ssl_context()
    client_socket = context.wrap_socket(socket.socket(socket.AF_INET))
    client_socket.connect((server_ip, 5000))
    client_socket.send(client_name.encode())

    # Start listening thread
    threading.Thread(target=listen_to_server, daemon=True).start()
    return jsonify({"status": "connected"})

@app.route("/call", methods=["POST"])
def call_user():
    target = request.json["target"]
    if client_socket:
        client_socket.send(f"CALL|{target}".encode())
        return jsonify({"status": "calling"})
    return jsonify({"error": "Not connected"}), 400

@app.route("/receive", methods=["POST"])
def receive_video_route():
    threading.Thread(target=receive_video, daemon=True).start()
    return jsonify({"status": "receiving"})

@app.route("/quit", methods=["POST"])
def quit_app():
    if client_socket:
        client_socket.send(f"END|{client_name}".encode())
        client_socket.close()
    return jsonify({"status": "quit"})

def listen_to_server():
    while True:
        try:
            data = client_socket.recv(4096).decode()
            print("[SERVER]", data)
            if data.startswith("INCOMING|"):
                caller = data.split("|")[1]
                print(f"Incoming call from {caller}")
                # Automatically accept for now
                client_socket.send(f"ACCEPT|{caller}".encode())
                send_video(server_ip)
            elif data.startswith("ACCEPTED|"):
                send_video(server_ip)
            elif data.startswith("USERLIST|"):
                userlist = data.split("|")[1:]
                socketio.emit("userlist", {"users": userlist})
        except:
            break

if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=8080)