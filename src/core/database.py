import sqlite3
import os

class DBManager:
    def __init__(self, drive_path, drive_name):
        self.db_path = os.path.join(drive_path, f"{drive_name}.db")

    def initialize(self, metadata):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT)")
            conn.execute("CREATE TABLE IF NOT EXISTS chunks (chunk_index INTEGER PRIMARY KEY, hash TEXT, filename TEXT)")
            for k, v in metadata.items():
                conn.execute("INSERT OR REPLACE INTO metadata VALUES (?, ?)", (k, str(v)))

    def update_chunk(self, index, h, filename):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("INSERT OR REPLACE INTO chunks VALUES (?, ?, ?)", (index, h, filename))

    def get_chunks(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            return [dict(r) for r in conn.execute("SELECT * FROM chunks ORDER BY chunk_index ASC").fetchall()]

    def get_meta(self, key):
        with sqlite3.connect(self.db_path) as conn:
            res = conn.execute("SELECT value FROM metadata WHERE key = ?", (key,)).fetchone()
            return res[0] if res else None
