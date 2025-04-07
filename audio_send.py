import socket
import pyaudio
import threading

def start_audio_send(peer_ip):
    CHUNK = 1024
    FORMAT = pyaudio.paInt16
    CHANNELS = 1
    RATE = 44100

    def send_audio():
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        p = pyaudio.PyAudio()
        stream = p.open(format=FORMAT, channels=CHANNELS, rate=RATE, input=True, frames_per_buffer=CHUNK)
        while True:
            try:
                data = stream.read(CHUNK)
                s.sendto(data, (peer_ip, 6000))
            except:
                pass
    threading.Thread(target=send_audio, daemon=True).start()
