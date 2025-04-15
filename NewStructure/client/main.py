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