import os, time, random, string, threading, base64, html
from urllib.parse import urlparse, parse_qs
from http.server import BaseHTTPRequestHandler, HTTPServer
import requests

BOT_TOKEN = os.environ["BOT_TOKEN"]
NPSSO = os.environ["NPSSO"]
OWNER_ID = int(os.environ.get("OWNER_ID", "0"))
TG = f"https://api.telegram.org/bot{BOT_TOKEN}"
CID = "09515159-7237-4370-9b40-3806e67c0891"
BASIC = base64.b64encode(f"{CID}:ucPjka5tntB2KqsP".encode()).decode()
REDIRECT = "com.scee.psxandroid.scecompcall://redirect"
SCOPE = "psn:mobile.v2.core psn:clientapp"
DELAY = 5  # ثواني بين كل تجربة
LINE = "━━━━━━━━━━━━━━"

token = {"v": None, "exp": 0}
state = {"run": False, "mode": 0}
tried = set()
stats = {"n": 0, "found": 0, "last": "", "code": 0, "start": 0}

HELP = (
    "🎮 <b>بوت يوزرات PlayStation</b>\n"
    f"{LINE}\n"
    "🔹 /start4 ـ بحث الرباعي (٣ حروف + شخطة)\n"
    "🔹 /start5 ـ بحث الخماسي (٤ حروف + شخطة)\n"
    "🔹 /status ـ حالة البحث\n"
    "🔹 /stop ـ إيقاف البحث\n"
    "🔹 /test اسم ـ فحص يوزر واحد\n"
    f"{LINE}\n"
    "💡 البوت يرسل لك فقط اليوزرات المتاحة."
)


def send(chat, text):
    requests.post(f"{TG}/sendMessage",
                  json={"chat_id": chat, "text": text, "parse_mode": "HTML"})


def fmt_time(sec):
    sec = int(sec)
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h} ساعة و {m} دقيقة"
    if m:
        return f"{m} دقيقة و {s} ثانية"
    return f"{s} ثانية"


def get_token():
    if token["v"] and time.time() < token["exp"]:
        return token["v"]
    r = requests.get(
        "https://ca.account.sony.com/api/authz/v3/oauth/authorize",
        params={"access_type": "offline", "client_id": CID,
                "response_type": "code", "scope": SCOPE,
                "redirect_uri": REDIRECT},
        headers={"Cookie": f"npsso={NPSSO}"}, allow_redirects=False)
    code = parse_qs(urlparse(r.headers.get("Location", "")).query).get("code")
    if not code:
        raise Exception("الـ NPSSO ما اشتغل (غلط أو منتهي الصلاحية)")
    r = requests.post(
        "https://ca.account.sony.com/api/authz/v3/oauth/token",
        headers={"Authorization": f"Basic {BASIC}"},
        data={"code": code[0], "redirect_uri": REDIRECT,
