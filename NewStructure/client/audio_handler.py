import pyaudio
import numpy as np
from queue import Queue
import threading

class AudioHandler:
    def __init__(self):
        self.audio = pyaudio.PyAudio()
        self.format = pyaudio.paInt16
        self.channels = 1
        self.rate = 44100
        self.chunk = 1024
        self.input_queue = Queue(maxsize=10)
        self.output_queue = Queue(maxsize=10)
        self.running = False

    def start(self):
        self.running = True
        self.stream_in = self.audio.open(
            format=self.format,
            channels=self.channels,
            rate=self.rate,
            input=True,
            frames_per_buffer=self.chunk
        )
        self.stream_out = self.audio.open(
            format=self.format,
            channels=self.channels,
            rate=self.rate,
            output=True,
            frames_per_buffer=self.chunk
        )
        threading.Thread(target=self._capture_audio, daemon=True).start()
        threading.Thread(target=self._play_audio, daemon=True).start()

    def _capture_audio(self):
        while self.running:
            data = self.stream_in.read(self.chunk, exception_on_overflow=False)
            if self.input_queue.full():
                self.input_queue.get()
            self.input_queue.put(data)

    def _play_audio(self):
        while self.running:
            if not self.output_queue.empty():
                data = self.output_queue.get()
                self.stream_out.write(data)

    def stop(self):
        self.running = False
        self.stream_in.stop_stream()
        self.stream_out.stop_stream()
        self.stream_in.close()
        self.stream_out.close()
        self.audio.terminate()