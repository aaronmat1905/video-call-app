import cv2
import numpy as np
import threading
from queue import Queue

class VideoHandler:
    def __init__(self):
        self.cap = cv2.VideoCapture(0)
        self.frame_queue = Queue(maxsize=10)
        self.running = False
        self.width = 640
        self.height = 480
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)

    def start_capture(self):
        self.running = True
        threading.Thread(target=self._capture_frames, daemon=True).start()

    def _capture_frames(self):
        while self.running:
            ret, frame = self.cap.read()
            if ret:
                if self.frame_queue.full():
                    self.frame_queue.get()
                self.frame_queue.put(frame)

    def get_frame(self):
        return self.frame_queue.get() if not self.frame_queue.empty() else None

    def stop(self):
        self.running = False
        self.cap.release()