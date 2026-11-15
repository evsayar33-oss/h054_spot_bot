# h054_spot_bot

Bitget botu. Strateji: **H054 + boştaki nakitle funding arbitrajı (always_on)**.
Bu, quant_lab'de ileri testte (walk-forward) **en kârlı** kabul edilen seçenektir (en az düşen değil).

- H054: BTC + ETH spot. SMA200 + TSMOM 30/90/180 gün + %40 vol hedefi + %10 bant. 4h kapanışta karar.
- Boştaki nakdin yarısı: spot al + perp short (1x, isolated). Funding geliri toplar, fiyat riski yok.
- Test (2020→, 1000$): H054+arbitraj ≈ 9.966$, sadece H054 ≈ 8.506$. Max düşüş ≈ −%24.5.

## Güvenlik
- Bot her çalışmada quant_lab `decisions/registry.json` okur. H054 ACCEPT değilse veya 10 günden eskiyse **her şeyi kapatır**.
- Varsayılan **PAPER** (sanal 1000$). Canlı için İKİ şart: `config.yaml` → `mode: live` VE repo değişkeni `LIVE_TRADING = true`.
- Tek çalışmada en çok %60 işlem hacmi. Bakiye < 100$ ise işlem yok.

## Kurulum (telefondan)
1. Bitget → API: izin **Read + Trade** (Spot ve Futures). **Withdraw ASLA açma.** IP kısıtı yoksa da çalışır.
2. GitHub → Settings → Secrets and variables → Actions → **Secrets**:
   `BITGET_API_KEY`, `BITGET_API_SECRET`, `BITGET_PASSPHRASE`, `TELEGRAM_TOKEN`, `CHAT_ID`.
   Anahtarları sohbete yazma.
3. Actions → h054-bot → Run workflow. Telegram'a PAPER mesajı gelmeli.
4. En az 2–4 hafta PAPER izle (`logs/equity.csv`, `logs/trades.csv`).
5. Canlı: `config.yaml` → `mode: live`; Variables → `LIVE_TRADING` = `true`.
   Durdurmak için `LIVE_TRADING` = `false` (bot paper'a döner, pozisyonlara dokunmaz) veya mode: paper.

## Sermaye
- Teknik alt sınır ≈ 500$ (Bitget en küçük emir ~5$). Önerilen 1.000–2.000$.
- Spot ve futures (USDT-M) hesabı aynı Bitget hesabında olmalı; bot USDT'yi aralarında transfer eder.

## Zayıf yönler
- Funding geçmişi Binance verisi (Bitget için vekil). Funding negatife dönerse arbitraj az kaybettirir.
- Sadece 2 coin; kripto genel düşüşünde H054 nakde geçer ama geçiş gecikmeli olabilir.
- Geçmiş test canlıda aynı sonucu garanti etmez.


## H054-MOM2 research variant (2026-11-15)
- **Change**: original H054 entered risk-on if *any one* of 30/90/180-day momentum signals was positive. MOM2 needs **at least two positive**. The 200-day SMA gate, 40% annualized vol target, 10% trade band, BTC/ETH equal sleeves, and idle-cash funding hedge settings are unchanged.
- **Research-only comparison, NOT verified live PnL**: on Binance BTC/ETH 4h spot OHLC, 2023-10-18 to 2026-11-13, a basic next-open, long/cash model with 15 bps assumed costs per traded spot side and no funding produced H054 +99.44% versus MOM2 +139.05%; max drawdown -23.91% versus -19.09%. In the already-viewed 2025-2026 interval: H054 -7.89% versus MOM2 +11.11%. These figures are not the bot's own futures-hedge NAV or an independent untouched holdout.
- No automatic changes to Bitget API orders, safety registry, live mode, perp bookkeeping, or funding assumptions. PAPER remains the default. This repo retains the original quant_lab H054 fixture only for **legacy min_positive_horizons=1**; new MOM2 tests verify the majority-vote behavior independently.
- Research continues separately in **quant_superlab**. Do not interpret a historical win as a forward profitability guarantee.
