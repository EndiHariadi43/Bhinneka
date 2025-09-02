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
import re
import time
import secrets
import logging
from datetime import datetime, timedelta, timezone
from typing import Iterable, Optional

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

def _to_bool(s: Optional[str]) -> bool:
    return str(s).strip().lower() in {"1", "true", "yes", "y", "on"}

def _parse_admins(s: Optional[str]) -> set[int]:
    # ADMINS boleh "6993912434" atau "6993912434, 12345"
    if not s:
        return set()
    parts = re.split(r"[,\s]+", s.strip())
    out = set()
    for p in parts:
        if p.isdigit():
            try:
                out.add(int(p))
            except Exception:
                pass
    return out

# OFFICIAL MODE (opsional)
OFFICIAL_ONLY = _to_bool(os.getenv("OFFICIAL_ONLY", "0"))
OFFICIAL_TON_ADDRESS = os.getenv(
    "OFFICIAL_TON_ADDRESS",
    "UQDwWm6EWph_L4suX5o7tC4KQZYr3rTN_rWiuP7gd8U3AMC5",
)

# ADMINS dari env (repo secrets)
ADMINS: set[int] = _parse_admins(os.getenv("ADMINS", ""))

BOT_TOKEN = os.getenv("BOT_TOKEN")
TON_DEST = os.getenv("TON_DEST_ADDRESS")
TON_API = os.getenv("TONCENTER_API", "https://toncenter.com/api/v2")
TON_API_KEY = os.getenv("TONCENTER_API_KEY", "")
PREMIUM_PRICE_TON = float(os.getenv("PREMIUM_PRICE_TON", "1.0"))
PREMIUM_DAYS = int(os.getenv("PREMIUM_DAYS", "30"))

# Terapkan OFFICIAL_ONLY sekali saat boot
if OFFICIAL_ONLY:
    if TON_DEST and TON_DEST != OFFICIAL_TON_ADDRESS:
        logger.warning("OFFICIAL_ONLY=ON — overriding TON_DEST to OFFICIAL_TON_ADDRESS")
    TON_DEST = OFFICIAL_TON_ADDRESS
    logger.info("Running in OFFICIAL mode. TON_DEST set to OFFICIAL_TON_ADDRESS.")

# Validasi env minimal
if not BOT_TOKEN:
    raise RuntimeError("Set BOT_TOKEN di env/secrets")
if not TON_DEST:
    raise RuntimeError("TON_DEST_ADDRESS kosong (atau set OFFICIAL_TON_ADDRESS jika OFFICIAL_ONLY=1)")

# ==== KOMUNITAS & GRUP ====
COMMUNITY_LINK = "https://t.me/bhinneka_coin"
X_LINK = "https://x.com/bhinneka_coin"
COMMUNITY_CHAT_ID = os.getenv("COMMUNITY_CHAT_ID", "@bhinneka_coin")

bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
r = Router(name="bhinneka")

DB_PATH = "bhinneka.db"

WELCOME_TEXT = (
    "👋 <b>Selamat datang di Bhinneka (BHEK) Bot!</b>\n"
    "BHEK — Unity in Diversity, powered by memes & community.\n\n"
    "🔹 /tasks — lihat tugas/quest harian\n"
    "🔹 /premium — posisi istimewa (dukungan TON)\n"
    "🔹 /status — status akun kamu\n"
    "🔹 /points — total poin kamu\n"
    "🔹 /leaderboard — papan peringkat komunitas"
)

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
            PRAGMA journal_mode=WAL;

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

            -- Quest harian (UTC)
            CREATE TABLE IF NOT EXISTS quests (
                user_id INTEGER,
                day TEXT,               -- YYYYMMDD (UTC)
                claimed_at INTEGER,     -- epoch seconds UTC
                PRIMARY KEY (user_id, day)
            );

            -- Log poin (audit)
            CREATE TABLE IF NOT EXISTS points_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                delta INTEGER,
                reason TEXT,
                by_admin INTEGER DEFAULT 0,
                created_at INTEGER
            );

            CREATE INDEX IF NOT EXISTS idx_orders_code ON orders(code);
            CREATE INDEX IF NOT EXISTS idx_orders_user ON orders(user_id);
            CREATE INDEX IF NOT EXISTS idx_points_user ON points_log(user_id);
            """
        )
        await db.commit()

async def upsert_user(msg: Message, ref_by: Optional[int] = None):
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

async def get_status(user_id: int) -> str:
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

# ---------- Quest & Points helpers ----------
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
        return False  # primary key conflict => sudah klaim

async def add_points(user_id: int, amount: int, reason: str = "", by_admin: bool = False):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET points = COALESCE(points,0) + ? WHERE user_id=?", (amount, user_id))
        await db.execute(
            "INSERT INTO points_log(user_id, delta, reason, by_admin, created_at) VALUES (?,?,?,?,?)",
            (user_id, amount, reason[:200], 1 if by_admin else 0, int(time.time())),
        )
        await db.commit()

async def get_points(user_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT points FROM users WHERE user_id=?", (user_id,))
        row = await cur.fetchone()
        return int(row[0]) if row and row[0] else 0

async def top_points(limit: int = 10) -> list[tuple[int, str, int]]:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT user_id, COALESCE(username,''), COALESCE(points,0) "
            "FROM users ORDER BY points DESC, user_id ASC LIMIT ?",
            (limit,),
        )
        return await cur.fetchall()

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

def extract_comment(tx: dict) -> Optional[str]:
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

# ---------- Helpers ----------
def _is_admin(uid: int) -> bool:
    return uid in ADMINS

async def _resolve_user_id(arg: str) -> Optional[int]:
    # arg: "12345" atau "@username"
    arg = arg.strip()
    if arg.startswith("@"):
        # Tidak ada API direct untuk resolve username → minta user /start supaya terdaftar,
        # atau admin beri ID numerik. (Sederhana & aman)
        return None
    if arg.isdigit():
        return int(arg)
    return None

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
            await add_points(uid, 10, reason="daily_claim", by_admin=False)
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

@r.message(Command("leaderboard"))
async def cmd_leaderboard(msg: Message):
    rows = await top_points(limit=10)
    if not rows:
        await msg.answer("📉 Belum ada data poin.")
        return
    lines = ["🏆 <b>Leaderboard Top 10</b>"]
    rank = 1
    for uid, uname, pts in rows:
        tag = f"@{uname}" if uname else f"<code>{uid}</code>"
        lines.append(f"{rank}. {tag} — <b>{pts}</b> pts")
        rank += 1
    await msg.answer("\n".join(lines))

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
        "/claim — Klaim harian (+10 poin)\n"
        "/queststatus — Progres klaim\n"
        "/points — Total poin\n"
        "/leaderboard — Papan peringkat Top 10\n"
        "/premium — Beli Premium via TON\n"
        "/status — Cek status Premium\n"
        "/ping — Tes respons bot\n"
        "/help — Panduan\n\n"
        "<i>Admin</i>: /give &lt;user_id&gt; &lt;amount&gt; [reason]",
        reply_markup=MAIN_KB
    )

@r.message(Command("broadcast"))
async def cmd_broadcast(msg: Message):
    """Kirim pesan ke semua user terdaftar (khusus admin). 
    Pakai: /broadcast <teks>  atau balas sebuah pesan lalu ketik /broadcast"""
    if not _is_admin(msg.from_user.id):
        await msg.answer("⛔ Perintah khusus admin.")
        return

    # Ambil teks dari argumen atau dari pesan yang di-reply
    args_text = (msg.text or "").split(maxsplit=1)
    text = ""
    if len(args_text) >= 2:
        text = args_text[1].strip()
    elif msg.reply_to_message and (msg.reply_to_message.text or msg.reply_to_message.caption):
        text = (msg.reply_to_message.text or msg.reply_to_message.caption).strip()

    if not text:
        await msg.answer(
            "Usage:\n"
            "<code>/broadcast pesan kamu...</code>\n"
            "atau balas sebuah pesan lalu ketik <code>/broadcast</code>."
        )
        return

    # Ambil semua user terdaftar
    async with aiosqlite.connect(DB_PATH) as db:
        rows = await db.execute_fetchall("SELECT user_id FROM users ORDER BY user_id ASC")

    # Kirim dengan throttle ringan agar aman dari rate limit
    ok = fail = 0
    for (uid,) in rows:
        try:
            await bot.send_message(uid, text, disable_web_page_preview=True)
            ok += 1
            await asyncio.sleep(0.04)  # ~25 msg/detik
        except Exception:
            fail += 1
            await asyncio.sleep(0.1)

    await msg.answer(f"📣 Broadcast selesai: terkirim <b>{ok}</b>, gagal <b>{fail}</b>.")
    
# ---------- Admin commands ----------
@r.message(Command("give"))
async def cmd_give(msg: Message):
    uid = msg.from_user.id
    if not _is_admin(uid):
        await msg.answer("⛔ Perintah khusus admin.")
        return

    # format: /give <user_id|@username> <amount> [reason...]
    raw = (msg.text or "").strip()
    parts = raw.split(maxsplit=3)
    if len(parts) < 3:
        await msg.answer("Usage: <code>/give &lt;user_id|@username&gt; &lt;amount&gt; [reason]</code>")
        return

    target_s = parts[1]
    amount_s = parts[2]
    reason = parts[3] if len(parts) >= 4 else "admin_grant"

    target_id = await _resolve_user_id(target_s)
    if not target_id:
        await msg.answer("❗ Gunakan user_id numerik (minta user kirim /start agar tercatat).")
        return

    try:
        amount = int(amount_s)
    except Exception:
        await msg.answer("Jumlah poin harus integer. Contoh: <code>/give 123456 50 reward</code>")
        return

    if amount == 0:
        await msg.answer("Jumlah 0 tidak ada efek.")
        return

    # upsert user agar aman
    class DummyFrom:
        id = target_id
        username = ""
        first_name = "User"
    class DummyMsg:
        from_user = DummyFrom()
    await upsert_user(DummyMsg())  # minimal supaya ada record users

    await add_points(target_id, amount, reason=reason, by_admin=True)
    new_pts = await get_points(target_id)
    await msg.answer(f"✅ Berhasil menambahkan <b>{amount}</b> poin ke <code>{target_id}</code> (reason: {reason}).\nTotal sekarang: <b>{new_pts}</b>.")

# Fallback untuk command tidak dikenal
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
    if ADMINS:
        logger.info("Loaded %d admin(s): %s", len(ADMINS), ", ".join(map(str, ADMINS)))
    await init_db()
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("Webhook deleted (drop_pending_updates=True).")
    except Exception as e:
        logger.warning("delete_webhook failed: %s", e)

    await bot.set_my_commands([
        BotCommand(command="start", description="Welcome + menu"),
        BotCommand(command="tasks", description="Quest harian"),
        BotCommand(command="claim", description="Klaim harian (+10 pts)"),
        BotCommand(command="queststatus", description="Progres klaim"),
        BotCommand(command="points", description="Total poin"),
        BotCommand(command="leaderboard", description="Papan peringkat"),
        BotCommand(command="premium", description="Beli Premium via TON"),
        BotCommand(command="status", description="Cek status Premium"),
        BotCommand(command="ping", description="Tes respons bot"),
        BotCommand(command="help", description="Panduan"),
    ])

    dp.include_router(r)
    asyncio.create_task(premium_watcher())
    logger.info("🚀 BhinnekaBot is polling for updates…")
    await dp.start_polling(bot, allowed_updates=None)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped")
