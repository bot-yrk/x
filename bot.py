import os
import time
import random
import string
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import requests
import telebot

BOT_TOKEN = os.environ["BOT_TOKEN"]
NPSSO = os.environ["NPSSO"]
LENGTHS = [int(x) for x in os.environ.get("LENGTHS", "4,5").split(",")]
MIN_PAUSE = float(os.environ.get("MIN_PAUSE", "8"))
MAX_PAUSE = float(os.environ.get("MAX_PAUSE", "15"))

# نفس فحص خانة تغيير الاسم في سوني (ما يحجز الاسم)
CHECK_URL = "https://accounts.api.playstation.com/api/v1/accounts/onlineIds"

bot = telebot.TeleBot(BOT_TOKEN)

LETTERS = string.ascii_lowercase
running = {}
seen = set()


class AuthError(Exception):
    pass


class RateLimit(Exception):
    pass


_tok = {"value": None, "time": 0}
AUTH_URL = "https://ca.account.sony.com/api/authz/v3/oauth/authorize"
TOKEN_URL = "https://ca.account.sony.com/api/authz/v3/oauth/token"
CLIENT_ID = "09515159-7237-4370-9b40-3806e67c0891"
BASIC = "Basic MDk1MTUxNTktNzIzNy00MzcwLTliNDAtMzgwNmU2N2MwODkxOnVjUGprYTV0bnRCMktxc1A="
REDIRECT = "com.scee.psxandroid.scecompcall://redirect"


def get_token():
    if _tok["value"] and time.time() - _tok["time"] < 2700:
        return _tok["value"]
    r = requests.get(
        AUTH_URL,
        params={
            "access_type": "offline",
            "client_id": CLIENT_ID,
            "response_type": "code",
            "scope": "psn:mobile.v2.core psn:clientapp",
            "redirect_uri": REDIRECT,
        },
        headers={"Cookie": "npsso=" + NPSSO},
        allow_redirects=False,
        timeout=20,
    )
    loc = r.headers.get("Location", "")
    if "code=" not in loc:
        raise AuthError("NPSSO غلط أو منتهي، جيب واحد جديد")
    code = loc.split("code=")[1].split("&")[0]
    r = requests.post(
        TOKEN_URL,
        headers={"Authorization": BASIC, "Content-Type": "application/x-www-form-urlencoded"},
        data={
            "code": code,
            "redirect_uri": REDIRECT,
            "grant_type": "authorization_code",
            "token_format": "jwt",
        },
        timeout=20,
    )
    token = r.json().get("access_token")
    if not token:
        raise AuthError("ما قدرت أجيب التوكن: " + r.text[:200])
    _tok["value"], _tok["time"] = token, time.time()
    return token


def make_name():
    length = random.choice(LENGTHS)
    dash = random.choice(["_", "-"])
    dash_pos = random.randint(1, length - 2)
    chars = [random.choice(LETTERS) for _ in range(length)]
    chars[dash_pos] = dash
    return "".join(chars)


class Unknown(Exception):
    pass


class Blocked(Exception):
    pass


last_report = {"t": 0}


def check(name):
    """يرجع True لو متاح، False لو مأخوذ. وأي رد غريب يرمي Unknown"""
    r = requests.post(
        CHECK_URL,
        headers={
            "Authorization": "Bearer " + get_token(),
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        json={"onlineId": name, "reserveIfAvailable": False},
        timeout=20,
    )
    raw = f"{r.status_code} {r.text[:150]}"
    if r.status_code == 200:
        return True
    if r.status_code == 400 and "3101" in r.text:
        return False
    if r.status_code == 401:
        _tok["value"] = None
        raise Unknown(raw)
    if r.status_code == 403:
        raise Blocked(raw)
    if r.status_code == 429:
        raise RateLimit(raw)
    raise Unknown(raw)


def hunt(chat_id):
    bot.send_message(chat_id, "بدأت البحث ✅ بأرسل لك بس المتاح.")
    while running.get(chat_id):
        name = make_name()
        if name in seen:
            continue
        seen.add(name)
        try:
            if check(name):
                bot.send_message(chat_id, f"متاح: {name}")
        except AuthError as e:
            bot.send_message(chat_id, f"مشكلة دخول (NPSSO أو التوكن): {e}")
            running[chat_id] = False
            return
        except Blocked:
            # سوني (الحماية حقتها) رفضت الطلب: ننتظر 10 دقايق ونرجع
            seen.discard(name)
            if time.time() - last_report["t"] > 600:
                last_report["t"] = time.time()
                bot.send_message(chat_id, "سوني رفضت الطلبات مؤقتاً (مو مشكلة NPSSO)، بانتظر 10 دقايق وأرجع.")
            time.sleep(600)
            continue
        except RateLimit:
            time.sleep(90)
            seen.discard(name)
            continue
        except Unknown as e:
            # رد غريب من سوني: ما نعتبره متاح ولا مأخوذ، ننتظر ونعيد المحاولة
            seen.discard(name)
            if time.time() - last_report["t"] > 300:
                last_report["t"] = time.time()
                bot.send_message(chat_id, f"رد غريب من سوني، أنتظر شوي: {str(e)[:120]}")
            time.sleep(45)
            continue
        except Exception as e:
            seen.discard(name)
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
