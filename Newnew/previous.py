import tkinter as tk
from tkinter import simpledialog, messagebox
import socket, ssl, threading, cv2, pickle, struct
import numpy as np

# ---- Control Socket (for JOIN/CALL/END) ----
class ControlClient:
    def __init__(self, name, host='localhost', port=5000):
        self.name = name
        self.host = host
        self.port = port
        self.context = ssl.create_default_context()
        self.context.check_hostname = False
        self.context.verify_mode = ssl.CERT_NONE
        self.sock = self.context.wrap_socket(socket.socket(socket.AF_INET), server_hostname=host)
        self.sock.connect((host, port))
        self.sock.send(name.encode())

        self.running = True
        threading.Thread(target=self.listen_server, daemon=True).start()

    def send(self, msg):
        self.sock.send(msg.encode())

    def listen_server(self):
        while self.running:
            try:
                data = self.sock.recv(4096).decode()
                if data:
                    print("[SERVER]", data)
                    if data.startswith("INCOMING|"):
                        caller = data.split("|")[1]
                        answer = messagebox.askyesno("Incoming Call", f"{caller} is calling you. Accept?")
                        if answer:
                            self.send(f"ACCEPT|{caller}")
                            start_video_stream()
                else:
                    break
            except:
                break

    def close(self):
        self.running = False
        self.send(f"END|{self.name}")
        self.sock.close()


# ---- Video Send/Receive Functions ----
def start_video_stream():
    threading.Thread(target=send_video, daemon=True).start()
    threading.Thread(target=receive_video, daemon=True).start()

def send_video():
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    sock = context.wrap_socket(socket.socket(socket.AF_INET))
    sock.connect(('localhost', 6000))  # video server port

    cap = cv2.VideoCapture(0)
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        _, buffer = cv2.imencode('.jpg', frame)
        data = pickle.dumps(buffer)
        size = struct.pack("L", len(data))
        try:
            sock.sendall(size + data)
        except:
            break
    cap.release()
    sock.close()

def receive_video():
    context = ssl.create_default_context()
    context.load_cert_chain(certfile='cert.pem', keyfile='key.pem')
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(('0.0.0.0', 6000))
    server.listen(1)
    conn, _ = server.accept()
    conn = context.wrap_socket(conn, server_side=True)

    data = b""
    payload_size = struct.calcsize("L")

    while True:
        while len(data) < payload_size:
            data += conn.recv(4096)
        packed_size = data[:payload_size]
        data = data[payload_size:]
        msg_size = struct.unpack("L", packed_size)[0]

        while len(data) < msg_size:
            data += conn.recv(4096)
        frame_data = data[:msg_size]
        data = data[msg_size:]

        frame = pickle.loads(frame_data)
        frame = cv2.imdecode(frame, cv2.IMREAD_COLOR)
        cv2.imshow('Video', frame)
        if cv2.waitKey(1) == 27:
            break
    conn.close()
    cv2.destroyAllWindows()

import tkinter as tk
from tkinter import simpledialog, messagebox
from PIL import Image, ImageTk
import socket, ssl, threading, pickle, struct, cv2

class VideoCallApp:
    def __init__(self, root):
        self.root = root
        self.root.title("🔐 Secure Video Call")
        self.root.geometry("600x500")
        self.root.configure(bg="#eaf4f4")

        self.name = simpledialog.askstring("Login", "Enter your name:")
        if not self.name:
            root.destroy()
            return

        self.frame = tk.Frame(root, bg="#ffffff", bd=2, relief=tk.RIDGE)
        self.frame.pack(pady=20, padx=20, fill=tk.X)

        tk.Label(self.frame, text=f"Welcome, {self.name}", font=("Helvetica", 16, "bold"), bg="#ffffff").pack(pady=(15, 5))

        tk.Label(self.frame, text="Call by Username:", font=("Helvetica", 12), bg="#ffffff").pack()
        self.user_entry = tk.Entry(self.frame, font=("Helvetica", 12), width=25)
        self.user_entry.pack(pady=5)
        tk.Button(self.frame, text="📞 Call User", font=("Helvetica", 12), bg="#4CAF50", fg="white", command=self.call_user).pack(pady=5)

        tk.Label(self.frame, text="Call by IP Address:", font=("Helvetica", 12), bg="#ffffff").pack()
        self.ip_entry = tk.Entry(self.frame, font=("Helvetica", 12), width=25)
        self.ip_entry.pack(pady=5)
        tk.Button(self.frame, text="🌐 Call IP", font=("Helvetica", 12), bg="#2196F3", fg="white", command=self.call_ip).pack(pady=5)

        tk.Button(self.frame, text="❌ Quit", font=("Helvetica", 12), bg="#f44336", fg="white", command=self.quit).pack(pady=10)

        # Video Frame Container
        self.video_panel = tk.Label(root)
        self.video_panel.pack(padx=10, pady=10)

        self.status = tk.Label(root, text="Status: Ready", bg="#eaf4f4", fg="gray")
        self.status.pack(side=tk.BOTTOM)

        self.running = True

    def call_user(self):
        user = self.user_entry.get()
        if not user:
            messagebox.showerror("Error", "Enter a username.")
            return
        # TODO: integrate control server call here
        self.status.config(text=f"Calling {user}...")
        self.start_video_stream('localhost')  # replace with resolved IP

    def call_ip(self):
        ip = self.ip_entry.get()
        if not ip:
            messagebox.showerror("Error", "Enter an IP address.")
            return
        self.status.config(text=f"Calling IP {ip}...")
        self.start_video_stream(ip)

    def start_video_stream(self, target_ip):
        threading.Thread(target=self.send_video, args=(target_ip,), daemon=True).start()
        threading.Thread(target=self.receive_video, daemon=True).start()

    def send_video(self, ip):
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        sock = context.wrap_socket(socket.socket(socket.AF_INET))
        try:
            sock.connect((ip, 6000))
        except Exception as e:
            self.status.config(text="Send Error: " + str(e))
            return

        cap = cv2.VideoCapture(0)
        while self.running:
            ret, frame = cap.read()
            if not ret:
                break
            _, buffer = cv2.imencode('.jpg', frame)
            data = pickle.dumps(buffer)
            size = struct.pack("L", len(data))
            try:
                sock.sendall(size + data)
            except:
                break
        cap.release()
        sock.close()

    def receive_video(self):
        context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        context.load_cert_chain(certfile='cert.pem', keyfile='key.pem')
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.bind(('0.0.0.0', 6000))
        server.listen(1)
        conn, _ = server.accept()
        conn = context.wrap_socket(conn, server_side=True)

        data = b""
        payload_size = struct.calcsize("L")

        while self.running:
            while len(data) < payload_size:
                packet = conn.recv(4096)
                if not packet:
                    return
                data += packet
            packed_size = data[:payload_size]
            data = data[payload_size:]
            msg_size = struct.unpack("L", packed_size)[0]

            while len(data) < msg_size:
                data += conn.recv(4096)
            frame_data = data[:msg_size]
            data = data[msg_size:]

            frame = pickle.loads(frame_data)
            frame = cv2.imdecode(frame, cv2.IMREAD_COLOR)
            img = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img = ImageTk.PhotoImage(Image.fromarray(img))

            self.video_panel.config(image=img)
            self.video_panel.image = img

        conn.close()

    def quit(self):
        self.running = False
        self.root.destroy()

# Main run
if __name__ == "__main__":
    root = tk.Tk()
    app = VideoCallApp(root)
    root.mainloop()
