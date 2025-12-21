import sqlite3
import os

class DBManager:
    def __init__(self, drive_path, drive_name):
        self.db_path = os.path.join(drive_path, f"{drive_name}.db")

    def _get_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA journal_mode=WAL;")
        return conn

    def initialize(self, metadata):
        with self._get_conn() as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT)")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS chunks (
                    chunk_index INTEGER PRIMARY KEY, 
                    hash TEXT, 
                    filename TEXT,
                    size INTEGER,
                    mtime REAL
                )
            """)
            for k, v in metadata.items():
                conn.execute("INSERT OR REPLACE INTO metadata VALUES (?, ?)", (k, str(v)))

    def update_chunk(self, index, h, filename, size, mtime):
        with self._get_conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO chunks (chunk_index, hash, filename, size, mtime) VALUES (?, ?, ?, ?, ?)", 
                (index, h, filename, size, mtime)
            )

    def get_chunks(self):
        with self._get_conn() as conn:
            conn.row_factory = sqlite3.Row
            return [dict(r) for r in conn.execute("SELECT * FROM chunks ORDER BY chunk_index ASC").fetchall()]

    def get_meta(self, key):
        with self._get_conn() as conn:
            res = conn.execute("SELECT value FROM metadata WHERE key = ?", (key,)).fetchone()
            return res[0] if res else None
