import cv2, socket, ssl, pickle, struct
from common import create_ssl_context

def send_video(target_ip, port=6000):
    context = create_ssl_context()
    sock = context.wrap_socket(socket.socket(socket.AF_INET))
    sock.connect((target_ip, port))

    cap = cv2.VideoCapture(0)
    while True:
        ret, frame = cap.read()
        if not ret: break
        _, buffer = cv2.imencode('.jpg', frame)
        data = pickle.dumps(buffer)
        size = struct.pack("L", len(data))
        try:
            sock.sendall(size + data)
        except:
            break
    cap.release()
    sock.close()

def receive_video(port=6000):
    context = create_ssl_context(server=True)
    sock = socket.socket(socket.AF_INET)
    sock.bind(('0.0.0.0', port))
    sock.listen(1)
    conn, _ = sock.accept()
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
        cv2.imshow('Group Video Room', frame)
        if cv2.waitKey(1) == 27: break
    conn.close()
    cv2.destroyAllWindows()
