import ssl 
import socket
from pathlib import Path

def create_ssl_context(certfile:str, keyfile:str, server_side:bool = False):
    """Create and configure SSL Context"""
    context = ssl.create_default_context(
        ssl.Purpose.CLIENT_AUTH if server_side else ssl.Purpose.SERVER_AUTH
    )
    context.load_cert_chain(certfile= certfile, keyfile=keyfile)
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    return context

def wrap_socket(
        sock:socket.socket, 
        ssl_context:ssl.SSLContext, 
        server_side:bool = False
)->ssl.SSLSocket:
    """Wrap socket with SSL"""
    return ssl_context.wrap_socket(
        sock, 
        server_side = server_side, 
        do_handshake_on_connect= True, 
        suppress_ragged_eofs=True
    )