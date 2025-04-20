import socket
import threading
import pyaudio
import pickle

class AudioChannel:
    def __init__(self, port=6003):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(('0.0.0.0', port))
        self.audio = pyaudio.PyAudio()
        
    def start_receiver(self, callback):
        def receive_audio():
            while True:
                data, _ = self.sock.recvfrom(4096)
                audio_frame = pickle.loads(data)
                callback(audio_frame)
        
        threading.Thread(target=receive_audio, daemon=True).start()
    
    def send_audio(self, audio_frame, target_ip):
        data = pickle.dumps(audio_frame)
        self.sock.sendto(data, (target_ip, 6001))