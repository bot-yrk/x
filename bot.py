import os
import time
import random
import string
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import telebot
from psnawp_api import PSNAWP
from psnawp_api.core.psnawp_exceptions import PSNAWPNotFound

BOT_TOKEN = os.environ["BOT_TOKEN"]
NPSSO = os.environ["NPSSO"]
# أطوال اليوزر المطلوبة، مثال: "4,5"
LENGTHS = [int(x) for x in os.environ.get("LENGTHS", "4,5").split(",")]
# أقل وأكثر مدة انتظار بين كل فحص (بالثواني) عشان يكون بطيء وطبيعي
MIN_PAUSE = float(os.environ.get("MIN_PAUSE", "4"))
MAX_PAUSE = float(os.environ.get("MAX_PAUSE", "9"))

bot = telebot.TeleBot(BOT_TOKEN)
psn = PSNAWP(NPSSO)

LETTERS = string.ascii_lowercase
running = {}  # chat_id -> True/False
seen = set()


def make_name():
    """حروف + شرطة وحدة (_ أو -) مو في أول اليوزر ولا آخره"""
    length = random.choice(LENGTHS)
    dash = random.choice(["_", "-"])
    dash_pos = random.randint(1, length - 2)
    chars = [random.choice(LETTERS) for _ in range(length)]
    chars[dash_pos] = dash
    return "".join(chars)


def is_available(name):
    """لو سوني ما لقت حساب بهذا الاسم يعني متاح"""
    try:
        psn.user(online_id=name)
        return False
    except PSNAWPNotFound:
        return True


def hunt(chat_id):
    bot.send_message(chat_id, "بدأت البحث ✅ بأرسل لك بس المتاح.")
    while running.get(chat_id):
        name = make_name()
        if name in seen:
            continue
        seen.add(name)
        try:
            if is_available(name):
                bot.send_message(chat_id, f"متاح: {name}")
        except Exception as e:
            msg = str(e).lower()
            if "npsso" in msg or "401" in msg or "unauthor" in msg:
                bot.send_message(chat_id, "الـ NPSSO انتهى، جيب واحد جديد وحطه في Render.")
                running[chat_id] = False
                return
            # غالباً ضغط من سوني، ننتظر دقيقة
            time.sleep(60)
            continue
        time.sleep(random.uniform(MIN_PAUSE, MAX_PAUSE))


@bot.message_handler(commands=["start"])
def on_start(message):
    chat_id = message.chat.id
    if running.get(chat_id):
        bot.send_message(chat_id, "البحث شغال أصلاً.")
        return
    running[chat_id] = True
    threading.Thread(target=hunt, args=(chat_id,), daemon=True).start()


@bot.message_handler(commands=["stop"])
def on_stop(message):
    running[message.chat.id] = False
    bot.send_message(message.chat.id, "وقفت البحث.")


class Health(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, *args):
        pass


def run_health_server():
    port = int(os.environ.get("PORT", "10000"))
    HTTPServer(("0.0.0.0", port), Health).serve_forever()


if __name__ == "__main__":
    threading.Thread(target=run_health_server, daemon=True).start()
    bot.infinity_polling()
