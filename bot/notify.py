from __future__ import annotations

import os
import urllib.parse
import urllib.request


def telegram(text: str) -> None:
    tok, chat = os.environ.get("TELEGRAM_TOKEN"), os.environ.get("CHAT_ID")
    if not tok or not chat:
        print("[telegram] not configured\n" + text)
        return
    body = urllib.parse.urlencode({"chat_id": chat, "text": text[:4000]}).encode()
    try:
        urllib.request.urlopen(f"https://api.telegram.org/bot{tok}/sendMessage", body, timeout=15)
    except Exception as e:  # noqa: BLE001
        print(f"[telegram] failed: {e}")
