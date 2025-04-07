import socket
import threading

def start_ping_listener(notify_callback):
    def listener():
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.bind(("", 5001))
        while True:
            data, addr = s.recvfrom(1024)
            if data == b"ping":
                s.sendto(b"pong", addr)
            else:
                notify_callback(addr[0])
    threading.Thread(target=listener, daemon=True).start()
