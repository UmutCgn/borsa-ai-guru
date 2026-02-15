import telebot
import os
import ccxt
import threading
import time
from dotenv import load_dotenv
import portfolio_manager as port_man

# .env dosyasındaki anahtarları yükle
load_dotenv()

# --- GÜVENLİK AYARLARI ---
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
bot = telebot.TeleBot(TOKEN)

# --- V23 KAMIKAZE ELITE AYARLARI ---
ayarlar = {
    "target_coin": "BTC/USDT",
    "radar_listesi": ["BTC/USDT"], # /kesfet ile dolacak
    "trading_aktif": False,
    "butce": 0.0,
    "kar_hedefi": 40.0,      # Kamikaze Hedefi: %40 (1000 -> 1400)
    "zarar_durur": 35.0,     # Kasa Koruma: %35 (1000 -> 650)
    "baslangic_bakiyesi": 1000.0, 
    "mod": "NORMAL",
    "manual_trigger": False,
    "durduruldu": False,
    "bekleyen_coin": None,
    "son_radar_guncelleme": 0
}

@bot.message_handler(commands=['reset'])
def acil_reset(message):
    """Cüzdandaki hayalet işlemleri temizler."""
    try:
        cuzdan = port_man.cuzdan_yukle()
        cuzdan["acik_islem"] = None
        port_man.cuzdan_kaydet(cuzdan)
        ayarlar["trading_aktif"] = False
        ayarlar["mod"] = "NORMAL"
        bot.reply_to(message, "🧹 *Cüzdan Temizlendi!* Hayalet işlemler silindi ve mod NORMAL'e çekildi. Şimdi tekrar `/trade` yapabilirsin.")
    except Exception as e:
        bot.reply_to(message, f"❌ Reset Hatası: {e}")

def piyasayi_tara_ve_liste_guncelle():
    """
    Ana döngüden (main.py) çağrılan, mesaj atmayan sessiz radar güncelleyici.
    """
    try:
        # Daha önce yazdığımız tarama fonksiyonunu çağırıyoruz
        sonuclar = piyasayi_tara_ve_bul() 
        
        if sonuclar:
            yeni_radar = [c['symbol'] for c in sonuclar]
            ayarlar["radar_listesi"] = yeni_radar
            ayarlar["son_radar_guncelleme"] = time.time()
            print(f"📡 Radar Sessizce Güncellendi: {yeni_radar}")
            return True
    except Exception as e:
        print(f"⚠️ Sessiz Radar Hatası: {e}")
    return False

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
    cuzdan = port_man.cuzdan_yukle()
    return cuzdan.get("acik_islem") is not None

# --- KOMUT HANDLERLARI ---
@bot.message_handler(commands=['start', 'yardim', 'komutlar'])
def yardim_mesaji(message=None):
    metin = (
        "🧠 *Guru AI V23 Elite - Komuta Merkezi*\n\n"
        "🚀 `/trade 1000` - Kamikaze modunu 1000 birimle başlatır.\n"
        "🔭 `/kesfet` - Piyasanın en hareketli coinlerini bulur.\n"
        "📊 `/durum` - Kasa ilerlemesini (X -> 1400) gösterir.\n"
        "🔍 `/analiz` - Mevcut hedefe anlık AI analizi yapar.\n"
        "🏁 `/bitir` - Yeni işlemleri kapatır.\n"
        "🛑 `/stop` - Her şeyi kapatır ve nakde geçer."
    )
    if message: bot.reply_to(message, metin, parse_mode="Markdown")
    else: mesaj_gonder(metin)

@bot.message_handler(commands=['durum'])
def durum_raporu(message):
    try:
        cuzdan = port_man.cuzdan_yukle()
        mevcut_nakit = cuzdan.get("bakiye", 0.0)
        islem = cuzdan.get("acik_islem")
        islem_miktari = islem.get("miktar", 0.0) if islem else 0.0
        toplam_varlik = mevcut_nakit + islem_miktari
        
        # Kamikaze İlerleme Hesaplama
        baslangic = ayarlar["baslangic_bakiyesi"]
        hedef = baslangic * 1.40
        erime_siniri = baslangic * 0.65
        ilerleme = ((toplam_varlik - baslangic) / (hedef - baslangic)) * 100 if toplam_varlik > baslangic else 0

        metin = (
            f"🎯 *KAMIKAZE OPERASYON MERKEZİ*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"💰 *Mevcut Kasa:* {toplam_varlik:.2f} USDT\n"
            f"🏁 *Hedef (1400):* %{max(0, ilerleme):.1f} tamamlandı\n"
            f"🛡️ *Kasa Koruma (650):* {'GÜVENLİ' if toplam_varlik > erime_siniri else 'KRİTİK'}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📡 *Radar:* {len(ayarlar['radar_listesi'])} Coin aktif\n"
            f"📍 *Aktif Poz:* {islem.get('coin', 'Yok') if islem else 'Yok'}\n"
            f"🚀 *Mod:* {ayarlar['mod']} | {'🟢 AKTİF' if ayarlar['trading_aktif'] else '🔴 DURDU'}"
        )
        bot.send_message(message.chat.id, metin, parse_mode="Markdown")
    except Exception as e:
        print(f"❌ Durum Hatası: {e}")

@bot.message_handler(commands=['trade'])
def trade_baslat(message):
    try:
        args = message.text.split()
        bakiye = float(args[1]) if len(args) > 1 else 1000.0
        
        # AYARLARI ZORLA GÜNCELLE
        ayarlar["trading_aktif"] = True  # 👈 Emniyet kilidini aç
        ayarlar["mod"] = "KAMIKAZE"     # 👈 Modu Kamikaze yap
        ayarlar["baslangic_bakiyesi"] = bakiye
        ayarlar["butce"] = bakiye * 0.10 # %10 margin (isteğine göre ayarla)
        ayarlar["manual_trigger"] = True # 👈 Hemen analize başlaması için dürt
        
        bot.reply_to(message, f"🚀 *KAMIKAZE ELITE ÇALIŞTIRILDI!*\n💰 Kasa: {bakiye}\n🛡️ Durum: AKTİF")
    except:
        bot.reply_to(message, "❌ Örn: `/trade 10000`")

def piyasayi_tara_ve_bul():
    """Binance üzerinde yüksek hacim ve volatilite tarar."""
    try:
        borsa = ccxt.binance()
        tickers = borsa.fetch_tickers()
        adaylar = []
        for symbol, data in tickers.items():
            if "/USDT" in symbol and all(x not in symbol for x in ["UP/", "DOWN/", "BULL/", "BEAR/"]):
                vol = data.get('quoteVolume', 0)
                degisim = data.get('percentage', 0)
                if vol > 5000000: # 5M+ Hacim
                    adaylar.append({
                        "symbol": symbol,
                        "degisim": degisim,
                        "skor": abs(degisim)
                    })
        adaylar.sort(key=lambda x: x["skor"], reverse=True)
        return adaylar[:5]
    except Exception as e:
        print(f"Tarama Hatası: {e}")
        return []

@bot.message_handler(commands=['kesfet'])
def kesfet_komutu(message):
    bot.send_message(CHAT_ID, "🔭 *Piyasa Radarı çalışıyor... Sadece liste güncellenecek, işlem açılmayacak.*")
    
    sonuclar = piyasayi_tara_ve_bul() # Bu fonksiyon sadece veriyi çeker
    
    if sonuclar:
        yeni_radar = [c['symbol'] for c in sonuclar]
        ayarlar["radar_listesi"] = yeni_radar # Listeyi güncelledik
        ayarlar["son_radar_guncelleme"] = time.time()
        
        rapor = "🌪️ *RADAR GÜNCELLENDİ*\n━━━━━━━━━━━━━━━━━━━━\n"
        for i, c in enumerate(sonuclar, 1):
            rapor += f"{i}. *{c['symbol']}* | %{c['degisim']:.2f}\n"
        
        rapor += "\n✅ *Liste hazır.* İşlemi başlatmak için: `/trade 1000`"
        bot.send_message(CHAT_ID, rapor, parse_mode="Markdown")
    else:
        bot.send_message(CHAT_ID, "⚠️ Hareketli coin bulunamadı.")
    yeni_radar = [c['symbol'] for c in sonuclar]
    ayarlar["radar_listesi"] = yeni_radar
    ayarlar["son_radar_guncelleme"] = time.time()
    
    rapor = "🌪️ *RADARINDAKİ YENİ HEDEFLER*\n━━━━━━━━━━━━━━━━━━━━\n"
    for i, c in enumerate(sonuclar, 1):
        ikon = "📈" if c['degisim'] > 0 else "📉"
        rapor += f"{i}. *{c['symbol']}* | %{c['degisim']:.2f} {ikon}\n"
    
    rapor += "\n✅ Bu coinler Kamikaze moduna eklendi.\n2 saat boyunca bu liste taranacak."
    bot.send_message(CHAT_ID, rapor, parse_mode="Markdown")

@bot.message_handler(commands=['coin'])
def coin_degistir(message):
    args = message.text.split()
    if len(args) < 2:
        bot.reply_to(message, "👉 Örn: `/coin eth` (Sadece tekil analiz hedefini değiştirir)")
        return
    
    yeni = args[1].upper()
    yeni = yeni if "/" in yeni else f"{yeni}/USDT"
    ayarlar["target_coin"] = yeni
    ayarlar["manual_trigger"] = True
    bot.reply_to(message, f"🎯 Tekil analiz hedefi: *{yeni}*")

@bot.message_handler(commands=['bitir'])
def bitir_komutu(message):
    ayarlar["trading_aktif"] = False
    bot.reply_to(message, "🏁 *Kamikaze durduruldu.* Yeni işlem açılmayacak.")

@bot.message_handler(commands=['stop'])
def stop_sistem(message):
    ayarlar["durduruldu"] = True
    bot.reply_to(message, "🛑 *ACİL DURUM:* Sistem nakde geçip tamamen kapanıyor...")

@bot.message_handler(commands=['analiz'])
def analiz_tetikle(message):
    ayarlar["manual_trigger"] = True
    bot.reply_to(message, "⚙️ Analiz motoru tetiklendi...")

def dinlemeyi_baslat():
    threading.Thread(target=bot.infinity_polling, daemon=True).start()