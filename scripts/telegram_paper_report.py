"""Best-effort Telegram reporting for independent Regime Band-30 PAPER."""
import json
import socket
import ssl
import urllib.error
import os
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

MAX_ATTEMPTS = 3


def _safe_error_kind(exc):
    if isinstance(exc, urllib.error.HTTPError):
        return f"http_{exc.code}"
    if isinstance(exc, urllib.error.URLError):
        reason = exc.reason
        if isinstance(reason, ssl.SSLError):
            return "tls_error"
        if isinstance(reason, socket.gaierror):
            return "dns_error"
        if isinstance(reason, (TimeoutError, socket.timeout)):
            return "timeout"
        if isinstance(reason, ConnectionRefusedError):
            return "connection_refused"
        return "network_error"
    if isinstance(exc, (TimeoutError, socket.timeout)):
        return "timeout"
    return "unexpected_error"


def send_telegram(token, chat, msg, *, opener=None, sleeper=None):
    """Best-effort delivery. Never log token, URL, response body or chat ID."""
    opener = opener or urllib.request.urlopen
    sleeper = sleeper or time.sleep
    data = urllib.parse.urlencode({"chat_id": chat, "text": msg[:4000]}).encode()
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            with opener(url, data, timeout=15) as response:
                payload = json.load(response)
            if payload.get("ok") is True:
                print("TELEGRAM_DELIVERED")
                return True
            # A non-ok API response is not assumed transient; avoid duplicate sends.
            print("TELEGRAM_DELIVERY_FAILED: api_rejected")
            return False
        except urllib.error.HTTPError as exc:
            kind = _safe_error_kind(exc)
            # 429/5xx are retryable; 400/401/403 indicate configuration/permission.
            retryable = exc.code == 429 or 500 <= exc.code <= 599
        except (urllib.error.URLError, TimeoutError, socket.timeout) as exc:
            kind = _safe_error_kind(exc)
            retryable = kind in {"dns_error", "timeout", "network_error", "connection_refused"}
        except (ValueError, OSError) as exc:
            kind = _safe_error_kind(exc)
            retryable = False
        if not retryable or attempt == MAX_ATTEMPTS:
            print(f"TELEGRAM_DELIVERY_FAILED: {kind}; attempts={attempt}")
            return False
        print(f"TELEGRAM_RETRY: {kind}; attempt={attempt}")
        sleeper(min(2 ** (attempt - 1), 4))
    return False


def message(state, summary, now_ms=None):
    now_ms = int(time.time() * 1000) if now_ms is None else now_ms
    ticks = state.get("ticks", [])
    outages = state.get("outages", [])
    last_tick = ticks[-1] if ticks else None
    last_outage = outages[-1] if outages else None
    fresh = lambda event: event and 0 <= now_ms - int(event.get("observed_ms", 0)) < 30 * 60 * 1000
    if fresh(last_outage) and (not last_tick or last_outage["observed_ms"] >= last_tick["observed_ms"]):
        # Only notify the newly recorded outage; historical outages are ignored.
        return ("🚨 Regime Band-30 PAPER | Yeni veri kesintisi\n"
                f"Hata: {str(last_outage.get('error', 'unknown'))[:80]}\n"
                f"Açıklama: {str(last_outage.get('message', ''))[:180]}")
    if not fresh(last_tick):
        return None  # No new 4h candle, no duplicate message
    stamp = datetime.fromtimestamp(last_tick["candle_ms"] / 1000, timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    new_trades = [t for t in state.get("trades", []) if t.get("observed_ms") == last_tick["observed_ms"]]
    lines = ["📊 Regime Band-30 | Bitget PAPER", f"4h mum: {stamp}",
             f"Gözlem: {summary.get('observations', 0)} | Toplam işlem: {summary.get('trades', 0)}",
             f"Sanal NAV: {float(summary.get('nav', 0)):,.2f} USDT",
             f"Başlangıçtan getiri: {float(summary.get('return_pct', 0)):+.2f}%",
             f"Yeni sanal işlem: {len(new_trades)}"]
    for trade in new_trades[:12]:
        lines.append(f"{trade['side'].upper()} {trade['asset']} | {float(trade['usdt']):.2f} USDT @ {float(trade['px']):.6g}")
    if len(new_trades) > 12:
        lines.append(f"+{len(new_trades)-12} işlem daha")
    lines.append("Gerçek emir yok; sonuçlar yalnızca simülasyondur.")
    return "\n".join(lines)

def main():
    token = os.environ.get("TELEGRAM_BOT_TOKEN") or os.environ.get("TELEGRAM_TOKEN")
    chat = os.environ.get("TELEGRAM_CHAT_ID") or os.environ.get("CHAT_ID")
    if not token or not chat:
        print("Telegram secrets missing; reporting skipped")
        return
    root = Path("results/regime_band30")
    state_file, summary_file = root / "state.json", root / "report/summary.json"
    if not state_file.exists() or not summary_file.exists():
        print("No PAPER report; reporting skipped")
        return
    state, summary = json.loads(state_file.read_text()), json.loads(summary_file.read_text())
    msg = message(state, summary)
    if not msg:
        print("No new observation or outage; reporting skipped")
        return
    run_url = f"https://github.com/{os.environ.get('GITHUB_REPOSITORY', 'evsayar33-oss/h054_spot_bot')}/actions/runs/{os.environ.get('GITHUB_RUN_ID', '')}"
    msg += "\nRun: " + run_url
    send_telegram(token, chat, msg)

if __name__ == "__main__":
    main()
