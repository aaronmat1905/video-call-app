import socket
import ssl

class ControlProtocol:
    def __init__(self):
        self.context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        self.context.check_hostname = False
        self.context.verify_mode = ssl.CERT_NONE
    
    def connect(self, server_ip, port=5000):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.secure_sock = self.context.wrap_socket(sock)
        self.secure_sock.connect((server_ip, port))
        return self.secure_sock
    
    def send_signal(self, signal_type, payload):
        message = f"{signal_type}|{payload}"
        self.secure_sock.sendall(message.encode())
    
    def receive_signal(self):
        return self.secure_sock.recv(1024).decode()