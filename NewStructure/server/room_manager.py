from typing import Dict, Set
import threading

class RoomManager:
    def __init__(self):
        self.rooms: Dict[str, Set[str]] = {}
        self.lock = threading.Lock()

    def add_user(self, room: str, username: str):
        with self.lock:
            if room not in self.rooms:
                self.rooms[room] = set()
            self.rooms[room].add(username)

    def remove_user(self, room: str, username: str):
        with self.lock:
            if room in self.rooms:
                self.rooms[room].discard(username)
                if not self.rooms[room]:
                    del self.rooms[room]

    def get_users(self, room: str) -> Set[str]:
        with self.lock:
            return self.rooms.get(room, set()).copy()