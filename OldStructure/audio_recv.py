import socket
import pyaudio
import threading

def start_audio_recv():
    CHUNK = 1024
    FORMAT = pyaudio.paInt16
    CHANNELS = 1
    RATE = 44100

    p = pyaudio.PyAudio()
    stream = p.open(format=FORMAT, channels=CHANNELS, rate=RATE, output=True, frames_per_buffer=CHUNK)

    def recv_audio():
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.bind(("", 6000))
        while True:
            try:
                data, _ = s.recvfrom(2048)
                stream.write(data)
            except:
                pass
    threading.Thread(target=recv_audio, daemon=True).start()
