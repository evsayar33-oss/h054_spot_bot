# h054_spot_bot — veri biriktirme, sınırlı araştırma ve ileri kanıt

Kaynak: 4h H054-MOM2 PAPER durum ve local registry, bağımsız band30 araştırma hattı.

Orijinal strateji mantığı: BTC/ETH rejim-temelli momentum, hareket/düşüş bandı ve risk bütçesi.

Kabul/araştırma koruması: PAPER_ACCEPT yalnız simülasyon; LIVE_DENY korunur.

Bu araştırma iş akışı, üretimdeki mevcut strateji, PAPER veya LIVE
kurallarını **değiştirmez**. Repo içindeki mevcut tarihli veri ve resmi
araştırma kayıtları üzerinden kaynağın orijinal durumunu toplar.
Kayıtlar aynı SHA ile yinelendiğinde yeni örnek sayılmaz. Kaynak zamanı
geri sarılırsa fail-closed; aynı kaynak zamanı düzeltilirse revision sayılır.
Her yeni gerçek kaynak kaydının parmak izi append-only
`research/strategy-mesh-evidence/observations/strategy_mesh/observations.jsonl`
zincirinde tutulur. Günlük cron ve manuel Actions çalıştırması ayrıca
JSON/Markdown raporu ve yalnız tasarım amaçlı hipotez kuyruğu üretir.

Kullanılan araştırma motoru: `evsayar33-oss/quant_superlab` pinned
`811c04aeca2f2634bfe0f3d07be9c4b8bf480090`.
Bu kod yalnız çalıştıran repo içinde çalışır; diğer repoya veri göndermez.

Özgün mantığı bozmamak için kombinasyonlar yalnız bu repo için
önceden belirlenmiş ve ekonomik anlamı olan özellik ailelerinden gelir.
Bunlar **backtest veya doğrulanmış strateji değildir**. Sıradaki
aşamada verisi yeterli bulunan adayların t-anında bilinen özellikleri,
negatif kontroller, walk-forward, masraf/likidite stresi, ayrık holdout
ve olgunlaşmış prospective trade kanıtı bağımsız olarak tamamlanacaktır.
Bunları geçmeden otomatik PAPER/LIVE terfisi yasaktır.

GitHub Actions → *Native data-first strategy research (NO ORDERS)* →
*Run workflow* ile manuel başlatılabilir. Araştırma defteri ve kanıt
branch'i, mevcut üretim dalı ve eski PAPER kanıt dallarından bağımsızdır.
