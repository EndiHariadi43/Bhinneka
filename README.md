[![Actions Status](https://img.shields.io/github/actions/workflow/status/EndiHariadi43/Bhinneka/bhinnekabot.yml?branch=main)](https://github.com/EndiHariadi43/Bhinneka/actions/workflows/bhinnekabot.yml)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](./LICENSE)
[![Telegram](https://img.shields.io/badge/Telegram-@BHEK_bot-26A5E4?logo=telegram&logoColor=white)](https://t.me/BHEK_bot)

# Bhinneka (BHEK) — Unity in Diversity

Bhinneka (BHEK) is a community-driven meme coin inspired by the spirit of *“Bhinneka Tunggal Ika”* — Unity in Diversity.  
This repo contains:
- **BhinnekaBot** (Telegram) with **TON Premium** payment & on-chain verification  
- Minimal **ERC20/BEP20** contract (OpenZeppelin-based)  
- GitHub Actions workflow to run the bot 24/7 (long polling, rotating every 6h)

---

## 🌏 Filosofi Bhinneka Tunggal Ika

> *“Bhinneka Tunggal Ika”* berasal dari kitab Sutasoma karya Mpu Tantular (abad ke-14),  
> yang berarti **“Berbeda-beda tetapi tetap satu jua”**.  

Filosofi ini menjadi dasar persatuan bangsa Indonesia, menekankan bahwa keragaman suku, bahasa, budaya, dan keyakinan bisa disatukan dalam harmoni.  

BHEK mengadopsi nilai ini dalam dunia crypto:  
- Menghubungkan komunitas global yang beragam.  
- Menyatukan tujuan bersama melalui **transparansi**, **keadilan**, dan **kebersamaan**.  
- Menciptakan ekosistem komunitas yang kuat dan berkelanjutan.  

Dengan semangat *Unity in Diversity*, BHEK bukan sekadar meme coin, tetapi juga simbol kolaborasi lintas batas. 🚀

---

## 🚀 Earn Passive Income with Referrals

We believe in **community empowerment** — and now you can be rewarded simply by sharing Bhinneka (BHEK) with your friends!

✨ **How it works**:  
1. Share your **special referral link** below.  
2. When your friends trade, you earn **10% of their trading fees** — instantly, transparently, and on-chain.  
3. No limits: invite more friends = earn more rewards.

🔥 Don’t miss this chance to generate **passive income** while helping our community grow stronger.  
It’s simple, fair, and a win–win for everyone.

🔗 **Your Referral Link**  
👉 [Claim Rewards Here](https://four.meme/token/0x10bf27e03364b9cb471641893bbe4895dddc4444?code=K3QL9TE2KCHC)

> 💡 Tip: Pin this link on your social media or share it directly with friends — every trade counts toward your reward!

---

## ⚡ Quick Start (Local)

```bash
# Setup environment
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt

# Set environment variables
export BOT_TOKEN=xxx
export TON_DEST_ADDRESS=UQDwWm6EWph_L4suX5o7tC4KQZYr3rTN_rWiuP7gd8U3AMC5           # your TON wallet

# Run bot
python bhinnekabot.py
