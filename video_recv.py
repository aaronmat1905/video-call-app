import socket
import cv2
import numpy as np
import threading

def start_video_recv(callback):
    def recv_video():
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.bind(("", 5000))
        while True:
            packet, _ = s.recvfrom(65536)
            npdata = np.frombuffer(packet, dtype=np.uint8)
            frame = cv2.imdecode(npdata, 1)
            callback(frame)
    threading.Thread(target=recv_video, daemon=True).start()
