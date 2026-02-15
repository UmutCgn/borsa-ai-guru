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
borsa_api = ccxt.binance() # Fiyat çekmek için

# --- V23 MULTI-SNIPER AYARLARI ---
ayarlar = {
    "target_coin": "BTC/USDT",
    "radar_listesi": [], 
    "trading_aktif": False,
    "butce": 0.0,
    "kar_hedefi": 40.0,      # %40 (Örn: 1000 -> 1400)
    "zarar_durur": 35.0,     # %35 (Örn: 1000 -> 650)
    "baslangic_bakiyesi": 1000.0, 
    "mod": "NORMAL",
    "manual_trigger": False,
    "durduruldu": False,
    "son_radar_guncelleme": 0
}

# --- YARDIMCI FONKSİYONLAR ---
def mesaj_gonder(metin):
    try: bot.send_message(CHAT_ID, metin, parse_mode="Markdown")
    except Exception as e: print(f"⚠️ Mesaj hatası: {e}")

def resim_gonder(resim_yolu, alt_yazi):
    try:
        with open(resim_yolu, 'rb') as photo:
            bot.send_photo(CHAT_ID, photo, caption=alt_yazi, parse_mode="Markdown")
    except Exception as e: print(f"⚠️ Resim hatası: {e}")

def piyasayi_tara_ve_bul():
    """Binance üzerinde yüksek hacim ve volatilite tarar."""
    try:
        tickers = borsa_api.fetch_tickers()
        adaylar = []
        for symbol, data in tickers.items():
            if "/USDT" in symbol and all(x not in symbol for x in ["UP/", "DOWN/", "BULL/", "BEAR/"]):
                vol = data.get('quoteVolume', 0)
                degisim = data.get('percentage', 0)
                if vol > 5000000: # 5M+ Hacim
                    adaylar.append({"symbol": symbol, "degisim": degisim, "skor": abs(degisim)})
        adaylar.sort(key=lambda x: x["skor"], reverse=True)
        return adaylar[:5]
    except Exception as e:
        print(f"Tarama Hatası: {e}")
        return []

def piyasayi_tara_ve_liste_guncelle():
    """Ana döngüden sessizce çağrılır."""
    try:
        sonuclar = piyasayi_tara_ve_bul() 
        if sonuclar:
            ayarlar["radar_listesi"] = [c['symbol'] for c in sonuclar]
            ayarlar["son_radar_guncelleme"] = time.time()
            return True
    except: pass
    return False

# --- KOMUT HANDLERLARI ---
@bot.message_handler(commands=['start', 'yardim', 'komutlar'])
def yardim_mesaji(message=None):
    metin = (
        "🧠 *GURU AI V23 MULTI-SNIPER | Komuta Merkezi*\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "🔭 `/kesfet` - Piyasayı tarar, en hareketli 5 coini radara alır.\n"
        "🚀 `/trade [bütçe]` - Radardaki coinlere 5 koldan saldırır (Örn: `/trade 10000`).\n"
        "📊 `/durum` - Kasa ilerlemesini ve açık pozisyonları anlık gösterir.\n"
        "🔍 `/analiz` - Mevcut radarı hemen taraması için botu dürter.\n"
        "🧹 `/reset` - Cüzdanı sıfırlar, hayalet işlemleri temizler.\n"
        "🏁 `/bitir` - Yeni işlem alımını durdurur, açık olanların kapanmasını bekler.\n"
        "🛑 `/stop` - ACİL ÇIKIŞ! Her şeyi anında piyasa fiyatından satar ve nakde geçer."
    )
    if message: bot.reply_to(message, metin, parse_mode="Markdown")
    else: mesaj_gonder(metin)

@bot.message_handler(commands=['kesfet'])
def kesfet_komutu(message):
    bot.reply_to(message, "🔭 *Piyasa Radarı çalıştırılıyor...* (Sadece liste güncellenecek)")
    
    sonuclar = piyasayi_tara_ve_bul()
    if sonuclar:
        ayarlar["radar_listesi"] = [c['symbol'] for c in sonuclar]
        ayarlar["son_radar_guncelleme"] = time.time()
        
        rapor = "🌪️ *RADAR GÜNCELLENDİ (YENİ HEDEFLER)*\n━━━━━━━━━━━━━━━━━━━━\n"
        for i, c in enumerate(sonuclar, 1):
            ikon = "📈" if c['degisim'] > 0 else "📉"
            rapor += f"{i}. *{c['symbol']}* | %{c['degisim']:.2f} {ikon}\n"
        
        rapor += "\n✅ *Liste hazır.* İşlemi başlatmak için: `/trade 10000`"
        bot.send_message(CHAT_ID, rapor, parse_mode="Markdown")
    else:
        bot.send_message(CHAT_ID, "⚠️ Yeterli hacme sahip hareketli coin bulunamadı.")

@bot.message_handler(commands=['trade'])
def trade_baslat(message):
    try:
        # 5 İŞLEM SINIRI KONTROLÜ
        if port_man.aktif_islem_sayisi() >= 5:
            bot.reply_to(message, "⚠️ *HATA:* Maksimum kapasite dolu (5/5). Yeni analiz için bir işlemin kapanması lazım.")
            return

        args = message.text.split()
        bakiye = float(args[1]) if len(args) > 1 else 1000.0
        
        ayarlar["trading_aktif"] = True
        ayarlar["mod"] = "KAMIKAZE"
        ayarlar["baslangic_bakiyesi"] = bakiye
        ayarlar["butce"] = bakiye * 0.10 # Her işleme kasanın %10'u
        ayarlar["manual_trigger"] = True 
        
        bot.reply_to(message, f"🚀 *MULTI-SNIPER ATEŞLENDİ!*\nRadardaki tüm coinler saniye saniye taranıyor.\n💰 Kasa Limit: {bakiye} USDT")
    except Exception as e:
        # ASIL HATAYI BURADA GÖSTERECEK!
        bot.reply_to(message, f"❌ Hata Detayı: {e}\nÖrn: `/trade 10000`")
        print(f"Trade Komutu Hatası: {e}")

@bot.message_handler(commands=['durum'])
def durum_raporu(message):
    try:
        cuzdan = port_man.cuzdan_yukle()
        pozlar = cuzdan.get("aktif_pozisyonlar", [])
        nakit = cuzdan.get("bakiye", 0.0)
        
        islemdeki_para = sum([p["miktar"] for p in pozlar])
        toplam_varlik = nakit + islemdeki_para
        aktif_poz_isimleri = ", ".join([p["coin"] for p in pozlar]) if pozlar else "Yok"
        
        baslangic = ayarlar["baslangic_bakiyesi"]
        hedef_yuzde = ((toplam_varlik / baslangic) * 100) - 100 if baslangic > 0 else 0
        radar_sayisi = len(ayarlar.get("radar_listesi", []))

        metin = (
            f"🎯 *MULTI-SNIPER OPERASYON MERKEZİ*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"💰 *Toplam Varlık:* {toplam_varlik:.2f} USDT\n"
            f"💵 *Boşta Nakit:* {nakit:.2f} USDT\n"
            f"📈 *Kâr Durumu:* %{hedef_yuzde:.2f}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📡 *Radar:* {radar_sayisi} Coin taranıyor\n"
            f"🔥 *Aktif Poz ({len(pozlar)}/5):* {aktif_poz_isimleri}\n"
            f"🚀 *Mod:* {ayarlar['mod']} | {'🟢 AKTİF' if ayarlar['trading_aktif'] else '🔴 DURDU'}"
        )
        bot.reply_to(message, metin, parse_mode="Markdown")
    except Exception as e:
        bot.reply_to(message, f"❌ Durum Hatası: {e}")

@bot.message_handler(commands=['reset'])
def acil_reset(message):
    try:
        cuzdan = port_man.cuzdan_yukle()
        pozlar = cuzdan.get("aktif_pozisyonlar", [])
        
        # 🚨 BUG FIX: İÇERİDEKİ PARAYI ANA BAKİYEYE İADE ET!
        iade_edilecek_para = sum([p["miktar"] for p in pozlar])
        if iade_edilecek_para > 0:
            cuzdan["bakiye"] += iade_edilecek_para
            
        cuzdan["aktif_pozisyonlar"] = []
        if "acik_islem" in cuzdan: cuzdan["acik_islem"] = None 
        port_man.cuzdan_kaydet(cuzdan)
        
        ayarlar["trading_aktif"] = False
        ayarlar["mod"] = "NORMAL"
        
        bot.reply_to(message, f"🧹 *CÜZDAN SIFIRLANDI VE KURTARILDI!* \nHayalet işlemler silindi.\n💸 Kaybolmaktan kurtarılan iade: {iade_edilecek_para:.2f} USDT\n💰 Güncel Net Bakiye: {cuzdan['bakiye']:.2f} USDT")
    except Exception as e:
        bot.reply_to(message, f"❌ Reset Hatası: {e}")
@bot.message_handler(commands=['analiz'])
def analiz_tetikle(message):
    ayarlar["manual_trigger"] = True
    bot.reply_to(message, "⚙️ Analiz motoru anında tetiklendi...")

@bot.message_handler(commands=['bitir'])
def bitir_komutu(message):
    ayarlar["trading_aktif"] = False
    bot.reply_to(message, "🏁 *SİSTEM DURDURULDU!*\nYeni pozisyon açılmayacak. Sadece açık olan işlemlerin TP/SL olması beklenecek.")

@bot.message_handler(commands=['stop'])
def stop_sistem(message):
    try:
        ayarlar["trading_aktif"] = False
        ayarlar["durduruldu"] = True
        
        cuzdan = port_man.cuzdan_yukle()
        pozlar = cuzdan.get("aktif_pozisyonlar", [])
        
        # EĞER İÇERİDE İŞLEM YOKSA
        if not pozlar:
            bot.reply_to(message, "🛑 Sistem kapatıldı. Açık pozisyon yoktu.\n🔌 Botun fişi çekiliyor...")
            import os, threading
            threading.Timer(2.0, lambda: os._exit(0)).start() # 2 sn sonra komple kapatır
            return
            
        bot.reply_to(message, f"⚠️ *ACİL DURUM:* {len(pozlar)} adet açık pozisyon anında piyasa fiyatından satılıp nakde çevriliyor!")
        
        # AÇIK POZİSYONLARI SAT VE NAKDE GEÇ
        kapanan_sayisi = 0
        for p in list(pozlar): 
            try:
                fiyat = borsa_api.fetch_ticker(p["coin"])['last']
                port_man.islem_kapat(p["coin"], fiyat, "ACIL_STOP")
                kapanan_sayisi += 1
            except Exception as ex:
                print(f"Acil Stop'ta {p['coin']} kapatılamadı: {ex}")
        
        # EMNİYET KEMERİ: Takılı kalan varsa parayı iade edip listeyi temizle
        cuzdan_son = port_man.cuzdan_yukle()
        kalan_pozlar = cuzdan_son.get("aktif_pozisyonlar", [])
        if kalan_pozlar:
            iade = sum([k["miktar"] for k in kalan_pozlar])
            cuzdan_son["bakiye"] += iade
            cuzdan_son["aktif_pozisyonlar"] = []
            port_man.cuzdan_kaydet(cuzdan_son)
            
        bot.reply_to(message, f"✅ *STOP BAŞARILI!* \n{kapanan_sayisi} işlem satıldı. Cüzdan nakitte güvende.\n🔌 Sistem tamamen kapatılıyor...")
        
        # 🚨 ŞALTERİ İNDİR (Mesajın gitmesi için 2 saniye bekle ve Python'u öldür)
        import os, threading
        threading.Timer(2.0, lambda: os._exit(0)).start()
        
    except Exception as e:
        bot.reply_to(message, f"❌ Acil stop hatası: {e}")

def dinlemeyi_baslat():
    threading.Thread(target=bot.infinity_polling, daemon=True).start()