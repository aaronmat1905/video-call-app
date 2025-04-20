import tkinter as tk
from tkinter import simpledialog, messagebox
from common import get_local_ip, create_ssl_context
import socket, threading
from video_stream import send_video, receive_video

class ClientApp:
    def __init__(self, root):
        self.root = root
        self.root.title("📹 VideoCall Group App")
        self.root.geometry("500x600")
        self.root.configure(bg="#fafafa")  # Light grey background

        # Ask for name and server IP
        self.name = simpledialog.askstring("Your Name", "Enter your name:")
        if not self.name:
            root.destroy()
            return

        self.server_ip = simpledialog.askstring("Server IP", "Enter Server IP:", initialvalue=get_local_ip())
        self.context = create_ssl_context()
        self.sock = self.context.wrap_socket(socket.socket(socket.AF_INET))
        self.sock.connect((self.server_ip, 5000))
        self.sock.send(self.name.encode())

        self.members = []
        self.build_ui()
        threading.Thread(target=self.listen_server, daemon=True).start()

    def build_ui(self):
        self.frame = tk.Frame(self.root, bg="white", bd=10, relief="solid", padx=20, pady=20)
        self.frame.place(relx=0.5, rely=0.5, anchor=tk.CENTER)

        tk.Label(self.frame, text=f"Logged in as: {self.name}", bg="white", font=("Helvetica", 14, "bold"), fg="#333").pack(pady=10)

        # User listbox for showing active users
        self.user_listbox = tk.Listbox(self.frame, height=10, width=35, font=("Helvetica", 12), bg="#f0f0f0", bd=0, selectmode=tk.SINGLE)
        self.user_listbox.pack(pady=10)
        
        # Input field for call target
        self.target_entry = tk.Entry(self.frame, font=("Helvetica", 12), width=20, bd=2, relief="solid", borderwidth=2)
        self.target_entry.pack(pady=10)

        # Call button with a rounded and modern look
        self.call_button = tk.Button(self.frame, text="📞 Call", bg="#4CAF50", fg="white", font=("Helvetica", 12, "bold"), relief="flat", width=15, height=2, command=self.call_user)
        self.call_button.pack(pady=5)

        # Receive button
        self.receive_button = tk.Button(self.frame, text="📺 Receive", bg="#2196F3", fg="white", font=("Helvetica", 12, "bold"), relief="flat", width=15, height=2, command=receive_video)
        self.receive_button.pack(pady=5)

        # Quit button with a red background
        self.quit_button = tk.Button(self.frame, text="❌ Quit", bg="#f44336", fg="white", font=("Helvetica", 12, "bold"), relief="flat", width=15, height=2, command=self.quit_app)
        self.quit_button.pack(pady=20)

    def call_user(self):
        target = self.target_entry.get()
        if not target:
            messagebox.showerror("Input error", "Enter a name")
            return
        self.sock.send(f"CALL|{target}".encode())

    def listen_server(self):
        while True:
            try:
                data = self.sock.recv(4096).decode()
                if data.startswith("INCOMING|"):
                    caller = data.split("|")[1]
                    answer = messagebox.askyesno("Incoming Call", f"{caller} is calling. Accept?")
                    if answer:
                        self.sock.send(f"ACCEPT|{caller}".encode())
                        send_video(self.server_ip)
                elif data.startswith("USERLIST|"):
                    userlist = data.split("|")[1:]
                    self.update_user_list(userlist)
                elif data.startswith("ACCEPTED|"):
                    send_video(self.server_ip)
            except:
                break

    def update_user_list(self, userlist):
        """Update the user listbox with the names of all connected users"""
        self.user_listbox.delete(0, tk.END)
        for user in userlist:
            if user != self.name:
                self.user_listbox.insert(tk.END, user)

    def quit_app(self):
        self.sock.send(f"END|{self.name}".encode())
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = ClientApp(root)
    root.mainloop()