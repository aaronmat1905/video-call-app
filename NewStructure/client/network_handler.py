import socket
import selectors
import threading
from typing import Optional, Callable
from shared import protocols, ssl_utils

class NetworkHandler:
    def __init__(self, host: str, port: int, certfile: str):
        self.host = host
        self.port = port
        self.certfile = certfile
        self.socket: Optional[socket.socket] = None
        self.ssl_socket: Optional[ssl.SSLSocket] = None
        self.running = False
        self.message_callback: Optional[Callable] = None
        
    def connect(self):
        """Establish connection to server"""
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        ssl_context = ssl_utils.create_ssl_context(self.certfile, None, server_side=False)
        
        try:
            self.socket.connect((self.host, self.port))
            self.ssl_socket = ssl_utils.wrap_socket(self.socket, ssl_context)
            self.running = True
            return True
        except Exception as e:
            print(f"Connection failed: {e}")
            return False
    
    def start_receiving(self, callback: Callable):
        """Start thread to receive messages"""
        self.message_callback = callback
        receive_thread = threading.Thread(target=self._receive_loop, daemon=True)
        receive_thread.start()
    
    def _receive_loop(self):
        """Continuously receive messages from server"""
        try:
            while self.running and self.ssl_socket:
                # Read header first
                header = self.ssl_socket.recv(protocols.Protocol.HEADER_SIZE)
                if not header:
                    break
                
                msg_length = struct.unpack('!I', header)[0]
                data = self.ssl_socket.recv(msg_length)
                
                if not data:
                    break
                    
                message = protocols.Protocol.decode_message(data)
                if self.message_callback:
                    self.message_callback(message)
                    
        except (ConnectionResetError, BrokenPipeError):
            print("Disconnected from server")
        except Exception as e:
            print(f"Error receiving data: {e}")
        finally:
            self.disconnect()
    
    def send_message(self, message: dict):
        """Send a message to the server"""
        if self.ssl_socket and self.running:
            try:
                self.ssl_socket.sendall(protocols.Protocol.encode_message(message))
            except Exception as e:
                print(f"Failed to send message: {e}")
                self.disconnect()
    
    def disconnect(self):
        """Close the connection"""
        self.running = False
        if self.ssl_socket:
            try:
                self.ssl_socket.close()
            except:
                pass
        if self.socket:
            try:
                self.socket.close()
            except:
                pass