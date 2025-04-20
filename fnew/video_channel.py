import socket
import threading
import cv2
import pickle
import struct

import socket
import pickle

class VideoChannel:
    def __init__(self, port=6002):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(('0.0.0.0', port))
        self.port = port

    def start_receiver(self, callback):
        """Renamed from process_frame to match your earlier code"""
        def receive_frames():
            while True:
                data, addr = self.sock.recvfrom(65536)
                frame = pickle.loads(data)
                callback(frame)
        threading.Thread(target=receive_frames, daemon=True).start()

    def send_frame(self, frame, target_ip):
        """Send frame to target"""
        data = pickle.dumps(frame)
        self.sock.sendto(data, (target_ip, self.port))