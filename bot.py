import os, time, random, string, threading, base64
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

token = {"v": None, "exp": 0}
state = {"run": False}
tried = set()

def send(chat, text):
    requests.post(f"{TG}/sendMessage", json={"chat_id": chat, "text": text})

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
        raise Exception("الـ NPSSO ما اشتغل (غلط أو منتهي)")
    r = requests.post(
        "https://ca.account.sony.com/api/authz/v3/oauth/token",
        headers={"Authorization": f"Basic {BASIC}"},
        data={"code": code[0], "redirect_uri": REDIRECT,
              "grant_type": "authorization_code",
              "token_format": "jwt", "scope": SCOPE})
    token["v"] = r.json()["access_token"]
    token["exp"] = time.time() + 3000
    return token["v"]

def check(name):
    r = requests.post(
        "https://accounts.api.playstation.com/api/v1/accounts/onlineIds",
        headers={"Authorization": f"Bearer {get_token()}"},
        json={"onlineId": name, "reserveIfAvailable": False})
    return r.status_code, r.text[:300]

def available(status, text):
    # قاعدة مؤقتة، نعدلها بعد ما نشوف نتيجة /test
    return status in (200, 204)

def make(n):
    letters = [random.choice(string.ascii_lowercase) for _ in range(n)]
    letters.insert(random.randint(1, n), random.choice("_-"))
    return "".join(letters)

def search(chat, n):
    state["run"] = True
    send(chat, f"بديت البحث ({n+1} خانات)")
    while state["run"]:
        name = make(n)
        if name in tried:
            continue
        try:
            status, text = check(name)
        except Exception as e:
            send(chat, f"خطأ: {e}")
            time.sleep(60)
            continue
        if status == 429:
            time.sleep(120)
            continue
        if status == 401:
            token["exp"] = 0
            continue
        tried.add(name)
        if available(status, text):
            send(chat, f"✅ {name}")
        time.sleep(DELAY)
    send(chat, "وقفت البحث")

def handle(m):
    chat = m["chat"]["id"]
    text = m.get("text", "")
    if text == "/id":
        return send(chat, f"رقمك: {chat}")
    if chat != OWNER_ID:
        return
    if text.startswith("/test"):
        parts = text.split()
        if len(parts) < 2:
            return send(chat, "اكتب: /test اسم")
        try:
            s, t = check(parts[1])
            send(chat, f"{s}\n{t}")
        except Exception as e:
            send(chat, f"خطأ: {e}")
    elif text == "/start4" and not state["run"]:
        threading.Thread(target=search, args=(chat, 3), daemon=True).start()
    elif text == "/start5" and not state["run"]:
        threading.Thread(target=search, args=(chat, 4), daemon=True).start()
    elif text == "/stop":
        state["run"] = False

class H(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.end_headers(); self.wfile.write(b"ok")

threading.Thread(
    target=lambda: HTTPServer(("0.0.0.0", int(os.environ.get("PORT", 10000))), H).serve_forever(),
    daemon=True).start()

offset = 0
while True:
    try:
        r = requests.get(f"{TG}/getUpdates", params={"offset": offset, "timeout": 30}, timeout=40).json()
        for u in r.get("result", []):
            offset = u["update_id"] + 1
            if "message" in u:
                handle(u["message"])
    except Exception:
        time.sleep(5)
