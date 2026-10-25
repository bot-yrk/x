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
    send(chat,
         "🚀 <b>بدأ البحث</b>\n" + LINE + "\n"
         f"🎯 النوع: <b>{kind}</b> ({n + 1} خانات)\n"
         f"⏱ سرعة الفحص: يوزر كل {DELAY} ثواني\n"
         + LINE + "\n"
         "📩 بوصلك إشعار أول ما ألقى يوزر متاح.\n"
         "📊 /status للحالة  |  🛑 /stop للإيقاف")
    while state["run"]:
        name = make(n)
        if name in tried:
            continue
        try:
            status, text = check(name)
        except Exception as e:
            send(chat, "⚠️ <b>صار خطأ</b>\n" + html.escape(str(e))
                 + "\n🔄 بعيد المحاولة بعد دقيقة.")
            time.sleep(60)
            continue
        if status == 429:
            stats["code"] = 429
            send(chat, "⏳ <b>Sony طلبت إبطاء الفحص</b>\n"
                       "بوقف دقيقتين وبكمل تلقائياً.")
            time.sleep(120)
            continue
        if status == 403:
            stats["code"] = 403
            send(chat, "🚫 <b>Sony رفضت الطلب (403)</b>\n"
                 + html.escape(text[:200])
                 + "\n⏳ بوقف 5 دقايق وأعيد المحاولة.")
            token["exp"] = 0
            time.sleep(300)
            continue
        if status == 401:
            token["exp"] = 0
            continue
        tried.add(name)
        stats["n"] += 1
        stats["last"] = name
        stats["code"] = status
        if available(status, text):
            stats["found"] += 1
            elapsed = fmt_time(time.time() - stats["start"])
            send(chat,
                 "✅ <b>يوزر متاح!</b>\n" + LINE + "\n"
                 f"👤 <code>{html.escape(name)}</code>\n"
                 f"🔢 التجربة رقم: {stats['n']}\n"
                 f"⏱ بعد: {elapsed}\n"
                 + LINE + "\n"
                 "⚡ بادر بحجزه قبل لا ينسرق!")
        time.sleep(DELAY)
    send(chat,
         "🛑 <b>تم إيقاف البحث</b>\n" + LINE + "\n"
         f"🔎 اليوزرات اللي انفحصت: {stats['n']}\n"
         f"✅ المتاحة: {stats['found']}")


def status_text():
    if state["run"]:
        kind = "رباعي" if state["mode"] == 4 else "خماسي"
        elapsed = time.time() - stats["start"]
        rate = int(stats["n"] / elapsed * 3600) if elapsed > 0 else 0
        code = stats["code"]
        if code in (200, 201, 400):
            health = "سليم ✅"
        else:
            health = f"تنبيه ⚠️ ({code})"
        last = html.escape(stats["last"] or "-")
        return (
            "📊 <b>حالة البحث</b>\n" + LINE + "\n"
            f"🟢 الحالة: شغال ({kind})\n"
            f"⏱ مدة التشغيل: {fmt_time(elapsed)}\n"
            f"🔎 المفحوص: {stats['n']} يوزر\n"
            f"✅ المتاح: {stats['found']}\n"
            f"⚡ السرعة: حوالي {rate} يوزر بالساعة\n"
            f"👤 آخر يوزر: <code>{last}</code>\n"
            f"📡 اتصال Sony: {health}"
        )
    return (
        "📊 <b>حالة البحث</b>\n" + LINE + "\n"
        "🔴 الحالة: متوقف\n"
        f"🔎 آخر جلسة: {stats['n']} يوزر | ✅ {stats['found']} متاح\n"
        + LINE + "\n"
        "▶️ ابدأ بـ /start4 أو /start5"
    )


def handle(m):
    chat = m["chat"]["id"]
    text = m.get("text", "")
    if text == "/id":
        return send(chat, f"🆔 رقمك: <code>{chat}</code>")
    if chat != OWNER_ID:
        return send(chat, "⛔ هذا البوت خاص بالمالك فقط.")
    if text in ("/start", "/help"):
        send(chat, HELP)
    elif text.startswith("/test"):
        parts = text.split()
        if len(parts) < 2:
            return send(chat, "ℹ️ الاستخدام: <code>/test اسم</code>")
        name = parts[1]
        try:
            s, t = check(name)
        except Exception as e:
            return send(chat, "⚠️ <b>خطأ</b>\n" + html.escape(str(e)))
        if available(s, t):
            result = "✅ متاح"
        elif s == 400:
            result = "❌ مأخوذ أو غير صالح"
        else:
            result = f"⚠️ رد غير متوقع ({s})"
        send(chat,
             "🧪 <b>نتيجة الفحص</b>\n" + LINE + "\n"
             f"👤 <code>{html.escape(name)}</code>\n"
             f"📌 {result}")
    elif text in ("/start4", "/start5"):
        if state["run"]:
            return send(chat, "⚠️ البحث شغال حالياً.\nاستخدم /stop لإيقافه أول.")
        n = 3 if text == "/start4" else 4
        threading.Thread(target=search, args=(chat, n), daemon=True).start()
    elif text == "/status":
        send(chat, status_text())
    elif text == "/stop":
        if state["run"]:
            state["run"] = False
        else:
            send(chat, "ℹ️ ما فيه بحث شغال الحين.")


class H(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, *a):
        pass


def run_server():
    port = int(os.environ.get("PORT", 10000))
    HTTPServer(("0.0.0.0", port), H).serve_forever()


threading.Thread(target=run_server, daemon=True).start()

offset = 0
while True:
    try:
        r = requests.get(TG + "/getUpdates",
                         params={"offset": offset, "timeout": 30},
                         timeout=40).json()
        for u in r.get("result", []):
            offset = u["update_id"] + 1
            if "message" in u:
                handle(u["message"])
    except Exception:
        time.sleep(5)
