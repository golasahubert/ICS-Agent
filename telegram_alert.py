# telegram_alert.py

import os
import httpx

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "") #TELEGRAM BOTID:BOTPWD
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "") # TELEGRAM CHAT ID

async def send_telegram_alert(message: str):
    """
    Sends an alert message to your Telegram bot.

    :param message: Message string to send (can contain HTML formatting)
    """
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, json=payload, timeout=10)
            if response.status_code == 200:
                print("[TG] [+] Alert sent successfully.")
            else:
                print(f"[TG] [!] Failed to send alert. Status: {response.status_code}, {response.text}")
        except Exception as e:
            print(f"[TG] [✘] Exception while sending alert: {e}")

# Optional: test independently
if __name__ == "__main__":
    import asyncio
    asyncio.run(send_telegram_alert("✅ Test: Honeypot Telegram bot integration working."))
