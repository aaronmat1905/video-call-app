import argparse
import socket
import ssl
import struct
import threading
import time
from queue import Queue
from typing import Optional, Callable

import pyaudio
import numpy as np
import cv2
from PIL import Image, ImageTk
import tkinter as tk
from tkinter import ttk

from shared import protocols, ssl_utils


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
            format=self.format, channels=self.channels,
            rate=self.rate, input=True, frames_per_buffer=self.chunk
        )
        self.stream_out = self.audio.open(
            format=self.format, channels=self.channels,
            rate=self.rate, output=True, frames_per_buffer=self.chunk
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
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        ssl_context = ssl_utils.create_ssl_context(
            self.certfile, '../ssl/key.pem', server_side=False
        )
        try:
            self.socket.connect((self.host, self.port))
            self.ssl_socket = ssl_utils.wrap_socket(self.socket, ssl_context)
            self.running = True
            return True
        except Exception as e:
            print(f"Connection failed: {e}")
            return False

    def start_receiving(self, callback: Callable):
        self.message_callback = callback
        threading.Thread(target=self._receive_loop, daemon=True).start()

    def _receive_loop(self):
        try:
            while self.running and self.ssl_socket:
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
        if self.ssl_socket and self.running:
            try:
                self.ssl_socket.sendall(protocols.Protocol.encode_message(message))
            except Exception as e:
                print(f"Failed to send message: {e}")
                self.disconnect()

    def disconnect(self):
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


class VideoCallApp:
    def __init__(self, root, username, server_host, server_port, certfile):
        self.root = root
        self.username = username
        self.video = VideoHandler()
        self.audio = AudioHandler()
        self.network = NetworkHandler(server_host, server_port, certfile)
        self.connected = False

        self.setup_ui()
        self.setup_media()
        self.setup_network()

    def setup_ui(self):
        self.root.title(f"Video Call - {self.username}")

        self.local_video = tk.Label(self.root)
        self.local_video.pack(side=tk.LEFT, padx=10, pady=10)

        self.remote_video = tk.Label(self.root)
        self.remote_video.pack(side=tk.RIGHT, padx=10, pady=10)

        control_frame = tk.Frame(self.root)
        control_frame.pack(side=tk.BOTTOM, fill=tk.X)

        self.btn_mute = ttk.Button(control_frame, text="Mute", command=self.toggle_mute)
        self.btn_mute.pack(side=tk.LEFT, padx=5)

        self.btn_video = ttk.Button(control_frame, text="Video Off", command=self.toggle_video)
        self.btn_video.pack(side=tk.LEFT, padx=5)

        ttk.Button(control_frame, text="Exit", command=self.shutdown).pack(side=tk.RIGHT, padx=5)

        self.update_local_video()
        self.update_remote_video()

    def setup_media(self):
        self.video.start_capture()
        self.audio.start()

    def setup_network(self):
        if self.network.connect():
            self.connected = True
            self.network.send_message({
                'type': 'JOIN',
                'username': self.username,
                'room': 'default'
            })
            self.network.start_receiving(self.handle_network_message)
            self.start_dummy_media()
        else:
            print("Failed to connect to server")

    def handle_network_message(self, message):
        msg_type = message.get('type')
        if msg_type == 'MEDIA':
            # TODO: Handle incoming media stream
            pass

    def update_local_video(self):
        frame = self.video.get_frame()
        if frame is not None:
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(frame)
            imgtk = ImageTk.PhotoImage(image=img)
            self.local_video.imgtk = imgtk
            self.local_video.configure(image=imgtk)
        self.root.after(30, self.update_local_video)

    def update_remote_video(self):
        # Placeholder for remote video feed
        self.root.after(1000, self.update_remote_video)

    def start_dummy_media(self):
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

        threading.Thread(target=send_dummy, daemon=True).start()

    def toggle_mute(self):
        pass  # TODO: Implement mute/unmute logic

    def toggle_video(self):
        pass  # TODO: Implement video on/off logic

    def shutdown(self):
        self.connected = False
        self.video.stop()
        self.audio.stop()
        self.network.send_message({
            'type': 'LEAVE',
            'username': self.username
        })
        time.sleep(0.5)
        self.network.disconnect()
        self.root.destroy()


def main():
    parser = argparse.ArgumentParser(description="Video Call Client")
    parser.add_argument('--host', default='localhost', help='Server host')
    parser.add_argument('--port', type=int, default=5000, help='Server port')
    parser.add_argument('--cert', default='../ssl/cert.pem', help='SSL certificate file')
    parser.add_argument('--username', required=True, help='Your username')
    args = parser.parse_args()

    root = tk.Tk()
    app = VideoCallApp(root, args.username, args.host, args.port, args.cert)
    root.mainloop()


if __name__ == "__main__":
    main()
