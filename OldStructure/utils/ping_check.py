import socket

def is_peer_alive(ip, port=5001):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(1)
        s.sendto(b"ping", (ip, port))
        data, _ = s.recvfrom(1024)
        return data == b"pong"
    except:
        return False
