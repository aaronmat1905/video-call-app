I'd be happy to help you code this video call application from scratch! Let's start with a clean implementation that meets all your requirements. I'll provide a structured approach with code samples for each component.

## Project Structure

Let's begin with the basic structure you outlined and build up the components:

```
video-call-app/
│
├── client/
│   ├── main.py
│   ├── video_handler.py
│   ├── audio_handler.py
│   ├── network_handler.py
│
├── server/
│   ├── main.py
│   ├── connection_manager.py
│   ├── room_manager.py
│
├── shared/
│   ├── protocols.py
│   ├── ssl_utils.py
│
├── ssl/
│   ├── cert.pem
│   ├── key.pem
│
├── requirements.txt
└── README.md
```

## 1. Let's start with the shared protocols and SSL utilities

`shared/protocols.py`:
```python
import json
import struct

class Protocol:
    HEADER_SIZE = 4  # 4 bytes for message length
    
    @staticmethod
    def encode_message(message: dict) -> bytes:
        """Convert dict to JSON and prepend length header"""
        json_msg = json.dumps(message).encode('utf-8')
        header = struct.pack('!I', len(json_msg))  # network byte order
        return header + json_msg
    
    @staticmethod
    def decode_message(data: bytes) -> dict:
        """Extract JSON message from bytes"""
        json_msg = data.decode('utf-8')
        return json.loads(json_msg)
    
    @staticmethod
    def create_control_message(msg_type: str, **kwargs) -> bytes:
        """Create standard control message"""
        message = {'type': msg_type, **kwargs}
        return Protocol.encode_message(message)
```

`shared/ssl_utils.py`:
```python
import ssl
import socket
from pathlib import Path

def create_ssl_context(certfile: str, keyfile: str, server_side: bool = False) -> ssl.SSLContext:
    """Create and configure SSL context"""
    context = ssl.create_default_context(
        ssl.Purpose.CLIENT_AUTH if server_side else ssl.Purpose.SERVER_AUTH
    )
    context.load_cert_chain(certfile=certfile, keyfile=keyfile)
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE  # For self-signed certs
    return context

def wrap_socket(sock: socket.socket, ssl_context: ssl.SSLContext, server_side: bool = False) -> ssl.SSLSocket:
    """Wrap socket with SSL"""
    return ssl_context.wrap_socket(
        sock,
        server_side=server_side,
        do_handshake_on_connect=True,
        suppress_ragged_eofs=True
    )
```

## 2. Server Implementation

`server/connection_manager.py`:
```python
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
```

`server/main.py`:
```python
from connection_manager import ConnectionManager
import argparse

def main():
    parser = argparse.ArgumentParser(description="Video Call Server")
    parser.add_argument('--host', default='0.0.0.0', help='Server host address')
    parser.add_argument('--port', type=int, default=5000, help='Server port')
    parser.add_argument('--cert', default='ssl/cert.pem', help='SSL certificate file')
    parser.add_argument('--key', default='ssl/key.pem', help='SSL key file')
    
    args = parser.parse_args()
    
    server = ConnectionManager(
        host=args.host,
        port=args.port,
        certfile=args.cert,
        keyfile=args.key
    )
    
    server.start()

if __name__ == "__main__":
    main()
```

## 3. Client Implementation

`client/network_handler.py`:
```python
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
```

`client/main.py`:
```python
from network_handler import NetworkHandler
import argparse
import threading
import time

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
    parser.add_argument('--cert', default='ssl/cert.pem', help='SSL certificate file')
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
```

## 4. SSL Certificate Generation

First, let's create the SSL certificate. Run this in your terminal:

```bash
mkdir -p ssl
openssl req -x509 -newkey rsa:4096 -keyout ssl/key.pem -out ssl/cert.pem -days 365 -nodes -subj "/CN=localhost"
```

## 5. requirements.txt

```
# Only using standard library modules
# This file is empty as we're not using external dependencies
```

## Running the System

1. Start the server in one terminal:
```bash
python server/main.py
```

2. Start client 1 in another terminal:
```bash
python client/main.py --username user1
```

3. Start client 2 in a third terminal:
```bash
python client/main.py --username user2
```

## Next Steps

This gives you a complete foundation with:
- Raw socket communication
- SSL encryption
- Basic protocol handling
- Multi-client support
- Graceful shutdown

To complete the video call functionality, you would need to:

1. Implement real video capture/display using OpenCV or similar
2. Add audio support with PyAudio
3. Enhance the media streaming protocol
4. Add room management on the server
5. Implement NAT traversal if needed

Would you like me to elaborate on any of these aspects or would you prefer to start with testing the basic communication system first?