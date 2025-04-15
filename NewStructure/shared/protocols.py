import json 
import struct

class Protocol:
    HEADER_SIZE = 4

    @staticmethod
    def encode_message(message:dict):
        """Convert dict to json and prepend length header"""
        json_msg = json.dumps(message).encode("utf-8")
        header = struct.pack("!I", len(json_msg))
        return header +json_msg
    @staticmethod
    def decode_message(data:bytes):
        """Extract JSON message from bytes"""
        json_msg = data.decode("utf-8")
        return json.loads(json_msg)
    @staticmethod
    def create_control_message(msg_type:str, **kwargs)->bytes:
        """Create standard control message"""
        message = {"type":msg_type, **kwargs}
        return Protocol.encode_message(message)