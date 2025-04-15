import tkinter as tk
from tkinter import ttk
import cv2
from PIL import Image, ImageTk
from video_handler import VideoHandler
from audio_handler import AudioHandler
from network_handler import NetworkHandler

class VideoCallApp:
    def __init__(self, root, username, server_host, server_port, certfile):
        self.root = root
        self.username = username
        self.video = VideoHandler()
        self.audio = AudioHandler()
        self.network = NetworkHandler(server_host, server_port, certfile)
        
        self.setup_ui()
        self.setup_media()
        self.setup_network()

    def setup_ui(self):
        self.root.title(f"Video Call - {self.username}")
        
        # Video frames
        self.local_video = tk.Label(self.root)
        self.local_video.pack(side=tk.LEFT, padx=10, pady=10)
        
        self.remote_video = tk.Label(self.root)
        self.remote_video.pack(side=tk.RIGHT, padx=10, pady=10)
        
        # Controls
        control_frame = tk.Frame(self.root)
        control_frame.pack(side=tk.BOTTOM, fill=tk.X)
        
        self.btn_mute = ttk.Button(control_frame, text="Mute", command=self.toggle_mute)
        self.btn_mute.pack(side=tk.LEFT, padx=5)
        
        self.btn_video = ttk.Button(control_frame, text="Video Off", command=self.toggle_video)
        self.btn_video.pack(side=tk.LEFT, padx=5)
        
        ttk.Button(control_frame, text="Exit", command=self.shutdown).pack(side=tk.RIGHT, padx=5)
        
        # Update video frames
        self.update_local_video()
        self.update_remote_video()

    def setup_media(self):
        self.video.start_capture()
        self.audio.start()

    def setup_network(self):
        if self.network.connect():
            self.network.send_message({
                'type': 'JOIN',
                'username': self.username,
                'room': 'default'
            })
            self.network.start_receiving(self.handle_network_message)
        else:
            print("Failed to connect to server")

    def handle_network_message(self, message):
        msg_type = message.get('type')
        if msg_type == 'MEDIA':
            # Process incoming media
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
        # Placeholder for remote video
        self.root.after(1000, self.update_remote_video)

    def toggle_mute(self):
        pass

    def toggle_video(self):
        pass

    def shutdown(self):
        self.video.stop()
        self.audio.stop()
        self.network.disconnect()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = VideoCallApp(root, "test_user", "localhost", 5000, "ssl/cert.pem")
    root.mainloop()