import time, ccxt, os
import telegram_module as tel_mod
import matplotlib
matplotlib.use('Agg')
from datetime import datetime
import matplotlib.pyplot as plt
import ai_supervisor
import portfolio_manager as port_man
import vision_module, sentiment_module, decision_engine, risk_yoneticisi, sayisal_veri

# --- AYARLAR ---
DONGU_SURESI = 900 # 15 Dakika (Analiz periyodu)
borsa = ccxt.binance({
    'timeout': 30000, 
    'enableRateLimit': True, 
    'options': {'defaultType': 'spot'} 
}) # Tek borsa objesi ile hız kazanıyoruz


def grafik_hazirla(sembol, tf):
    """V6 Dataset standardında 17 mumluk çizgili grafik çizer."""
    try:
        # LİMİTİ 150 YAPTIK: İndikatörlerin (EMA50 vb.) hesaplanabilmesi için geçmişe ihtiyaç var!
        ohlcv = borsa.fetch_ohlcv(sembol, timeframe=tf, limit=150)
        import pandas as pd; import mplfinance as mpf; import pandas_ta as ta
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('timestamp', inplace=True)
        
        # Çizgileri ekle
        df['EMA20'] = ta.ema(df['close'], length=20)
        df['EMA50'] = ta.ema(df['close'], length=50)
        bbands = ta.bbands(df['close'], length=20, std=2)
        df['BB_LOWER'] = bbands.iloc[:, 0]
        df['BB_UPPER'] = bbands.iloc[:, 2]
        
        # NaN olanları at (İlk 50 mum çöpe gidecek, geriye sağlam mumlar kalacak)
        df.dropna(inplace=True)
        
        # Son 17 mumu al (AI'ın tam olarak eğitimde gördüğü pencere genişliği)
        df_slice = df.tail(17) 
        
        ekstra_cizgiler = [
            mpf.make_addplot(df_slice['EMA20'], color='blue', width=1.5),
            mpf.make_addplot(df_slice['EMA50'], color='orange', width=1.5),
            mpf.make_addplot(df_slice['BB_LOWER'], color='gray', alpha=0.5),
            mpf.make_addplot(df_slice['BB_UPPER'], color='gray', alpha=0.5)
        ]
        
        custom_style = mpf.make_mpf_style(
            base_mpf_style='charles', 
            gridstyle='', 
            facecolor='white', 
            figcolor='white', 
            edgecolor='black'
        )
        
        # scale_padding=0.0 ekledik ki kenarlardan gereksiz boşluk bırakmasın, yapay zeka mumları net görsün.
        mpf_kwargs = dict(
            type='candle', 
            style=custom_style, 
            axisoff=True, 
            tight_layout=True, 
            scale_padding=0.0,
            addplot=ekstra_cizgiler
        )
        
        yol = "canli_analiz.png"
        mpf.plot(df_slice, **mpf_kwargs, savefig=dict(fname=yol, dpi=85, format='png', bbox_inches='tight'))
        plt.close('all')
        
        return yol, df['close'].iloc[-1], df
    except Exception as e:
        print(f"⚠️ Grafik Hatası: {e}")
        return None, None, None

def acil_durum_bekcisi(fiyat):
    """Her saniye fiyatı kontrol edip hedeflere ulaşıldıysa tetiğe basan mekanizma."""
    cuzdan = port_man.cuzdan_yukle()
    pos = cuzdan.get("acik_islem")
    
    if pos:
        # P/L Formülü: $$P/L = \frac{Price_{current} - Price_{entry}}{Price_{entry}} \times 100$$
        pnl = ((fiyat - pos["giris_fiyati"]) / pos["giris_fiyati"]) * 100
        if pos["tip"] == "SELL": pnl *= -1

        # Satış Koşulları (BUY için)
        if pos["tip"] == "BUY":
            if fiyat >= pos["tp"] or fiyat <= pos["sl"]:
                print(f"🎯 HEDEF GÖRÜLDÜ! Fiyat: {fiyat} | P/L: %{pnl:.2f}")
                port_man.islem_kapat(fiyat, "WATCHDOG_EXIT")
                tel_mod.mesaj_gonder(f"💰 *ACİL SATIŞ GERÇEKLEŞTİ!* \nFiyat: {fiyat} | Sonuç: %{pnl:.2f}")
                return True
    return False

def tekil_analiz_yap():
    """15 dakikada bir çalışan V6 Elite analiz motoru."""
    coin = tel_mod.ayarlar["target_coin"]
    mod = tel_mod.ayarlar["mod"]
    
    # 1. GÖRSEL VE SAYISAL VERİ HAZIRLIĞI
    yol, fiyat, df = grafik_hazirla(coin, "15m")
    if not yol: return

    sayisal_vektor = sayisal_veri.verileri_cek(borsa, coin)
    atr_yuzde = sayisal_vektor[2] # Sayısal vektörden taze ATR'yi al

    # 2. RİSK VE VOLATİLİTE KONTROLÜ
    print(f"🔍 [Risk Analizi] Anlık Piyasa Volatilitesi (ATR): %{atr_yuzde:.2f}")
    if atr_yuzde < 0.25:
        tel_mod.mesaj_gonder(f"⚠️ *Piyasa Çok Yatay!*\n{coin} için volatilite (%{atr_yuzde:.2f}) çok düşük. Analiz pas geçildi.")
        return

    # 3. ESKİ İŞLEM KONTROLÜ (Coin değiştiyse kapat)
    cuzdan = port_man.cuzdan_yukle()
    if cuzdan.get("acik_islem") and cuzdan["acik_islem"]["coin"] != coin:
        try:
            f = borsa.fetch_ticker(cuzdan["acik_islem"]["coin"])['last']
            port_man.islem_kapat(f, "COIN_DEGISIMI")
        except: pass

    # 4. YAPAY ZEKA VE DUYGU ANALİZİ (Değişkenler burada tanımlanıyor)
    tespit, guven, sinyal = decision_engine.sistemi_test_et_donuslu(yol, sayisal_vektor)
    duygu, d_skor, ham_etki = sentiment_module.haber_analizi_yap(coin)
    
    # 5. ASİMETRİK HEDEF HESAPLAMA (Risk: 1.5x ATR | Ödül: 3x Risk)
    temel_risk = max(atr_yuzde, 0.30)
    risk_yuzdesi = temel_risk * 1.5 
    tp_yuzdesi = risk_yuzdesi * 3.0 
    sl_yuzdesi = risk_yuzdesi

    islem_tipi = None
    if "BUY" in sinyal.upper():
        tp_fiyat = fiyat * (1 + tp_yuzdesi / 100)
        sl_fiyat = fiyat * (1 - sl_yuzdesi / 100)
        islem_tipi = "BUY"
    elif "SELL" in sinyal.upper():
        tp_fiyat = fiyat * (1 - tp_yuzdesi / 100)
        sl_fiyat = fiyat * (1 + sl_yuzdesi / 100)
        islem_tipi = "SELL"

    # 6. İŞLEM GİRİŞ MANTIĞI
    cuzdan = port_man.cuzdan_yukle() 
    pnl_metni = ""

    if cuzdan.get("acik_islem"):
        pos = cuzdan["acik_islem"]
        pnl = ((fiyat - pos["giris_fiyati"]) / pos["giris_fiyati"]) * 100
        if pos["tip"] == "SELL": pnl *= -1
        pnl_metni = f"\n\n🔔 *İŞLEM:* %{pnl:.2f} {'📈' if pnl>0 else '📉'}\n🛑 SL: {pos['sl']:.2f} | ✅ TP: {pos['tp']:.2f}"

    elif tel_mod.ayarlar["trading_aktif"] and islem_tipi:
        esik = 50 if mod == "KAMIKAZE" else 75
        
        if guven >= esik:
            # İşlemi açarken sl_fiyat'ı hem SL hem de sl_ilk olarak gönderiyoruz
            if port_man.islem_ac(
                coin, fiyat, tel_mod.ayarlar["butce"], islem_tipi, 
                sl_fiyat, tp_fiyat, mod, 
                sl_yuzdesi, tp_yuzdesi, sl_fiyat
            ):
                tel_mod.mesaj_gonder(
                    f"🚀 *İŞLEME GİRİLDİ ({islem_tipi})*\n"
                    f"🧠 Güven: %{guven:.1f}\n"
                    f"📍 Fiyat: {fiyat:.4f}\n"
                    f"🎯 TP: {tp_fiyat:.4f} | 🛑 SL: {sl_fiyat:.4f}"
                )

    # 7. RAPORLAMA
    rapor = (f"📊 *{coin} DERİN ANALİZ*\n🛡️ Mod: {mod}\n━━━━━━━━━━━━━━\n"
             f"📍 Fiyat: {fiyat:.2f} USDT\n🧠 AI: {tespit} (%{guven:.2f})\n"
             f"🌍 Duygu: {duygu} ({d_skor})\n"
             f"🎯 Karar: `{sinyal}`{pnl_metni}")
    tel_mod.resim_gonder(yol, rapor)

def baslangic_kontrolleri():
    """Açılışta cüzdanı ve borsa bağlantısını selamlar."""
    print("⚙️ Sistem kontrolleri başlatılıyor...")
    port_man.bakiye_senkronize_et()
    cuzdan = port_man.cuzdan_yukle()
    nakit = cuzdan.get("bakiye", 0.0)
    print(f"💰 Bot Hazır! Mevcut Nakit: {nakit:.2f} USDT")
    tel_mod.mesaj_gonder(f"🤖 *Guru AI Başlatıldı!*\n💰 Bakiye: {nakit:.2f} USDT")

def analiz_motoru(coin, mod="KAMIKAZE"):

    

    try:

        
        # 1. BOTUN O COİNE BAKTIĞINI KANITLA
        print(f"🔍 {coin} verisi çekiliyor...", end=" ", flush=True) 
        
        tf = "5m" if mod == "KAMIKAZE" else "15m"
        yol, fiyat, df = grafik_hazirla(coin, tf)
        
        # 2. EĞER GRAFİK ÇİZİLEMEZSE SESSİZCE KAÇMASINI ENGELLE
        if not yol: 
            print("❌ GRAFİK HATASI! (Pas)", flush=True)
            return

        tf = "5m" if mod == "KAMIKAZE" else "15m"
        yol, fiyat, df = grafik_hazirla(coin, tf)
        if not yol: return

        s_vektor = sayisal_veri.verileri_cek(borsa, coin)
        rsi_val, atr_yuzde = s_vektor[0], s_vektor[2]
        tespit, guven, sinyal = decision_engine.sistemi_test_et_donuslu(yol, s_vektor)
        
        dolu_kutu = int(guven / 10)
        p_bar = "█" * dolu_kutu + "░" * (10 - dolu_kutu)
        zaman = datetime.now().strftime('%H:%M:%S')
        
        if guven >= 75 and ("BUY" in sinyal or "SELL" in sinyal):
            risk_m = max(atr_yuzde, 0.30) * 1.5
            tp_f = fiyat * (1 + (risk_m * 3)/100) if "BUY" in sinyal else fiyat * (1 - (risk_m * 3)/100)
            sl_f = fiyat * (1 - risk_m/100) if "BUY" in sinyal else fiyat * (1 + risk_m/100)

            if port_man.islem_ac(coin, fiyat, tel_mod.ayarlar["butce"], sinyal, sl_f, tp_f, mod, risk_m, risk_m*3, sl_f):
                # flush=True anında terminale basar!
                print(f"\n[{zaman}] 🚀 {coin:<10} [{p_bar}] AI:%{guven:05.1f} | RSI:{rsi_val:05.2f} | 🎯 TETİK ÇEKİLDİ!", flush=True)
                
                rapor = (f"🎯 *SNIPER GİRİŞ:* {coin}\n━━━━━━━━━━━━━━\n"
                         f"📍 Fiyat: {fiyat:.4f}\n🧠 AI: %{guven:.1f} ({tespit})\n"
                         f"🛑 SL: {sl_f:.4f} | ✅ TP: {tp_f:.4f}")
                tel_mod.resim_gonder(yol, rapor)
        else:
            # Saniyeler içinde terminale bilgi düşer
            print(f"[{zaman}] 📡 {coin:<10} [{p_bar}] AI:%{guven:05.1f} | RSI:{rsi_val:05.2f} | ⏳ Pas ({tespit})", flush=True)

    except Exception as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ {coin} Hatası: {e}", flush=True)
def ana_dongu():
    """Botun Hareket Merkezi: 5 Koldan Sessiz Takip Yapar."""
    tel_mod.dinlemeyi_baslat()
    time.sleep(2)
    tel_mod.mesaj_gonder("🤖 *GURU AI V23 Multi-Sniper Aktif!* \nSpam engellendi, sadece aksiyon raporlanacak.")
    
    sayac, k_timer = 0, time.time()
    
    while True:
        try:
            is_aktif = tel_mod.ayarlar.get("trading_aktif", False)
            aktif_mod = tel_mod.ayarlar.get("mod", "NORMAL")
            manual_mi = tel_mod.ayarlar.get("manual_trigger", False)
            
            # 🛡️ 1. KASA KORUMA KONTROLÜ (1400 / 650)
            if is_aktif and aktif_mod == "KAMIKAZE":
                baslangic = tel_mod.ayarlar.get("baslangic_bakiyesi", 1000)
                durum, toplam_varlik = port_man.kasa_durumu_kontrol(baslangic, 40, 35) # +%40, -%35
                
                if durum == "TARGET_REACHED":
                    tel_mod.mesaj_gonder(f"💰 *HEDEF 1400 TAMAMLANDI!* \nToplam Varlık: {toplam_varlik:.2f}\nSistem durduruluyor.")
                    tel_mod.ayarlar["trading_aktif"] = False
                elif durum == "MAX_LOSS_REACHED":
                    tel_mod.mesaj_gonder(f"🛑 *KASA KORUMA AKTİF!* \nToplam Varlık: {toplam_varlik:.2f}\nZarar durduruldu.")
                    tel_mod.ayarlar["trading_aktif"] = False

            # 📡 2. SESSİZ ÇOKLU RADAR TARAMASI
            if tel_mod.ayarlar.get("trading_aktif") and (sayac <= 0 or manual_mi):
                radar = tel_mod.ayarlar.get("radar_listesi", [])
                
                for coin in radar:
                    cuzdan = port_man.cuzdan_yukle()
                    # İşlem limitini (5) ve coinin zaten açık olup olmadığını kontrol et
                    if len(cuzdan.get("aktif_pozisyonlar", [])) < 5 and not port_man.bu_coin_acik_mi(coin):
                        analiz_motoru(coin, aktif_mod)
                
                tel_mod.ayarlar["manual_trigger"] = False
                sayac = 60 # 5 dakikada bir tarar
            
            # 🚀 3. SÜREKLİ TAKİP (SUPERVISOR)
            cuzdan = port_man.cuzdan_yukle()
            for islem in cuzdan.get("aktif_pozisyonlar", []):
                try:
                    f = borsa.fetch_ticker(islem["coin"])['last']
                    durum_sup, veri_sup = ai_supervisor.denetle(islem, f, 0)
                    
                    if durum_sup == "CLOSE":
                        port_man.islem_kapat(islem["coin"], f, veri_sup)
                        tel_mod.mesaj_gonder(f"✅ *POZİSYON KAPANDI:* {islem['coin']}\nNeden: {veri_sup}\nFiyat: {f}")
                    elif durum_sup == "UPDATE_SL":
                        if port_man.sl_guncelle(islem["coin"], veri_sup):
                            tel_mod.mesaj_gonder(f"🛡️ *KÂR KİLİTLENDİ:* {islem['coin']} \nYeni SL: {veri_sup:.4f}")
                except Exception as e:
                    print(f"⚠️ {islem['coin']} Bekçi Hatası: {e}")

            # 📊 4. SAATLİK SESSİZ RAPOR (İsteğe bağlı)
            if tel_mod.ayarlar.get("trading_aktif") and (time.time() - k_timer) >= 3600:
                c_guncel = port_man.cuzdan_yukle()
                p_sayisi = len(c_guncel.get("aktif_pozisyonlar", []))
                tel_mod.mesaj_gonder(f"📊 *SAATLİK DURUM*\nNakit: {c_guncel['bakiye']:.2f} USDT\nAçık İşlem: {p_sayisi}/5")
                k_timer = time.time()

        except Exception as e:
            print(f"⚠️ Kritik Ana Döngü Hatası: {e}")
            time.sleep(5)

        time.sleep(1)
if __name__ == "__main__":
    ana_dongu()