from server.connection_manager import ConnectionManager
import argparse

def main():
    parser = argparse.ArgumentParser(description="Video Call Server")
    parser.add_argument('--host', default='0.0.0.0', help='Server host address')
    parser.add_argument('--port', type=int, default=5000, help='Server port')
    parser.add_argument('--cert', default='ssl/cert.pem', help='SSL certificate file')
    parser.add_argument('--key', default='ssl/key.pem', help='SSL key file')
    
    args = parser.parse_args()
    
    server = ConnectionManager(
        host=args.host,
        port=args.port,
        certfile=args.cert,
        keyfile=args.key
    )
    
    server.start()

if __name__ == "__main__":
    main()