[![Build](https://github.com/EndiHariadi43/Bhinneka/actions/workflows/bhinnekabot.yml/badge.svg)](https://github.com/EndiHariadi43/Bhinneka/actions)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](./LICENSE)
[![Telegram](https://img.shields.io/badge/Telegram-@BHEK_bot-26A5E4?logo=telegram&logoColor=white)](https://t.me/BHEK_bot)

# Bhinneka (BHEK) — Unity in Diversity

Bhinneka (BHEK) is a community-driven meme coin inspired by the spirit of *“Bhinneka Tunggal Ika”* — Unity in Diversity.  
This repo contains:
- **BhinnekaBot** (Telegram) with **TON Premium** payment & on-chain verification  
- Minimal **ERC20/BEP20** contract (OpenZeppelin-based)  
- GitHub Actions workflow to run the bot 24/7 (long polling, rotating every 6h)  

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

## Quick Start (Local)

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
export BOT_TOKEN=xxx
export TON_DEST_ADDRESS=UQC...           # your TON wallet
python bhinnekabot.py
