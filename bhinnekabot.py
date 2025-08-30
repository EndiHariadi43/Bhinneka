# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Endi Hariadi
# 
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# bhinnekabot.py
# BhinnekaBot — Unity in Diversity 🤝

import asyncio
import os
import time
import secrets
import logging
from datetime import datetime, timedelta, timezone

import aiosqlite
import httpx
from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, BotCommand
)
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ChatMemberStatus, ParseMode
from dotenv import load_dotenv

# ---------- ENV & LOGGING ----------
load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("bhinnekabot")

BOT_TOKEN = os.getenv("BOT_TOKEN")
TON_DEST = os.getenv("TON_DEST_ADDRESS")  # alamat tujuan TON
TON_API = os.getenv("TONCENTER_API", "https://toncenter.com/api/v2")
TON_API_KEY = os.getenv("TONCENTER_API_KEY", "")
PREMIUM_PRICE_TON = float(os.getenv("PREMIUM_PRICE_TON", "1.0"))
PREMIUM_DAYS = int(os.getenv("PREMIUM_DAYS", "30"))

# ==== KOMUNITAS & GRUP ====
COMMUNITY_LINK = "https://t.me/bhinneka_coin"
X_LINK = "https://x.com/bhinneka_coin"
# Bisa username berawalan @ atau ID numerik; jika kosong, fitur verifikasi akan di-skip
COMMUNITY_CHAT_ID = os.getenv("COMMUNITY_CHAT_ID", "@bhinneka_coin")

if not BOT_TOKEN or not TON_DEST:
    raise RuntimeError("Set BOT_TOKEN & TON_DEST_ADDRESS di env/secrets")

bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
r = Router(name="bhinneka")

DB_PATH = "bhinneka.db"

WELCOME_TEXT = (
    "👋 <b>Selamat datang di Bhinneka (BHEK) Bot!</b>\n"
    "BHEK — Unity in Diversity, powered by memes & community.\n\n"
    "🔹 /tasks — lihat tugas/quest harian\n"
    "🔹 /premium — posisi istimewa (dukungan TON)\n"
    "🔹 /status — status akun kamu"
)

TASKS = [
    f'Join komunitas Telegram: <a href="{COMMUNITY_LINK}">@bhinneka_coin</a>',
    "Follow X (Twitter): <i>opsional</i>",
    "Retweet pinned post (X) & mention #BHEK",
]

# ---------- MAIN KEYBOARD ----------
MAIN_KB = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="👥 Join Telegram", url=COMMUNITY_LINK)],
        [InlineKeyboardButton(text="🐦 @Bhinneka_coin", url=X_LINK)],
    ]
)

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
                ref_by INTEGER,
                points INTEGER DEFAULT 0
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

            CREATE TABLE IF NOT EXISTS quests (
                user_id INTEGER,
                day TEXT,
                claimed_at INTEGER,
                PRIMARY KEY (user_id, day)
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
        await db.execute("UPDATE users SET premium_until=? WHERE user_id=?", (until, user_id))
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

# ---------- Quest helpers ----------
def _today_key_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d")

async def has_claimed_today(user_id: int) -> bool:
    day = _today_key_utc()
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT 1 FROM quests WHERE user_id=? AND day=?", (user_id, day))
        return await cur.fetchone() is not None

async def record_claim(user_id: int) -> bool:
    day = _today_key_utc()
    now = int(time.time())
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT INTO quests(user_id, day, claimed_at) VALUES (?,?,?)",
                (user_id, day, now),
            )
            await db.commit()
        return True
    except Exception:
        return False

async def add_points(user_id: int, amount: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET points = COALESCE(points,0) + ? WHERE user_id=?", (amount, user_id))
        await db.commit()

async def get_points(user_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT points FROM users WHERE user_id=?", (user_id,))
        row = await cur.fetchone()
        return row[0] if row and row[0] else 0

# ---------- TON Helpers ----------
def build_ton_deeplink(address: str, amount_ton: float, comment: str) -> str:
    from urllib.parse import quote
    amount_nano = int(amount_ton * 1_000_000_000)
    return f"ton://transfer/{address}?amount={amount_nano}&text={quote(comment)}"

def build_tgwallet_link(address: str, amount_ton: float, comment: str) -> str:
    from urllib.parse import quote
    return f"https://t.me/wallet/send/{address}?amount={amount_ton}&asset=TON&text={quote(comment)}"

def build_tonhub_link(address: str, amount_ton: float, comment: str) -> str:
    from urllib.parse import quote
    amount_nano = int(amount_ton * 1_000_000_000)
    return f"https://tonhub.com/transfer/{address}?amount={amount_nano}&text={quote(comment)}"

def build_tonviewer_address(address: str) -> str:
    return f"https://tonviewer.com/{address}"

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
            logger.exception("watcher error: %s", e)

        await asyncio.sleep(15)

# ---------- Keyboards ----------
def premium_keyboard(link_app: str, link_tonhub: str, link_tgwallet: str, link_explorer: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔗 Pay in TON (App)", url=link_app)],
            [InlineKeyboardButton(text="🌐 Pay via Web (Tonhub)", url=link_tonhub)],
            [InlineKeyboardButton(text="💳 Pay via Telegram Wallet", url=link_tgwallet)],
            [InlineKeyboardButton(text="👁️ Lihat alamat di Tonviewer", url=link_explorer)],
            [InlineKeyboardButton(text="✅ Saya sudah transfer", callback_data="check_payment")],
        ]
    )

# ---------- Handlers ----------
@r.message(CommandStart())
async def cmd_start(msg: Message):
    logger.info("START from uid=%s username=%s", msg.from_user.id, msg.from_user.username)
    await upsert_user(msg)
    await msg.answer(WELCOME_TEXT, reply_markup=MAIN_KB)
    logger.info("Sent /start reply to uid=%s", msg.from_user.id)

@r.message(Command("ping"))
async def cmd_ping(msg: Message):
    await msg.answer("🏓 Pong!")

@r.message(Command("tasks"))
async def cmd_tasks(msg: Message):
    lines = ["📋 <b>Quest Harian</b>"]
    lines.append(f'1) Join komunitas Telegram: <a href="{COMMUNITY_LINK}">@bhinneka_coin</a>')
    lines.append('2) Follow X (Twitter): <a href="https://x.com/bhinneka_coin">@Bhinneka_coin</a>')
    lines.append('3) Retweet pinned post (X) & mention <b>#BHEK</b>')
    lines.append("\nKetik <code>/claim</code> setelah selesai.")
    await msg.answer("\n".join(lines), reply_markup=MAIN_KB)

@r.message(Command("claim"))
async def cmd_claim(msg: Message):
    uid = msg.from_user.id
    try:
        # jika tidak dikonfigurasi, skip verifikasi join
        if COMMUNITY_CHAT_ID:
            member = await bot.get_chat_member(COMMUNITY_CHAT_ID, uid)
            status_ok = member.status in {
                ChatMemberStatus.MEMBER,
                ChatMemberStatus.ADMINISTRATOR,
                getattr(ChatMemberStatus, "CREATOR", ChatMemberStatus.ADMINISTRATOR),
                getattr(ChatMemberStatus, "OWNER", ChatMemberStatus.ADMINISTRATOR),
            }
            if not status_ok:
                await msg.answer(
                    "❌ Kamu belum terdeteksi di grup. Silakan join via tombol di /tasks.",
                    reply_markup=MAIN_KB
                )
                return

        if await has_claimed_today(uid):
            await msg.answer("ℹ️ Kamu sudah klaim quest hari ini. Datang lagi besok ya! ✨", reply_markup=MAIN_KB)
            return

        if await record_claim(uid):
            await add_points(uid, 10)
            pts = await get_points(uid)
            await msg.answer(
                f"✅ Klaim dicatat (+10 poin). Total poin: <b>{pts}</b>",
                reply_markup=MAIN_KB
            )
        else:
            await msg.answer("ℹ️ Terlihat kamu sudah klaim hari ini. Sampai jumpa besok! 👋", reply_markup=MAIN_KB)
    except Exception as e:
        logger.exception("verify/claim error: %s", e)
        await msg.answer("⚠️ Tidak bisa memverifikasi. Pastikan bot sudah ada di grup dan coba lagi.", reply_markup=MAIN_KB)

@r.message(Command("queststatus"))
async def cmd_queststatus(msg: Message):
    uid = msg.from_user.id
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT COUNT(*) FROM quests WHERE user_id=?", (uid,))
        total, = await cur.fetchone()
    today_done = await has_claimed_today(uid)
    txt = (
        "📊 <b>Status Quest</b>\n"
        f"• Total hari berhasil klaim: <b>{total}</b>\n"
        f"• Hari ini: {'✅ sudah' if today_done else '❌ belum'}"
    )
    await msg.answer(txt, reply_markup=MAIN_KB)

@r.message(Command("points"))
async def cmd_points(msg: Message):
    pts = await get_points(msg.from_user.id)
    await msg.answer(f"🏅 Total poin kamu: <b>{pts}</b>", reply_markup=MAIN_KB)

@r.message(Command("premium"))
async def cmd_premium(msg: Message):
    uid = msg.from_user.id
    code = f"BHEK-{uid}-{secrets.token_hex(2).upper()}"

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM orders WHERE user_id=? AND status='PENDING'", (uid,))
        await db.execute(
            "INSERT INTO orders(user_id, code, amount_ton, created_at) VALUES (?,?,?,?)",
            (uid, code, PREMIUM_PRICE_TON, int(time.time())),
        )
        await db.commit()

    link_app = build_ton_deeplink(TON_DEST, PREMIUM_PRICE_TON, code)
    link_web = build_tonhub_link(TON_DEST, PREMIUM_PRICE_TON, code)
    link_tgwallet = build_tgwallet_link(TON_DEST, PREMIUM_PRICE_TON, code)
    link_explorer = build_tonviewer_address(TON_DEST)

    text = (
        "🌟 <b>Premium / Posisi Istimewa</b>\n\n"
        f"Harga: <b>{PREMIUM_PRICE_TON} TON</b> untuk {PREMIUM_DAYS} hari.\n"
        f"Alamat: <code>{TON_DEST}</code>\n"
        f"Komentar (WAJIB): <code>{code}</code>\n\n"
        "1) Pilih salah satu: <b>Pay in TON (App)</b>, <b>Pay via Web (Tonhub)</b>, atau "
        "<b>Pay via Telegram Wallet</b>\n"
        "2) Pastikan <b>comment</b> PERSIS sama\n"
        "3) Setelah bayar, tekan <b>Saya sudah transfer</b>\n\n"
        "Bot akan memverifikasi on-chain dan mengaktifkan Premium ✅"
    )

    await msg.answer(text, reply_markup=premium_keyboard(link_app, link_web, link_tgwallet, link_explorer))

@r.callback_query(F.data == "check_payment")
async def cb_check_payment(cb: CallbackQuery):
    uid = cb.from_user.id
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT code, amount_ton, status FROM orders WHERE user_id=? ORDER BY id DESC LIMIT 5",
            (uid,),
        )
        rows = await cur.fetchall()

    status = await get_status(uid)
    if not rows:
        await cb.message.answer(status + "\n\nTidak ada pembayaran yang tertunda.", reply_markup=MAIN_KB)
        await cb.answer()
        return

    lines = [status, "", "🧾 <b>Riwayat Pembayaran</b> (terakhir):"]
    for code, amt, st in rows:
        lines.append(f"• {st}: {amt} TON | comment: <code>{code}</code>")
    lines.append("\n⏳ Jika baru transfer, tunggu 1–2 menit lalu klik lagi.")
    await cb.message.answer("\n".join(lines), reply_markup=MAIN_KB)
    await cb.answer()

@r.message(Command("status"))
async def cmd_status(msg: Message):
    await upsert_user(msg)
    s = await get_status(msg.from_user.id)
    await msg.answer(s, reply_markup=MAIN_KB)

@r.message(Command("help"))
async def cmd_help(msg: Message):
    await msg.answer(
        "📖 <b>Command List</b>\n\n"
        "/start — Welcome & menu\n"
        "/tasks — Quest harian\n"
        "/claim — Klaim quest\n"
        "/queststatus — Lihat progres quest\n"
        "/points — Lihat total poin\n"
        "/premium — Beli Premium via TON\n"
        "/status — Cek status Premium\n"
        "/ping — Tes respons bot\n"
        "/help — Panduan semua command",
        reply_markup=MAIN_KB
    )

# Fallback untuk command yang tidak dikenal (opsional tapi membantu debug)
@r.message(F.text.regexp(r"^/"))
async def unknown_command(msg: Message):
    await msg.answer("❓ Perintah tidak dikenali. Coba /help.", reply_markup=MAIN_KB)

# ---------- Error logging ----------
@dp.errors()
async def on_error(event, exception):
    logger.exception("Unhandled error: %s | Update=%s", exception, getattr(event, "update", None))

# ---------- Main ----------
async def main():
    logger.info("Bot booting...")
    await init_db()

    # pastikan polling, tidak tertahan webhook lama
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("Webhook deleted (drop_pending_updates=True).")
    except Exception as e:
        logger.warning("delete_webhook failed: %s", e)

    # set menu commands
    await bot.set_my_commands([
        BotCommand(command="start", description="Welcome + menu"),
        BotCommand(command="tasks", description="Quest harian"),
        BotCommand(command="claim", description="Klaim quest"),
        BotCommand(command="queststatus", description="Lihat progres quest"),
        BotCommand(command="points", description="Lihat total poin"),
        BotCommand(command="premium", description="Beli Premium via TON"),
        BotCommand(command="status", description="Cek status Premium"),
        BotCommand(command="ping", description="Tes respons bot"),
        BotCommand(command="help", description="Panduan"),
    ])

    # daftarkan router
    dp.include_router(r)

    # jalankan watcher verifikasi premium
    asyncio.create_task(premium_watcher())

    logger.info("🚀 BhinnekaBot is polling for updates…")
    await dp.start_polling(bot, allowed_updates=None)  # None = semua

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped")
