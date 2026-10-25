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
DELAY = 5
LINE = "━━━━━━━━━━━━━━"

token = {"v": None, "exp": 0}
state = {"run": False, "mode": 0}
tried = set()
stats = {"n": 0, "found": 0, "last": "", "code": 0, "start": 0}

HELP = (
    "🎮 <b>بوت يوزرات PlayStation</b>\n"
    + LINE + "\n"
    "🔹 /start4 ـ بحث الرباعي (٣ حروف + شخطة)\n"
    "🔹 /start5 ـ بحث الخماسي (٤ حروف + شخطة)\n"
    "🔹 /status ـ حالة البحث\n"
    "🔹 /stop ـ إيقاف البحث\n"
    "🔹 /test اسم ـ فحص يوزر واحد\n"
    + LINE + "\n"
    "💡 البوت يرسل لك فقط اليوزرات المتاحة."
)


def send(chat, text):
    requests.post(TG + "/sendMessage",
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
    params = {
        "access_type": "offline",
        "client_id": CID,
        "response_type": "code",
        "scope": SCOPE,
        "redirect_uri": REDIRECT,
    }
    r = requests.get(
        "https://ca.account.sony.com/api/authz/v3/oauth/authorize",
        params=params,
        headers={"Cookie": "npsso=" + NPSSO},
        allow_redirects=False)
    loc = r.headers.get("Location", "")
    code = parse_qs(urlparse(loc).query).get("code")
    if not code:
        raise Exception("الـ NPSSO ما اشتغل (غلط أو منتهي الصلاحية)")
    body = {
        "code": code[0],
        "redirect_uri": REDIRECT,
        "grant_type": "authorization_code",
        "token_format": "jwt",
        "scope": SCOPE,
    }
    r = requests.post(
        "https://ca.account.sony.com/api/authz/v3/oauth/token",
        headers={"Authorization": "Basic " + BASIC},
        data=body)
    token["v"] = r.json()["access_token"]
    token["exp"] = time.time() + 3000
    return token["v"]


def check(name):
    headers = {
        "Authorization": "Bearer " + get_token(),
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0",
    }
    payload = {"onlineId": name, "reserveIfAvailable": False}
    r = requests.post(
        "https://accounts.api.playstation.com/api/v1/accounts/onlineIds",
        headers=headers, json=payload, timeout=20)
    return r.status_code, r.text[:300]


def available(status, text):
    return 200 <= status < 300 and "validationErrors" not in text


def make(n):
    letters = [random.choice(string.ascii_lowercase) for _ in range(n)]
    letters.insert(random.randint(1, n), random.choice("_-"))
    return "".join(letters)


def search(chat, n):
    state["run"] = True
    state["mode"] = n + 1
    stats["n"] = 0
    stats["found"] = 0
    stats["last"] = ""
    stats["code"] = 0
    stats["start"] = time.time()
    kind = "رباعي" if n == 3 else "خماسي"
    send(ch
