import socket
import selectors
import threading
from typing import Dict
from shared import protocols, ssl_utils

class ConnectionManager:
    def __init__(self, host: str, port: int, certfile: str, keyfile: str):
        self.host = host
        self.port = port
        self.certfile = certfile
        self.keyfile = keyfile
        self.selector = selectors.DefaultSelector()
        self.clients: Dict[str, socket.socket] = {}
        self.running = False
        
    def start(self):
        """Start the server and listen for connections"""
        self.running = True
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind((self.host, self.port))
        server_socket.listen(5)
        
        ssl_context = ssl_utils.create_ssl_context(self.certfile, self.keyfile, server_side=True)
        
        print(f"Server listening on {self.host}:{self.port}")
        
        try:
            while self.running:
                client_socket, addr = server_socket.accept()
                print(f"New connection from {addr}")
                
                try:
                    ssl_socket = ssl_utils.wrap_socket(client_socket, ssl_context, server_side=True)
                    client_thread = threading.Thread(
                        target=self.handle_client,
                        args=(ssl_socket, addr),
                        daemon=True
                    )
                    client_thread.start()
                except Exception as e:
                    print(f"Error establishing SSL connection: {e}")
                    client_socket.close()
        except KeyboardInterrupt:
            print("Shutting down server...")
        finally:
            server_socket.close()
    
    def handle_client(self, client_socket: socket.socket, addr: tuple):
        """Handle communication with a single client"""
        try:
            while self.running:
                # First read the header to get message length
                header = client_socket.recv(protocols.Protocol.HEADER_SIZE)
                if not header:
                    break
                
                msg_length = struct.unpack('!I', header)[0]
                data = client_socket.recv(msg_length)
                
                if not data:
                    break
                    
                message = protocols.Protocol.decode_message(data)
                self.process_message(message, client_socket, addr)
                
        except (ConnectionResetError, BrokenPipeError):
            print(f"Client {addr} disconnected abruptly")
        except Exception as e:
            print(f"Error with client {addr}: {e}")
        finally:
            client_socket.close()
            print(f"Connection closed with {addr}")
    
    def process_message(self, message: dict, client_socket: socket.socket, addr: tuple):
        """Process incoming messages from clients"""
        msg_type = message.get('type')
        print(f"Received message from {addr}: {message}")
        
        if msg_type == 'JOIN':
            username = message.get('username')
            self.clients[username] = client_socket
            response = protocols.Protocol.create_control_message('JOIN_ACK', status='success')
            client_socket.sendall(response)
            
        elif msg_type == 'LEAVE':
            username = message.get('username')
            if username in self.clients:
                del self.clients[username]
                
        elif msg_type == 'MEDIA':
            # Route media to other clients
            target = message.get('target', 'all')
            if target == 'all':
                for user, sock in self.clients.items():
                    if sock != client_socket:
                        try:
                            sock.sendall(protocols.Protocol.encode_message(message))
                        except:
                            print(f"Failed to send to {user}")