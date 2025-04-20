# from network_handler import NetworkHandler
import argparse
import threading
import time

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
        ssl_context = ssl_utils.create_ssl_context(self.certfile, '../ssl/key.pem', server_side=False)
        
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

class VideoCallClient:
    def __init__(self, server_host: str, server_port: int, certfile: str, username: str):
        self.network = NetworkHandler(server_host, server_port, certfile)
        self.username = username
        self.connected = False
        
    def start(self):
        """Connect to server and start communication"""
        if not self.network.connect():
            return
            
        self.connected = True
        self.network.start_receiving(self.handle_message)
        
        # Join the room
        join_msg = {
            'type': 'JOIN',
            'username': self.username,
            'room': 'default'
        }
        self.network.send_message(join_msg)
        
        # Start sending dummy media (replace with real video/audio)
        self.start_dummy_media()
        
        # Keep main thread alive
        try:
            while self.connected:
                time.sleep(1)
        except KeyboardInterrupt:
            print("Disconnecting...")
        finally:
            self.stop()
    
    def handle_message(self, message: dict):
        """Handle incoming messages from server"""
        msg_type = message.get('type')
        print(f"Received message: {message}")
        
        if msg_type == 'JOIN_ACK':
            print("Successfully joined the room")
        elif msg_type == 'MEDIA':
            # Handle incoming media (would be processed by video/audio handlers)
            pass
    
    def start_dummy_media(self):
        """Start sending dummy media for testing"""
        def send_dummy():
            while self.connected:
                media_msg = {
                    'type': 'MEDIA',
                    'from': self.username,
                    'data': 'dummy_frame_data',
                    'timestamp': time.time()
                }
                self.network.send_message(media_msg)
                time.sleep(0.1)
                
        media_thread = threading.Thread(target=send_dummy, daemon=True)
        media_thread.start()
    
    def stop(self):
        """Cleanup and disconnect"""
        if self.connected:
            leave_msg = {
                'type': 'LEAVE',
                'username': self.username
            }
            self.network.send_message(leave_msg)
            time.sleep(0.5)  # Give time for message to send
            
        self.connected = False
        self.network.disconnect()

def main():
    parser = argparse.ArgumentParser(description="Video Call Client")
    parser.add_argument('--host', default='localhost', help='Server host')
    parser.add_argument('--port', type=int, default=5000, help='Server port')
    parser.add_argument('--cert', default='../ssl/cert.pem', help='SSL certificate file')
    parser.add_argument('--username', required=True, help='Your username')
    
    args = parser.parse_args()
    
    client = VideoCallClient(
        server_host=args.host,
        server_port=args.port,
        certfile=args.cert,
        username=args.username
    )
    
    client.start()

if __name__ == "__main__":
    main()