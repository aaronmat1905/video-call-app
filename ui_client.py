import tkinter as tk
from tkinter import messagebox
from video_send import start_video_send
from audio_send import start_audio_send
from video_recv import start_video_recv
from audio_recv import start_audio_recv
from utils.ping_check import is_peer_alive
from utils.incoming_ping_listener import start_ping_listener
import cv2
from PIL import Image, ImageTk

class VideoCallApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Video Call App")
        self.peer_ip = ""
        self.video_on = True
        self.audio_on = True
        self.in_call = False

        self.create_ui()
        start_audio_recv()
        start_video_recv(self.update_remote_video)
        start_ping_listener(self.incoming_call_notify)

    def create_ui(self):
        self.remote_label = tk.Label(self.root, text="Remote Video")
        self.remote_label.pack()

        self.remote_canvas = tk.Label(self.root)
        self.remote_canvas.pack()

        self.ip_entry = tk.Entry(self.root, width=30)
        self.ip_entry.insert(0, "Enter peer IP address")
        self.ip_entry.pack()

        self.start_button = tk.Button(self.root, text="Start Call", command=self.start_call)
        self.start_button.pack(pady=5)

        self.mute_button = tk.Button(self.root, text="Mute", command=self.toggle_audio)
        self.mute_button.pack(pady=5)

        self.video_button = tk.Button(self.root, text="Stop Video", command=self.toggle_video)
        self.video_button.pack(pady=5)

    def update_remote_video(self, frame):
        img = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(img)
        imgtk = ImageTk.PhotoImage(image=img)
        self.remote_canvas.imgtk = imgtk
        self.remote_canvas.configure(image=imgtk)

    def start_call(self):
        self.peer_ip = self.ip_entry.get()
        if not is_peer_alive(self.peer_ip):
            messagebox.showerror("Peer Not Found", "Could not reach peer at IP: " + self.peer_ip)
            return
        start_audio_send(self.peer_ip)
        start_video_send(self.peer_ip)
        self.in_call = True

    def toggle_audio(self):
        self.audio_on = not self.audio_on
        self.mute_button.config(text="Unmute" if not self.audio_on else "Mute")
        # Optional: Add logic to pause/resume audio stream

    def toggle_video(self):
        self.video_on = not self.video_on
        self.video_button.config(text="Start Video" if not self.video_on else "Stop Video")
        # Optional: Add logic to pause/resume video stream

    def incoming_call_notify(self, sender_ip):
        if not self.in_call:
            response = messagebox.askyesno("Incoming Call", f"Call from {sender_ip}. Accept?")
            if response:
                self.peer_ip = sender_ip
                start_audio_send(self.peer_ip)
                start_video_send(self.peer_ip)
                self.in_call = True

if __name__ == "__main__":
    root = tk.Tk()
    app = VideoCallApp(root)
    root.mainloop()
