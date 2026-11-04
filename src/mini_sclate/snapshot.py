"""SaveState / RestoreState for the agent's memory (paper Table 4: save_state, restore_state).
A snapshot carries an integrity token; restore refuses a torn or partial save."""
import hashlib
import json
import os


class TornSnapshot(Exception):
    pass


def _digest(payload: str) -> str:
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def save_state(store, path: str) -> None:
    payload = json.dumps(store.dump(), sort_keys=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"payload": payload, "sha256": _digest(payload)}, f)
    os.replace(tmp, path)  # atomic: readers see the old or the new snapshot, never half of one


def restore_state(store, path: str) -> bool:
    """Returns False if no snapshot exists yet. Raises TornSnapshot if the file is partial or tampered."""
    if not os.path.exists(path):
        return False
    try:
        with open(path, encoding="utf-8") as f:
            doc = json.load(f)
        payload, token = doc["payload"], doc["sha256"]
    except (ValueError, KeyError) as exc:
        raise TornSnapshot(f"unreadable snapshot: {exc}") from exc
    if _digest(payload) != token:
        raise TornSnapshot("integrity token mismatch")
    store.load(json.loads(payload))
    return True
