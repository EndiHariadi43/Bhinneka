# bhinnekabot.py
# BhinnekaBot — Unity in Diversity 🤝
# Fitur: welcome + quest, premium via TON dengan verifikasi komentar unik on-chain.

import asyncio
import os
import time
import secrets
import logging
from datetime import datetime, timedelta, timezone

import aiosqlite
import httpx
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, BotCommand
from dotenv import load_dotenv

# ---------- ENV & LOGGING ----------
load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("bhinnekabot")

BOT_TOKEN = os.getenv("BOT_TOKEN")
TON_DEST = os.getenv("TON_DEST_ADDRESS")                      # alamat tujuan TON
TON_API = os.getenv("TONCENTER_API", "https://toncenter.com/api/v2")
TON_API_KEY = os.getenv("TONCENTER_API_KEY", "")
PREMIUM_PRICE_TON = float(os.getenv("PREMIUM_PRICE_TON", "1.0"))
PREMIUM_DAYS = int(os.getenv("PREMIUM_DAYS", "30"))

assert BOT_TOKEN and TON_DEST, "Set BOT_TOKEN & TON_DEST_ADDRESS di env/secrets"

bot = Bot(BOT_TOKEN, parse_mode="HTML")
dp = Dispatcher()

DB_PATH = "bhinneka.db"

WELCOME_TEXT = (
    "👋 <b>Selamat datang di Bhinneka (BHEK) Bot!</b>\n"
    "BHEK — Unity in Diversity, powered by memes & community.\n\n"
    "🔹 /tasks — lihat tugas/quest harian\n"
    "🔹 /premium — posisi istimewa (dukungan TON)\n"
    "🔹 /status — status akun kamu"
)

TASKS = [
    "Join komunitas Telegram: t.me/bhinneka_coin",
    "Follow X: @bhinneka_coin",
    "Retweet pinned post (X) & mention #BHEK",
]

# ---------- DB ----------
async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                joined_at INTEGER,
                premium_until INTEGER DEFAULT 0,
                ref_by INTEGER
            );

            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                code TEXT UNIQUE,
                amount_ton REAL,
                created_at INTEGER,
                confirmed_at INTEGER DEFAULT 0,
                status TEXT DEFAULT 'PENDING'
            );

            CREATE INDEX IF NOT EXISTS idx_orders_code ON orders(code);
            CREATE INDEX IF NOT EXISTS idx_orders_user ON orders(user_id);
            """
        )
        await db.commit()

async def upsert_user(msg: Message, ref_by: int | None = None):
    uid = msg.from_user.id
    username = msg.from_user.username or ""
    fname = msg.from_user.first_name or ""
    now = int(time.time())
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT user_id FROM users WHERE user_id=?", (uid,))
        row = await cur.fetchone()
        if row:
            await db.execute(
                "UPDATE users SET username=?, first_name=? WHERE user_id=?",
                (username, fname, uid),
            )
        else:
            await db.execute(
                "INSERT INTO users(user_id, username, first_name, joined_at, ref_by) VALUES (?,?,?,?,?)",
                (uid, username, fname, now, ref_by),
            )
        await db.commit()

async def set_premium(user_id: int, days: int):
    until = int((datetime.now(timezone.utc) + timedelta(days=days)).timestamp())
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET premium_until=? WHERE user_id=?",
            (until, user_id),
        )
        await db.commit()

async def get_status(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT premium_until FROM users WHERE user_id=?", (user_id,))
        row = await cur.fetchone()
        if not row:
            return "❌ Belum terdaftar."
        until = row[0] or 0
        now = int(time.time())
        if until > now:
            exp = datetime.fromtimestamp(until, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
            return f"🌟 Premium aktif hingga <b>{exp}</b>."
        return "🟢 Akun terdaftar. Premium: <b>Tidak aktif</b>."

# ---------- TON Helpers ----------
def build_ton_deeplink(address: str, amount_ton: float, comment: str) -> str:
    amount_nano = int(amount_ton * 1_000_000_000)  # 1 TON = 1e9 nanoTON
    from urllib.parse import quote
    return f"ton://transfer/{address}?amount={amount_nano}&text={quote(comment)}"

async def ton_get_transactions(address: str, limit: int = 20):
    params = {"address": address, "limit": limit}
    headers = {}
    if TON_API_KEY:
        headers["X-API-Key"] = TON_API_KEY
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.get(f"{TON_API}/getTransactions", params=params, headers=headers)
        r.raise_for_status()
        return r.json()

def extract_comment(tx: dict) -> str | None:
    try:
        msg = tx.get("in_msg") or {}
        return msg.get("message")
    except Exception:
        return None

def extract_amount_ton(tx: dict) -> float:
    try:
        msg = tx.get("in_msg") or {}
        val = int(msg.get("value", "0"))
        return val / 1_000_000_000
    except Exception:
        return 0.0

def matches_destination(tx: dict, addr: str) -> bool:
    try:
        dest = (tx.get("in_msg") or {}).get("destination", "")
        return dest == addr
    except Exception:
        return False

# ---------- Background Verifier ----------
async def premium_watcher():
    await asyncio.sleep(3)
    while True:
        try:
            # Tandai order PENDING yang kadaluarsa (>24 jam) sebagai EXPIRED
            now_ts = int(time.time())
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute(
                    "UPDATE orders SET status='EXPIRED' WHERE status='PENDING' AND created_at < ?",
                    (now_ts - 24 * 3600,),
                )
                await db.commit()

                cur = await db.execute(
                    "SELECT id, user_id, code, amount_ton FROM orders WHERE status='PENDING' ORDER BY id ASC"
                )
                orders = await cur.fetchall()

            if not orders:
                await asyncio.sleep(12)
                continue

            tx_data = await ton_get_transactions(TON_DEST, limit=40)
            txs = tx_data.get("result", []) if isinstance(tx_data, dict) else []

            if not txs:
                await asyncio.sleep(12)
                continue

            found_updates = []
            for oid, uid, code, amt in orders:
                for tx in txs:
                    if not matches_destination(tx, TON_DEST):
                        continue
                    comment = extract_comment(tx) or ""
                    value_ton = extract_amount_ton(tx)
                    if comment.strip() == code and (value_ton + 1e-9) >= float(amt):
                        found_updates.append((oid, uid))

            if found_updates:
                async with aiosqlite.connect(DB_PATH) as db:
                    for oid, uid in found_updates:
                        now = int(time.time())
                        await db.execute(
                            "UPDATE orders SET status='CONFIRMED', confirmed_at=? WHERE id=?",
                            (now, oid),
                        )
                        await db.commit()
                        await set_premium(uid, PREMIUM_DAYS)
                        logger.info("Premium confirmed uid=%s order_id=%s", uid, oid)
                        try:
                            await bot.send_message(
                                uid,
                                f"✅ <b>Pembayaran Premium diterima.</b>\n"
                                f"Terima kasih! Status Premium aktif {PREMIUM_DAYS} hari 🎉",
                            )
                        except Exception:
                            pass

        except httpx.HTTPError as e:
            logger.warning("TON API error: %s", e)
        except Exception as e:
            logger.exception("watcher error: %s
