import socket, ssl, threading
from common import create_ssl_context

clients = {}
lock = threading.Lock()

def broadcast_user_list():
    user_list = "|".join(clients.keys())
    for conn in clients.values():
        try:
            conn.send(f"USERLIST|{user_list}".encode())
        except:
            pass

def handle_client(conn, addr):
    try:
        name = conn.recv(1024).decode()
        with lock:
            clients[name] = conn
            print(f"{name} joined from {addr}")
            broadcast_user_list()

        while True:
            msg = conn.recv(4096).decode()
            if not msg:
                break
            print(f"[{name}] {msg}")

            if msg.startswith("CALL|"):
                target = msg.split("|")[1]
                with lock:
                    if target in clients:
                        clients[target].send(f"INCOMING|{name}".encode())

            elif msg.startswith("ACCEPT|"):
                caller = msg.split("|")[1]
                with lock:
                    if caller in clients:
                        clients[caller].send(f"ACCEPTED|{name}".encode())

    except Exception as e:
        print("Error:", e)

    finally:
        with lock:
            if name in clients:
                del clients[name]
                broadcast_user_list()
        conn.close()

def start_server(host='0.0.0.0', port=5000):
    context = create_ssl_context(server=True)
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind((host, port))
    sock.listen(5)
    print(f"[SERVER] Running on {host}:{port}")

    while True:
        client_sock, addr = sock.accept()
        conn = context.wrap_socket(client_sock, server_side=True)
        threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()

if __name__ == "__main__":
    start_server()
