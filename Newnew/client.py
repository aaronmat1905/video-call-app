from flask import Flask, render_template_string, request, jsonify
from video_stream import send_video, receive_video
from common import create_ssl_context
import cryptography
from flask_socketio import SocketIO
import socket, threading, ssl

from flask import Flask, render_template_string, request, jsonify
from flask_socketio import SocketIO
import socket
import ssl
import threading
import logging

# Disable verbose logging
logging.basicConfig(level=logging.ERROR)

app = Flask(__name__)
socketio = SocketIO(app)

# Global state
client_socket = None
client_name = None
server_ip = None

HTML = """
<!DOCTYPE html>
<html>
<head>
  <title>Video Call</title>
  <style>
    body { font-family: Arial; margin: 20px; }
    video { width: 300px; background: #000; margin: 10px; }
    button { padding: 10px; margin: 5px; }
  </style>
</head>
<body>
  <div>
    <input id="name" placeholder="Your Name">
    <input id="server_ip" placeholder="Server IP" value="127.0.0.1">
    <button onclick="connect()">Connect</button>
    <input id="target" placeholder="Target Username">
    <button onclick="call()">Call</button>
    <button onclick="quit()">Quit</button>
  </div>
  
  <div>
    <video id="localVideo" autoplay muted playsinline></video>
    <video id="remoteVideo" autoplay playsinline></video>
  </div>

  <script>
    let localStream;
    
    async function setupCamera() {
    try {
        // Try real camera first
        if (navigator.mediaDevices?.getUserMedia) {
            const stream = await navigator.mediaDevices.getUserMedia({ video: true });
            document.getElementById('localVideo').srcObject = stream;
        } else {
            // Fallback to test video if camera blocked
            document.getElementById('localVideo').src = "https://sample-videos.com/video123/mp4/720/big_buck_bunny_720p_1mb.mp4";
            console.log("Using test video (camera blocked)");
        }
    } catch (err) {
        alert("Camera access failed. Using test video instead.");
        document.getElementById('localVideo').src = "https://sample-videos.com/video123/mp4/720/big_buck_bunny_720p_1mb.mp4";
    }
}

    function connect() {
      setupCamera();
      fetch("/connect", {
        method: "POST",
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          name: document.getElementById("name").value,
          server_ip: document.getElementById("server_ip").value
        })
      });
    }

    function call() {
      fetch("/call", {
        method: "POST",
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ 
          target: document.getElementById("target").value 
        })
      });
    }

    function quit() {
      if (localStream) {
        localStream.getTracks().forEach(track => track.stop());
      }
      fetch("/quit", { method: "POST" });
    }
  </script>
</body>
</html>
"""

@app.route("/")
def index():
    return render_template_string(HTML)

@app.route("/connect", methods=["POST"])
def connect_to_server():
    global client_socket, client_name, server_ip
    data = request.json
    client_name = data["name"]
    server_ip = data["server_ip"]

    try:
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        client_socket = context.wrap_socket(
            socket.socket(socket.AF_INET),
            server_hostname=server_ip
        )
        client_socket.connect((server_ip, 5000))
        client_socket.send(client_name.encode())
        threading.Thread(target=listen_to_server, daemon=True).start()
        return jsonify({"status": "connected"})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route("/call", methods=["POST"])
def call_user():
    if not client_socket:
        return jsonify({"error": "Not connected"}), 400
    client_socket.send(f"CALL|{request.json['target']}".encode())
    return jsonify({"status": "calling"})

@app.route("/quit", methods=["POST"])
def quit_app():
    if client_socket:
        client_socket.close()
    return jsonify({"status": "quit"})

def listen_to_server():
    while True:
        try:
            data = client_socket.recv(1024).decode()
            if not data:
                break
            print(f"[SERVER] {data}")
        except:
            break

if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=8080, debug=True)