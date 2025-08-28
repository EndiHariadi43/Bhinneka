# bhinnekabot.py
# BhinnekaBot — Unity in Diversity 🤝
# Fitur: welcome + quest (daily claim), premium via TON dengan verifikasi komentar unik on-chain.

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
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ChatMemberStatus, ParseMode
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

# ==== KOMUNITAS & GRUP ====
COMMUNITY_LINK = "https://t.me/bhinneka_coin"   # grup/channel komunitas
X_LINK         = "https://x.com/bhinneka_coin"  # opsional
COMMUNITY_CHAT_ID = "@bhinneka_coin"            # pastikan bot adalah admin di grup ini

assert BOT_TOKEN and TON_DEST, "Set BOT_TOKEN & TON_DEST_ADDRESS di env/secrets"

bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
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
    f'Join komunitas Telegram: <a href="{COMMUNITY_LINK}">@bhinneka_coin</a>',
    "Follow X (Twitter): <i>opsional</i>",
    "Retweet pinned post (X) & mention #BHEK",
]

# ---------- MAIN KEYBOARD (GLOBAL, REUSABLE) ----------
MAIN_KB = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="👥 Join Telegram", url=COMMUNITY_LINK)],
        [InlineKeyboardButton(text="🐦 Follow X", url=X_LINK)],
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

            -- Quest harian (UTC), satu klaim per user per hari
            CREATE TABLE IF NOT EXISTS quests (
                user_id INTEGER,
                day TEXT,               -- YYYYMMDD (UTC)
                claimed_at INTEGER,     -- epoch seconds UTC
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
        return False  # kemungkinan sudah ada (PRIMARY KEY)

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
            # tandai order expired (>24h)
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

# ---------- Inline keyboards ----------
def premium_keyboard(deeplink: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔗 Pay in TON (App)", url=deeplink)],
            [InlineKeyboardButton(text="✅ Saya sudah transfer", callback_data="check_payment")],
        ]
    )

# ---------- Handlers ----------
@dp.message(CommandStart())
async def cmd_start(msg: Message):
    logger.info("START from uid=%s username=%s", msg.from_user.id, msg.from_user.username)
    await upsert_user(msg)
    await msg.answer(WELCOME_TEXT, reply_markup=MAIN_KB)
    logger.info("START replied to uid=%s", msg.from_user.id)

@dp.message(Command("tasks"))
async def cmd_tasks(msg: Message):
    lines = ["📋 <b>Quest Harian</b>"]
    for i, t in enumerate(TASKS, 1):
        lines.append(f"{i}. {t}")
    lines.append("\nKetik <code>/claim</code> setelah selesai.")
    await msg.answer("\n".join(lines), reply_markup=MAIN_KB)

@dp.message(Command("claim"))
async def cmd_claim(msg: Message):
    uid = msg.from_user.id
    try:
        member = await bot.get_chat_member(COMMUNITY_CHAT_ID, uid)
        status_ok = member.status in {
            ChatMemberStatus.MEMBER,
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.CREATOR,
        }
        if not status_ok:
            await msg.answer(
                "❌ Kamu belum terdeteksi di grup. Silakan join via tombol di /tasks.",
                reply_markup=MAIN_KB
            )
            return

        # Sudah join → cek apakah sudah klaim hari ini
        if await has_claimed_today(uid):
            await msg.answer(
                "ℹ️ Kamu sudah klaim quest hari ini. Datang lagi besok ya! ✨",
                reply_markup=MAIN_KB
            )
            return

        if await record_claim(uid):
            await msg.answer(
                "✅ Klaim kamu dicatat. (Sistem reward akan diaktifkan setelah Premium). Terima kasih sudah join!",
                reply_markup=MAIN_KB
            )
        else:
            await msg.answer(
                "ℹ️ Terlihat kamu sudah klaim hari ini. Sampai jumpa besok! 👋",
                reply_markup=MAIN_KB
            )

    except Exception:
        await msg.answer(
            "⚠️ Tidak bisa memverifikasi. Pastikan bot sudah ada di grup dan coba lagi.",
            reply_markup=MAIN_KB
        )

@dp.message(Command("queststatus"))
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

@dp.message(Command("premium"))
async def cmd_premium(msg: Message):
    uid = msg.from_user.id
    code = f"BHEK-{uid}-{secrets.token_hex(2).upper()}"

    async with aiosqlite.connect(DB_PATH) as db:
        # hindari penumpukan order pending
        await db.execute("DELETE FROM orders WHERE user_id=? AND status='PENDING'", (uid,))
        await db.execute(
            "INSERT INTO orders(user_id, code, amount_ton, created_at) VALUES (?,?,?,?)",
            (uid, code, PREMIUM_PRICE_TON, int(time.time())),
        )
        await db.commit()

    logger.info("Order created uid=%s code=%s price=%.3f", uid, code, PREMIUM_PRICE_TON)

    link = build_ton_deeplink(TON_DEST, PREMIUM_PRICE_TON, code)
    text = (
        "🌟 <b>Premium / Posisi Istimewa</b>\n\n"
        f"Harga: <b>{PREMIUM_PRICE_TON} TON</b> untuk {PREMIUM_DAYS} hari.\n"
        f"Alamat: <code>{TON_DEST}</code>\n"
        f"Komentar (WAJIB): <code>{code}</code>\n\n"
        "1) Klik tombol <b>Pay in TON</b> (atau transfer manual)\n"
        "2) Pastikan <b>comment</b> PERSIS sama\n"
        "3) Setelah bayar, tekan <b>Saya sudah transfer</b>\n\n"
        "Bot memverifikasi di blockchain dan otomatis mengaktifkan status Premium ✅"
    )
    await msg.answer(text, reply_markup=premium_keyboard(link))

@dp.callback_query(F.data == "check_payment")
async def cb_check_payment(cb):
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

@dp.message(Command("status"))
async def cmd_status(msg: Message):
    s = await get_status(msg.from_user.id)
    await msg.answer(s, reply_markup=MAIN_KB)

@dp.message(Command("help"))
async def cmd_help(msg: Message):
    await msg.answer(
        "📖 <b>Command List</b>\n\n"
        "/start — Welcome & menu\n"
        "/tasks — Quest harian\n"
        "/claim — Klaim quest (demo)\n"
        "/queststatus — Lihat progres quest\n"
        "/premium — Beli Premium via TON\n"
        "/status — Cek status Premium\n"
        "/help — Panduan semua command",
        reply_markup=MAIN_KB
    )

# ---------- Main ----------
async def main():
    logger.info("Bot booting...")
    await init_db()

    # set menu commands
    await bot.set_my_commands([
        BotCommand(command="start", description="Welcome + menu"),
        BotCommand(command="tasks", description="Quest harian"),
        BotCommand(command="claim", description="Klaim quest (demo)"),
        BotCommand(command="queststatus", description="Lihat progres quest"),
        BotCommand(command="premium", description="Beli Premium via TON"),
        BotCommand(command="status", description="Cek status Premium"),
        BotCommand(command="help", description="Bantuan"),
    ])

    asyncio.create_task(premium_watcher())
    logger.info("🚀 BhinnekaBot is polling for updates...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped")
