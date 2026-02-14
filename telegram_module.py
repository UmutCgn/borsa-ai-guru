import telebot
import os
import ccxt
import threading
from dotenv import load_dotenv
import portfolio_manager as port_man

# .env dosyasındaki anahtarları yükle
load_dotenv()

# --- GÜVENLİK AYARLARI ---
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
bot = telebot.TeleBot(TOKEN)

# --- GLOBAL DURUM VE HEDEFLER ---
ayarlar = {
    "target_coin": "BTC/USDT",
    "trading_aktif": False,
    "butce": 0.0,
    "kar_hedefi": 2.0,    # Varsayılan %2
    "zarar_durur": 2.0,   # Varsayılan %2
    "mod": "NORMAL",
    "manual_trigger": False,
    "durduruldu": False,
    "bekleyen_coin": None 
}

POPULER_COINLER = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "XRP/USDT", "AVAX/USDT"]

# --- YARDIMCI FONKSİYONLAR ---
def mesaj_gonder(metin):
    try: bot.send_message(CHAT_ID, metin, parse_mode="Markdown")
    except Exception as e: print(f"⚠️ Mesaj hatası: {e}")

def resim_gonder(resim_yolu, alt_yazi):
    try:
        with open(resim_yolu, 'rb') as photo:
            bot.send_photo(CHAT_ID, photo, caption=alt_yazi, parse_mode="Markdown")
    except Exception as e: print(f"⚠️ Resim hatası: {e}")

def is_islem_var():
    """Aktif işlem kontrolü yapar."""
    cuzdan = port_man.cuzdan_yukle()
    return cuzdan.get("acik_islem") is not None

# --- KOMUT HANDLERLARI ---
@bot.message_handler(commands=['start', 'yardim', 'komutlar'])
def yardim_mesaji(message=None):
    """
    Hem kullanıcı komutuna yanıt verir hem de bot açılışında 
    proaktif mesaj gönderir.
    """
    metin = (
        "🤖 *Guru AI - Komuta Merkezi*\n\n"
        "📊 `/durum` - Cüzdan ve başarı özeti.\n"
        "🚀 `/trade [BÜTÇE] [KAR%] [ZARAR%]` - Botu başlatır.\n"
        "🏁 `/bitir` - Yeni işlemleri kapatır.\n"
        "🪙 `/coin` - Hedef değiştirir.\n"
        "🔍 `/analiz` - Anlık rapor gönderir.\n"
        "🛑 `/stop` - Nakde geçer ve botu kapatır."
    )
    
    # Eğer bir mesaj üzerinden çağrıldıysa (kullanıcı yazdıysa) yanıtla
    if message is not None:
        try:
            bot.reply_to(message, metin, parse_mode="Markdown")
        except Exception as e:
            print(f"⚠️ Yanıt hatası: {e}")
            bot.send_message(CHAT_ID, metin, parse_mode="Markdown")
    else:
        # Eğer main.py içinden (None ile) çağrıldıysa doğrudan CHAT_ID'ye gönder
        try:
            bot.send_message(CHAT_ID, metin, parse_mode="Markdown")
        except Exception as e:
            print(f"⚠️ Başlangıç mesajı gönderilemedi: {e}")

@bot.message_handler(commands=['durum'])
def durum_raporu(message):
    try:
        cuzdan = port_man.cuzdan_yukle()
        h_kar, k_adet, k_basari = port_man.istatistikleri_getir()
        
        nakit = cuzdan.get("bakiye", 0.0)
        islem = cuzdan.get("acik_islem")
        islemdeki = islem.get("miktar", 0.0) if islem else 0.0
        aktif_p = islem.get("coin", "Yok") if islem else "Yok"
        
        metin = (
            f"📊 *GÜNCEL FİNANSAL TABLO*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"💵 *Net Nakit:* {nakit:.2f} USDT\n"
            f"💰 *İşlemdeki:* {islemdeki:.2f} USDT\n"
            f"🏦 *Toplam Varlık:* {nakit + islemdeki:.2f} USDT\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📅 *7 Günlük P/L:* {h_kar} USDT\n"
            f"🔥 *Kamikaze Başarısı:* %{k_basari} ({k_adet} İşlem)\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🛡️ *Mod:* {ayarlar['mod']}\n"
            f"🚀 *Trading:* {'🟢 AÇIK' if ayarlar['trading_aktif'] else '🔴 KAPALI'}\n"
            f"📍 *Aktif Poz:* {aktif_p}"
        )
        bot.send_message(message.chat.id, metin, parse_mode="Markdown")
    except Exception as e:
        print(f"❌ Durum Hatası: {e}")
        bot.reply_to(message, "⚠️ Rapor hazırlanırken bir hata oluştu.")

@bot.message_handler(commands=['trade'])
def trade_baslat(message):
    if is_islem_var():
        bot.reply_to(message, "⚠️ *HATA:* Aktif işlem varken yeni trade başlatılamaz!")
        return
    
    try:
        args = message.text.split()
        butce = float(args[1])
        kar = float(args[2]) if len(args) > 2 else 2.0
        zarar = float(args[3]) if len(args) > 3 else 2.0
        
        ayarlar.update({
            "trading_aktif": True, "butce": butce, 
            "kar_hedefi": kar, "zarar_durur": zarar,
            "mod": "KAMIKAZE", "manual_trigger": True
        })
        
        bot.reply_to(message, f"🔥 *KAMİKAZE AKTİF!*\n💰 Bütçe: {butce} USDT\n🎯 Hedef: %{kar}\n🛑 Stop: %{zarar}")
    except:
        bot.reply_to(message, "❌ Örn: `/trade 1000 2.5 1.5` (Bütçe Kar Zarar)")

@bot.message_handler(commands=['bitir'])
def trade_bitir(message):
    ayarlar["trading_aktif"] = False
    ayarlar["mod"] = "NORMAL"
    bot.reply_to(message, "🏁 *Trading Durduruldu.* Yeni işlem açılmayacak.")

def piyasayi_tara_ve_bul():
    """Tüm Binance piyasasını tarar ve en yüksek volatiliteye sahip 200+ coin içinden en iyi 5'i seçer."""
    try:
        # Binance bağlantısı (Hızlı tarama için)
        borsa = ccxt.binance()
        tickers = borsa.fetch_tickers()
        
        adaylar = []
        for symbol, data in tickers.items():
            # Filtreler: Sadece USDT pariteleri ve Kaldıraçlı (UP/DOWN) olmayanlar
            if "/USDT" in symbol and "UP/" not in symbol and "DOWN/" not in symbol:
                vol = data.get('quoteVolume') # 24s Hacim (USDT)
                degisim = data.get('percentage') # 24s Değişim %
                
                # Minimum 5 Milyon USDT hacim (Likidite güvenliği için)
                if vol and vol > 5000000 and degisim is not None:
                    adaylar.append({
                        "coin": symbol.split('/')[0], # Sadece 'BTC' kısmını al
                        "degisim": degisim,
                        "skor": abs(degisim) # Hem düşüş hem çıkış fırsattır
                    })
        
        # En hareketli olanlara göre sırala
        adaylar.sort(key=lambda x: x["skor"], reverse=True)
        return adaylar[:5] # En iyi 5 adayı dön
    except Exception as e:
        print(f"Tarama Hatası: {e}")
        return []

@bot.message_handler(commands=['kesfet'])
def kesfet_komutu(message):
    bot.reply_to(message, "🔭 *Piyasa Radarı 200+ Coin Üzerinde Çalışıyor...*")
    
    sonuclar = piyasayi_tara_ve_bul()
    
    if not sonuclar:
        bot.send_message(CHAT_ID, "⚠️ Şu an uygun hareketlilikte coin bulunamadı.")
        return

    rapor = "🌪️ *PİYASANIN EN HAREKETLİ COINLERİ*\n"
    rapor += "━━━━━━━━━━━━━━━━━━━━\n"
    
    for i, c in enumerate(sonuclar, 1):
        durum = "📈" if c['degisim'] > 0 else "📉"
        # Tıklanabilir komut oluşturuyoruz: /coin COIN_ADI
        rapor += f"{i}. *{c['coin']}* | %{c['degisim']:.2f} {durum}\n"
        rapor += f"   👉 Değiştirmek için: `/coin {c['coin'].lower()}`\n\n"
    
    en_iyi = sonuclar[0]['coin'].lower()
    rapor += "━━━━━━━━━━━━━━━━━━━━\n"
    rapor += f"🧠 *AI TAVSİYESİ:* `{en_iyi.upper()}`\n"
    rapor += f"Hemen analize başlamak için tıklayın: `/coin {en_iyi}`"
    
    bot.send_message(CHAT_ID, rapor, parse_mode="Markdown")

@bot.message_handler(commands=['stop'])
def stop_sistem(message):
    ayarlar["durduruldu"] = True
    bot.reply_to(message, "🛑 *KAPATMA EMRİ:* Sistem nakde geçip kapanıyor...")

@bot.message_handler(commands=['coin'])
def coin_komutu(message):
    args = message.text.split()
    
    # Eğer kullanıcı sadece /coin yazdıysa (Parametre yoksa)
    if len(args) == 1:
        metin = (
            "🎯 *Hedef Değiştirme Rehberi*\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "Doğrudan coin adını yazabilirsin:\n"
            "👉 `/coin btc` veya `/coin eth` gibi.\n\n"
            "💡 İpucu: `/kesfet` yazarak şu an en hareketli coinleri görebilirsin."
        )
        bot.send_message(CHAT_ID, metin, parse_mode="Markdown")
        return
    
    # Kullanıcının yazdığı coini al ve büyük harfe çevir
    yeni_coin_ham = args[1].upper()
    
    # Eğer kullanıcı sadece 'BTC' yazdıysa 'BTC/USDT' formatına çevir
    yeni = yeni_coin_ham if "/" in yeni_coin_ham else f"{yeni_coin_ham}/USDT"
    
    try:
        if is_islem_var():
            ayarlar["bekleyen_coin"] = yeni
            bot.reply_to(message, f"⚠️ Pozisyon açık! `{yeni}` birimine geçmek için onay verin: `/onayla`")
        else:
            ayarlar["target_coin"] = yeni
            ayarlar["manual_trigger"] = True
            bot.send_message(CHAT_ID, f"✅ Yeni Hedef Başarıyla Belirlendi: *{yeni}*")
    except Exception as e:
        bot.reply_to(message, f"❌ Hata oluştu: {e}")

@bot.message_handler(commands=['onayla'])
def onayla_komutu(message):
    if ayarlar["bekleyen_coin"]:
        ayarlar["target_coin"] = ayarlar["bekleyen_coin"]
        ayarlar["bekleyen_coin"] = None
        ayarlar["manual_trigger"] = True
        bot.reply_to(message, "🔄 Onaylandı, eski işlem kapatılıp yeni hedefe geçiliyor...")
    else: bot.reply_to(message, "Bekleyen onay yok.")

@bot.message_handler(commands=['analiz'])
def analiz_tetikle(message):
    ayarlar["manual_trigger"] = True
    bot.reply_to(message, "⚙️ Analiz motoru tetiklendi...")

def dinlemeyi_baslat():
    threading.Thread(target=bot.infinity_polling, daemon=True).start()