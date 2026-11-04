"""SQLite store: completed-fire registry (survives crashes) plus agent memory tables."""
import sqlite3


class Store:
    def __init__(self, path: str = ":memory:"):
        self.db = sqlite3.connect(path)
        self.db.executescript(
            """
            CREATE TABLE IF NOT EXISTS fires(
                fire_id TEXT PRIMARY KEY, status TEXT, t REAL, attempts INTEGER DEFAULT 0,
                not_before REAL DEFAULT 0, error TEXT);
            CREATE TABLE IF NOT EXISTS notes(
                id INTEGER PRIMARY KEY AUTOINCREMENT, bucket TEXT, text TEXT);
            CREATE TABLE IF NOT EXISTS kv(k TEXT PRIMARY KEY, v TEXT);
            """
        )
        self.db.commit()

    # fire registry
    def load_state(self):
        completed, dead, attempts, not_before = {}, set(), {}, {}
        for fid, status, t, att, nb in self.db.execute("SELECT fire_id,status,t,attempts,not_before FROM fires"):
            if status == "done":
                completed[fid] = t
            elif status == "dead":
                dead.add(fid)
            else:
                attempts[fid], not_before[fid] = att, nb
        return completed, dead, attempts, not_before

    def mark_done(self, fire_id: str, t: float) -> None:
        self.db.execute("INSERT OR REPLACE INTO fires(fire_id,status,t) VALUES(?, 'done', ?)", (fire_id, t))
        self.db.commit()

    def mark_dead(self, fire_id: str, error: str, attempts: int) -> None:
        self.db.execute(
            "INSERT OR REPLACE INTO fires(fire_id,status,attempts,error) VALUES(?, 'dead', ?, ?)",
            (fire_id, attempts, error))
        self.db.commit()

    def mark_retry(self, fire_id: str, attempts: int, not_before: float) -> None:
        self.db.execute(
            "INSERT OR REPLACE INTO fires(fire_id,status,attempts,not_before) VALUES(?, 'retry', ?, ?)",
            (fire_id, attempts, not_before))
        self.db.commit()

    def counts(self) -> dict:
        return dict(self.db.execute("SELECT status, COUNT(*) FROM fires GROUP BY status").fetchall())

    # memory tables
    def add_note(self, bucket: str, text: str) -> None:
        self.db.execute("INSERT INTO notes(bucket,text) VALUES(?,?)", (bucket, text))
        self.db.commit()

    def notes(self, bucket: str) -> list[str]:
        return [r[0] for r in self.db.execute("SELECT text FROM notes WHERE bucket=? ORDER BY id", (bucket,))]

    def clear_bucket(self, bucket: str) -> None:
        self.db.execute("DELETE FROM notes WHERE bucket=?", (bucket,))
        self.db.commit()

    def dump(self) -> dict:
        notes = [[b, t] for b, t in self.db.execute("SELECT bucket,text FROM notes ORDER BY id")]
        return {"notes": notes, "kv": dict(self.db.execute("SELECT k,v FROM kv"))}

    def wipe_memory(self) -> None:
        self.db.execute("DELETE FROM notes")
        self.db.execute("DELETE FROM kv")
        self.db.commit()

    def load(self, state: dict) -> None:
        self.wipe_memory()
        for bucket, text in state["notes"]:
            self.db.execute("INSERT INTO notes(bucket,text) VALUES(?,?)", (bucket, text))
        for k, v in state["kv"].items():
            self.db.execute("INSERT INTO kv(k,v) VALUES(?,?)", (k, v))
        self.db.commit()

    def kv_put(self, k: str, v: str) -> None:
        self.db.execute("INSERT OR REPLACE INTO kv(k,v) VALUES(?,?)", (k, v))
        self.db.commit()

    def kv_get(self, k: str):
        row = self.db.execute("SELECT v FROM kv WHERE k=?", (k,)).fetchone()
        return row[0] if row else None
