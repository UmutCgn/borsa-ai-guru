import time, ccxt, os
import telegram_module as tel_mod
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
    """OHLCV verisini çeker ve analiz için görselleştirir."""
    try:
        ohlcv = borsa.fetch_ohlcv(sembol, timeframe=tf, limit=50)
        import pandas as pd; import mplfinance as mpf
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('timestamp', inplace=True)
        yol = "canli_analiz.png"
        mpf.plot(df, type='candle', style='charles', axisoff=True, savefig=dict(fname=yol, dpi=100, bbox_inches='tight'))
        return yol, df['close'].iloc[-1], df
    except Exception as e:
        print(f"⚠️ Grafik Hatası: {e}")
        return None, None

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
    """15 dakikada bir çalışan derin analiz motoru."""
    coin = tel_mod.ayarlar["target_coin"]
    mod = tel_mod.ayarlar["mod"]
    yol, fiyat, df = grafik_hazirla(coin, "15m")
    if not yol: return

    sayisal_vektor = sayisal_veri.verileri_cek(borsa, coin)
    
    print(f"🛠️ [SİSTEM TESTİ] AI'a gidecek ham vektör: {sayisal_vektor}")

    if risk_yoneticisi.piyasa_olumu_yasiyor_mu(df, fiyat, min_hareket_yuzdesi=0.25):
        tel_mod.mesaj_gonder(f"⚠️ *Piyasa Çok Yatay!*\n{coin} için volatilite çok düşük. Hatalı sinyal almamak için analiz pas geçildi.")
        return
    
    

    # 1. ESKİ İŞLEMİ KAPAT (Coin değiştiyse)
    cuzdan = port_man.cuzdan_yukle()
    if cuzdan.get("acik_islem") and cuzdan["acik_islem"]["coin"] != coin:
        try:
            f = borsa.fetch_ticker(cuzdan["acik_islem"]["coin"])['last']
            port_man.islem_kapat(f, "COIN_DEGISIMI")
        except: pass

    # 2. ANALİZLER (AI + Duygu Analizi)
    tespit, guven, sinyal = decision_engine.sistemi_test_et_donuslu(yol)
    duygu, d_skor = sentiment_module.haber_analizi_yap(coin)
    
    # --- DİNAMİK HEDEF HESAPLAMA ---
    kar_orani = tel_mod.ayarlar["kar_hedefi"] / 100
    zarar_orani = tel_mod.ayarlar["zarar_durur"] / 100
    
    tp_fiyat = fiyat * (1 + kar_orani)
    sl_fiyat = fiyat * (1 - zarar_orani)

    cuzdan = port_man.cuzdan_yukle() # Taze veriyi çek
    pnl_metni = ""

    # 3. İŞLEM TAKİBİ (Yedek Kontrol)
    if cuzdan.get("acik_islem"):
        pos = cuzdan["acik_islem"]
        pnl = ((fiyat - pos["giris_fiyati"]) / pos["giris_fiyati"]) * 100
        if pos["tip"] == "SELL": pnl *= -1
        pnl_metni = f"\n\n🔔 *İŞLEM:* %{pnl:.2f} {'📈' if pnl>0 else '📉'}\n🛑 SL: {pos['sl']:.2f} | ✅ TP: {pos['tp']:.2f}"

    # 4. YENİ İŞLEM GİRİŞİ (Parametreler tam eklendi)
    elif tel_mod.ayarlar["trading_aktif"]:
        esik = 50 if mod == "KAMIKAZE" else 85
        if "BUY" in sinyal.upper() and guven >= esik:
            if port_man.islem_ac(
                coin, fiyat, tel_mod.ayarlar["butce"], "BUY", 
                sl_fiyat, tp_fiyat, mod, 
                tel_mod.ayarlar["zarar_durur"], tel_mod.ayarlar["kar_hedefi"]
            ):
                tel_mod.mesaj_gonder(
                    f"🚀 *KAMİKAZE İŞLEME GİRDİ!*\n"
                    f"💰 Bütçe: {tel_mod.ayarlar['butce']} USDT\n"
                    f"🎯 Kar: %{tel_mod.ayarlar['kar_hedefi']} | 🛑 Stop: %{tel_mod.ayarlar['zarar_durur']}"
                )

    # 5. RAPORLAMA
    rapor = (f"📊 *{coin} DERİN ANALİZ*\n🛡️ Mod: {mod}\n━━━━━━━━━━━━━━\n"
             f"📍 Fiyat: {fiyat:.2f} USDT\n🧠 AI: {tespit} (%{guven:.2f})\n"
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

def ana_dongu():
    """Botun kalbi: Telegram, Bekçi ve Analiz burada senkronize olur."""
    tel_mod.dinlemeyi_baslat()
    time.sleep(2); tel_mod.yardim_mesaji(None)
    baslangic_kontrolleri()
    
    sayac, k_timer = 0, time.time()
    
    while True:
        # 🛡️ 1. GÜVENLİ DURDURMA (Kullanıcı /stop yazarsa)
        if tel_mod.ayarlar["durduruldu"]:
            cuzdan = port_man.cuzdan_yukle()
            if cuzdan.get("acik_islem"):
                try:
                    f = borsa.fetch_ticker(cuzdan["acik_islem"]["coin"])['last']
                    port_man.islem_kapat(f, "SAFE_SHUTDOWN")
                    tel_mod.mesaj_gonder(f"💰 *GÜVENLİ ÇIKIŞ:* Pozisyon {f} fiyatından nakde çevrildi.")
                except: pass
            print("🛑 Sistem kapatıldı.")
            break 

        # 🚀 2. SANİYELİK ACİL DURUM BEKÇİSİ (Watchdog)
        try:
            current_f = borsa.fetch_ticker(tel_mod.ayarlar["target_coin"])['last']
            if acil_durum_bekcisi(current_f):
                sayac = 0 # Satış olduysa hemen yeni fırsat için analizi tetikle
        except Exception as e:
            print(f"⚠️ Bekçi Hatası: {e}")

        # 📊 3. 30 SANİYE KAMIKAZE RAPORU
        simdi = time.time()
        if tel_mod.ayarlar["mod"] == "KAMIKAZE" and (simdi - k_timer) >= 30:
            cuzdan = port_man.cuzdan_yukle()
            if cuzdan.get("acik_islem"):
                try:
                    f = borsa.fetch_ticker(tel_mod.ayarlar["target_coin"])['last']
                    pnl = ((f - cuzdan["acik_islem"]["giris_fiyati"]) / cuzdan["acik_islem"]["giris_fiyati"]) * 100
                    tel_mod.mesaj_gonder(f"🚀 *PNL:* %{pnl:.2f} {'📈' if pnl>0 else '📉'}")
                except: pass
            k_timer = simdi

        # 🔍 4. PERİYODİK ANALİZ (15 Dakikada bir veya Manuel)
        if sayac <= 0 or tel_mod.ayarlar["manual_trigger"]:
            tekil_analiz_yap()
            tel_mod.ayarlar["manual_trigger"] = False
            sayac = DONGU_SURESI
        
        time.sleep(1) # CPU'yu yormadan her saniye denetle
        sayac -= 1

if __name__ == "__main__":
    ana_dongu()