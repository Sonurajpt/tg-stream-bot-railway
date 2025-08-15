import os
import threading
import socket
import requests
from flask import Flask, request, Response, redirect, abort
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, MessageHandler, CommandHandler, filters, ContextTypes
from dotenv import load_dotenv

# --------- Config ---------
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")                       # set on Railway
BASE_URL_PATH = os.getenv("BASE_URL_PATH", "media")
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8080"))
PUBLIC_BASE = os.getenv("PUBLIC_BASE", "").strip().rstrip("/")  # set to Railway domain after first deploy

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN not found in environment")

API_BASE = "https://api.telegram.org"
BOT_API = f"{API_BASE}/bot{BOT_TOKEN}"
FILE_API = f"{API_BASE}/file/bot{BOT_TOKEN}"

app = Flask(__name__)

# --------- Helpers ---------
def base_url() -> str:
    """PUBLIC_BASE (recommended) -> request.host_url -> local ip"""
    if PUBLIC_BASE:
        return PUBLIC_BASE
    if request:
        return request.host_url.rstrip("/")
    try:
        local_ip = socket.gethostbyname(socket.gethostname())
    except Exception:
        local_ip = "127.0.0.1"
    return f"http://{local_ip}:{PORT}"

def get_cdn_url(file_id: str) -> str | None:
    try:
        r = requests.get(f"{BOT_API}/getFile", params={"file_id": file_id}, timeout=30)
        r.raise_for_status()
        js = r.json()
        if not js.get("ok"):
            return None
        file_path = js["result"]["file_path"]
        return f"{FILE_API}/{file_path}"
    except requests.RequestException:
        return None

# --------- HTTP Endpoints ---------
@app.route("/health")
def health():
    return "ok"

@app.route(f"/{BASE_URL_PATH}/d/<file_id>")
def direct_download(file_id):
    cdn = get_cdn_url(file_id)
    if not cdn:
        return abort(404, "Invalid file_id")
    return redirect(cdn, code=302)

@app.route(f"/{BASE_URL_PATH}/s/<file_id>")
def stream_proxy(file_id):
    cdn = get_cdn_url(file_id)
    if not cdn:
        return abort(404, "Invalid file_id")
    headers = {}
    if "Range" in request.headers:
        headers["Range"] = request.headers["Range"]
    try:
        upstream = requests.get(cdn, headers=headers, stream=True, timeout=30)
    except requests.RequestException:
        return abort(502, "Upstream error")

    excluded = {"transfer-encoding","connection","keep-alive","proxy-authenticate",
                "proxy-authorization","te","trailer","upgrade"}
    resp_headers = [(k, v) for k, v in upstream.headers.items() if k.lower() not in excluded]

    def generate():
        for chunk in upstream.iter_content(chunk_size=1024 * 64):
            if chunk:
                yield chunk

    return Response(generate(), status=upstream.status_code, headers=resp_headers)

# --------- Telegram Handlers ---------
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    b = base_url()
    keyboard = [
        [InlineKeyboardButton("✅ Health", url=f"{b}/health")],
    ]
    await update.message.reply_text(
        "👋 *Welcome!* Send a video/file/audio/photo and I’ll return public links.\n"
        "You’ll get:\n"
        "• Direct Download (redirect to Telegram CDN)\n"
        "• Stream Link (Range pass-through)\n",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )

def extract_file_id(msg) -> tuple[str | None, str]:
    if msg.document:
        return msg.document.file_id, msg.document.file_name or "Document"
    if msg.video:
        return msg.video.file_id, "Video"
    if msg.audio:
        return msg.audio.file_id, msg.audio.file_name or "Audio"
    if msg.voice:
        return msg.voice.file_id, "Voice"
    if msg.photo:
        return msg.photo[-1].file_id, "Photo"
    return None, ""

async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    file_id, label = extract_file_id(msg)
    if not file_id:
        await msg.reply_text("Send a file/video/audio/photo.")
        return

    b = base_url()
    direct_redirect = f"{b}/{BASE_URL_PATH}/d/{file_id}"
    stream_link = f"{b}/{BASE_URL_PATH}/s/{file_id}"
    cdn = get_cdn_url(file_id)

    text = (
        f"**{label}**\n"
        f"• Direct: `{direct_redirect}`\n"
        f"• Stream: `{stream_link}`\n"
    )
    if cdn:
        text += f"• Raw CDN: `{cdn}`\n"
    text += "_Note: Seeking depends on CDN & player._"

    # Buttons for convenience
    kb = [[InlineKeyboardButton("📥 Download", url=direct_redirect)],
          [InlineKeyboardButton("▶️ Stream", url=stream_link)]]
    await msg.reply_markdown(text, reply_markup=InlineKeyboardMarkup(kb))

# --------- Run ---------
def run_flask():
    app.run(host=HOST, port=PORT, threaded=True)

def main():
    threading.Thread(target=run_flask, daemon=True).start()
    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .connect_timeout(30)
        .read_timeout(30)
        .build()
    )
    application.add_handler(CommandHandler("start", start_cmd))
    application.add_handler(MessageHandler(filters.ALL, handle_file))
    application.run_polling(close_loop=False)

if __name__ == "__main__":
    main()
