import socket
import ssl
import threading

class ControlProtocol:
    def __init__(self):
        self.context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        self.context.check_hostname = False
        self.context.verify_mode = ssl.CERT_NONE
        self.secure_sock = None  # Initialize here to be safe

    def connect(self, server_ip, port=5000):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.secure_sock = self.context.wrap_socket(sock)
        self.secure_sock.connect((server_ip, port))
        return self  # ✅ Return self instead of the socket

    def send_signal(self, signal_type, payload):
        message = f"{signal_type}|{payload}"
        self.secure_sock.sendall(message.encode())

    def receive_signal(self):
        return self.secure_sock.recv(1024).decode()
    
    def register(self, name):
        self.send_signal('REGISTER', name)

    def listen_for_signals(self, on_signal):
        def loop():
            while True:
                try:
                    msg = self.receive_signal()
                    if msg:
                        parts = msg.split('|', 1)
                        if len(parts) == 2:
                            on_signal(parts[0], parts[1])
                except Exception as e:
                    print(f"❌ Signal listener error: {e}")
                    break
        threading.Thread(target=loop, daemon=True).start()