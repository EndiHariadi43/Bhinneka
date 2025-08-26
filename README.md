[![Build](https://github.com/EndiHariadi43/Bhinneka/actions/workflows/bhinnekabot.yml/badge.svg)](https://github.com/EndiHariadi43/Bhinneka/actions)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](./LICENSE)
[![Telegram](https://img.shields.io/badge/Telegram-@BHEK_bot-26A5E4?logo=telegram&logoColor=white)](https://t.me/BHEK_bot)

# Bhinneka (BHEK) — Unity in Diversity

Bhinneka (BHEK) is a community-driven meme coin inspired by the spirit of *“Bhinneka Tunggal Ika”* — Unity in Diversity.  
This repo contains:
- **BhinnekaBot** (Telegram) with **TON Premium** payment & on-chain verification
- Minimal **ERC20/BEP20** contract (OpenZeppelin-based)
- GitHub Actions workflow to run the bot 24/7 (long polling, rotating every 6h)

## Quick Start (Local)

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
export BOT_TOKEN=xxx
export TON_DEST_ADDRESS=UQC...           # your TON wallet
python bhinnekabot.py
