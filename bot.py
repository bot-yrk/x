import os
import time
import random
import string
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import requests
import telebot
from psnawp_api import PSNAWP

BOT_TOKEN = os.environ["BOT_TOKEN"]
NPSSO = os.environ["NPSSO"]
LENGTHS = [int(x) for x in os.environ.get("LENGTHS", "4,5").split(",")]
MIN_PAUSE = float(os.environ.get("MIN_PAUSE", "4"))
MAX_PAUSE = float(os.environ.get("MAX_PAUSE", "9"))

# نفس فحص خانة تغيير الاسم في سوني (ما يحجز الاسم)
CHECK_URL = "https://accounts.api.playstation.com/api/v1/accounts/onlineIds"

bot = telebot.TeleBot(BOT_TOKEN)
psn = PSNAWP(NPSSO)

LETTERS = string.ascii_lowercase
running = {}
seen = set()


class AuthError(Exception):
    pass


class RateLimit(Exception):
    pass


def get_token():
    auth = getattr(psn, "authenticator", None)
    token = getattr(auth, "access_token", None)
    if not token:
        raise AuthError("no token")
    return token


def make_name():
    length = random.choice(LENGTHS)
    dash = random.choice(["_", "-"])
    dash_pos = random.randint(1, length - 2)
    chars = [random.choice(LETTERS) for _ in range(length)]
    chars[dash_pos] = dash
    return "".join(chars)


def check(name):
    """يرجع (متاح؟، الرد الخام)"""
    r = requests.post(
        CHECK_URL,
        headers={
            "Authorization": "Bearer " + get_token(),
            "Content-Type": "application/json",
        },
        json={"onlineId": name, "reserveIfAvailable": False},
        timeout=20,
    )
    raw = f"{r.status_code} {r.text[:300]}"
    if r.status_code in (401, 403):
        raise AuthError(raw)
    if r.status_code == 429:
        raise RateLimit(raw)
    return r.status_code == 200, raw


def hunt(chat_id):
    bot.send_message(chat_id, "بدأت البحث ✅ بأرسل لك بس المتاح.")
    first = True
    while running.get(chat_id):
        name = make_name()
        if name in seen:
            continue
        seen.add(name)
        try:
            ok, raw = check(name)
            if first:
                # رسالة تشخيص مرة وحدة عشان نتأكد من رد سوني
                bot.send_message(chat_id, f"تشخيص ({name}): {raw}")
                first = False
            if ok:
                bot.send_message(chat_id, f"متاح: {name}")
        except AuthError as e:
            bot.send_message(chat_id, f"مشكلة دخول (NPSSO أو التوكن): {e}")
            running[chat_id] = False
            return
        except RateLimit:
            time.sleep(90)
            continue
        except Exception as e:
            bot.send_message(chat_id, f"خطأ: {e}")
            time.sleep(30)
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
