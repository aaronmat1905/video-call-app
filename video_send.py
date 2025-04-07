import socket
import cv2
import threading

def start_video_send(peer_ip):
    def send_video():
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        cap = cv2.VideoCapture(0)
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            _, img = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 30])
            s.sendto(img.tobytes(), (peer_ip, 5000))
        cap.release()
    threading.Thread(target=send_video, daemon=True).start()
