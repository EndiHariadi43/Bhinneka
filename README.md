[![Actions Status](https://img.shields.io/github/actions/workflow/status/EndiHariadi43/Bhinneka/bhinnekabot.yml?branch=main)](https://github.com/EndiHariadi43/Bhinneka/actions/workflows/bhinnekabot.yml)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](./LICENSE)
[![Telegram](https://img.shields.io/badge/Telegram-@BHEK_bot-26A5E4?logo=telegram&logoColor=white)](https://t.me/BHEK_bot)

# Bhinneka ($BHEK) — Unity in Diversity

**Bhinneka ($BHEK)** is a community-driven meme coin inspired by the timeless spirit of *“Bhinneka Tunggal Ika”* — Unity in Diversity.  

This repository contains:
- [**BhinnekaBot**](https://t.me/BHEK_bot) — Telegram bot with TON Premium payments & on-chain verification  
- [**Bhinneka Community**](https://t.me/bhinneka_coin) — Public group for discussions & updates  
- Minimal **ERC20/BEP20** contract (OpenZeppelin-based)  
- GitHub Actions workflow to keep the bot running 24/7 (long polling, rotating every 6h)  

---

## 🌏 The Philosophy of *Unity in Diversity*

> *“Bhinneka Tunggal Ika”* comes from the 14th-century *Sutasoma* manuscript by Mpu Tantular,  
> meaning **“They are many, yet they are one.”**

This motto later became the foundation of Indonesia’s national identity, symbolizing harmony among diverse ethnicities, languages, cultures, and beliefs.  

BHEK embraces this wisdom in the crypto space:  
- 🌐 Connecting communities across the globe  
- ⚖️ Promoting fairness, transparency, and collective growth  
- 🤝 Building a sustainable ecosystem based on cooperation  

With this philosophy, **$BHEK is more than just a meme coin** — it’s a **symbol of collaboration without borders**. 🚀  

---

## 🚀 Earn Passive Income with Referrals

We believe in **community empowerment** — now you can earn rewards simply by sharing Bhinneka ($BHEK) with your friends!

✨ **How it works:**  
1. Share your **special referral link**.  
2. Every time your friends trade, you earn **10% of their trading fees** — instantly, transparently, and on-chain.  
3. No limits: the more you share, the more you earn.  

🔥 Don’t miss this chance to generate **passive income** while helping our community grow stronger.  
It’s simple, fair, and a win–win for everyone.  

🔗 **Your Referral Link**  
👉 [Claim Rewards Here](https://four.meme/token/0x10bf27e03364b9cb471641893bbe4895dddc4444?code=K3QL9TE2KCHC)

> 💡 Pro tip: Pin this link on your socials or share it directly — every trade counts toward your rewards!

---

## ⚡ Quick Start (Local Development)

You can run the bot locally for testing or development.

```bash
# 1. Setup environment
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt

# 2. Create a .env file with your secrets
echo "BOT_TOKEN=your-telegram-bot-token" >> .env
echo "TON_DEST_ADDRESS=your-ton-wallet-address" >> .env

# 3. Run the bot
python bhinnekabot.py
```

> 📝 See [SECURITY.md](./SECURITY.md) for reporting vulnerabilities, and [CONTRIBUTING.md](./CONTRIBUTING.md) if you’d like to help improve the project.

---

## 💖 Support this project

Your support helps keep **Bhinneka ($BHEK)** alive and growing.  
Every contribution goes to development, hosting, and community rewards.

[![Sponsor](https://img.shields.io/badge/Sponsor-💖-pink?style=for-the-badge)](https://github.com/sponsors/EndiHariadi43)
[![Patreon](https://img.shields.io/badge/Patreon-Support-orange?style=for-the-badge&logo=patreon)](https://patreon.com/EndiHariadi43)

Or support via local platforms:  
[![Saweria](https://img.shields.io/badge/Saweria-Donate-brightgreen?style=for-the-badge&logo=buymeacoffee&logoColor=white)](https://saweria.co/EndiHariadi43)  
[![Trakteer](https://img.shields.io/badge/Trakteer-Support-red?style=for-the-badge&logo=buymeacoffee&logoColor=white)](https://trakteer.id/endihariadi43/tip)

---

## 📜 License

This project is licensed under the [Apache License 2.0](./LICENSE).  
See the [NOTICE](./NOTICE) file for additional attributions and third-party components.
