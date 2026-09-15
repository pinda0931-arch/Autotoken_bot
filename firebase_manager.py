import requests

def check_firebase_online(firebase_url: str) -> bool:
    try:
        r = requests.get(f"{firebase_url.rstrip('/')}.json", timeout=4)
        return r.status_code == 200
    except Exception:
        return False

def get_devices(firebase_url: str) -> dict:
    try:
        r = requests.get(f"{firebase_url.rstrip('/')}/devices.json", timeout=5)
        data = r.json()
        if isinstance(data, dict):
            return data
        return {}
    except Exception:
        return {}

def get_device_status(firebase_url: str, device_id: str) -> str:
    try:
        r = requests.get(
            f"{firebase_url.rstrip('/')}/devices/{device_id}/status.json",
            timeout=4
        )
        val = r.json()
        if val in ["online", True, 1, "1"]:
            return "🟢 Online"
        return "🔴 Offline"
    except Exception:
        return "❓ Unknown"

def read_incoming_sms(firebase_url: str, device_id: str, sim: str) -> list:
    try:
        path = f"{firebase_url.rstrip('/')}/devices/{device_id}/sms/{sim}.json"
        r = requests.get(path, timeout=4)
        data = r.json()
        if not isinstance(data, dict):
            return []
        results = []
        for key, val in data.items():
            if isinstance(val, dict):
                results.append({
                    "key": key,
                    "from": val.get("from", ""),
                    "body": val.get("body", val.get("message", ""))
                })
        return results
    except Exception:
        return []

def clear_sms_entry(firebase_url: str, device_id: str, sim: str, key: str):
    try:
        path = f"{firebase_url.rstrip('/')}/devices/{device_id}/sms/{sim}/{key}.json"
        requests.delete(path, timeout=4)
    except Exception:
        pass
