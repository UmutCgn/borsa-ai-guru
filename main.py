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
    """V6 Dataset standardında 17 mumluk çizgili grafik ve ADX/EMA50 verisi üretir."""
    try:
        ohlcv = borsa.fetch_ohlcv(sembol, timeframe=tf, limit=150)
        import pandas as pd; import mplfinance as mpf; import pandas_ta as ta
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('timestamp', inplace=True)
        
        # Çizgiler ve İndikatörler
        df['EMA20'] = ta.ema(df['close'], length=20)
        df['EMA50'] = ta.ema(df['close'], length=50)
        bbands = ta.bbands(df['close'], length=20, std=2)
        df['BB_LOWER'] = bbands.iloc[:, 0]
        df['BB_UPPER'] = bbands.iloc[:, 2]
        
        # 🚨 LIVE_SIM UYUMU: ADX (Trend Gücü) HESAPLAMASI 🚨
        adx_df = ta.adx(df['high'], df['low'], df['close'])
        df['ADX'] = adx_df['ADX_14'] if adx_df is not None else 0.0
        
        df.dropna(inplace=True)
        df_slice = df.tail(17) 
        
        ekstra_cizgiler = [
            mpf.make_addplot(df_slice['EMA20'], color='blue', width=1.5),
            mpf.make_addplot(df_slice['EMA50'], color='orange', width=1.5),
            mpf.make_addplot(df_slice['BB_LOWER'], color='gray', alpha=0.5),
            mpf.make_addplot(df_slice['BB_UPPER'], color='gray', alpha=0.5)
        ]
        
        custom_style = mpf.make_mpf_style(base_mpf_style='charles', gridstyle='', facecolor='white', figcolor='white', edgecolor='black')
        mpf_kwargs = dict(type='candle', style=custom_style, axisoff=True, tight_layout=True, scale_padding=0.0, addplot=ekstra_cizgiler)
        
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
        # Alt satıra inmeden, aynı satırda işlem başlatıldığını gösterir
        print(f"🔍 {coin:<10} inceleniyor... ", end="\r", flush=True) 
        
        tf = "5m" if mod == "KAMIKAZE" else "15m"
        yol, fiyat, df = grafik_hazirla(coin, tf)
        
        if not yol: 
            print(f"❌ {coin:<10} GRAFİK HATASI! (Pas)", flush=True); return
            
        s_vektor = sayisal_veri.verileri_cek(borsa, coin)
        
        # 🚨 HATA DÜZELTİLDİ: s_vektor[0] (sabit 1.0) yerine gerçek RSI olan s_vektor[1] kullanıldı!
        rsi_val, atr_yuzde = s_vektor[1], s_vektor[2] 
        tespit, guven, sinyal = decision_engine.sistemi_test_et_donuslu(yol, s_vektor)
        
        # 🚨 LIVE_SIM FİLTRE VERİLERİ 🚨
        adx_val = df['ADX'].iloc[-1]
        ema50_val = df['EMA50'].iloc[-1]
        
        d_kutu = int(guven / 10)
        p_bar = "█" * d_kutu + "░" * (10 - d_kutu)
        zaman = datetime.now().strftime('%H:%M:%S')
        
        # --- KATI GİRİŞ KURALLARI (Simülasyon Birebir Klonu) ---
        onay = False
        pas_sebebi = tespit # Varsayılan sebep yapay zekanın kendi kararı
        
        if guven >= 75:
            if adx_val > 20: # Trend yeterince güçlü mü?
                if "BUY" in sinyal and fiyat > ema50_val: # Long için trend üstü mü?
                    onay = True
                elif "SELL" in sinyal and fiyat < ema50_val: # Short için trend altı mı?
                    onay = True
                else:
                    pas_sebebi = "EMA50 Trendine Ters"
            else:
                pas_sebebi = "ADX<20 (Hacimsiz/Yatay)"

        # --- TETİĞİ ÇEK ---
        if onay:
            risk_m = max(atr_yuzde, 0.30) * 1.5
            tp_f = fiyat * (1 + (risk_m * 3)/100) if "BUY" in sinyal else fiyat * (1 - (risk_m * 3)/100)
            sl_f = fiyat * (1 - risk_m/100) if "BUY" in sinyal else fiyat * (1 + risk_m/100)

            if port_man.islem_ac(coin, fiyat, tel_mod.ayarlar["butce"], sinyal, sl_f, tp_f, mod, risk_m, risk_m*3, sl_f):
                # Başarılı girişi zengin formatta ekrana bas
                print(f"[{zaman}] 🚀 {coin:<10} [{p_bar}] AI:%{guven:05.1f} | RSI:{rsi_val:05.2f} | ADX:{adx_val:05.2f} | 🎯 TETİK ÇEKİLDİ!", flush=True)
                
                rapor = (f"🎯 *SNIPER GİRİŞ:* {coin}\n━━━━━━━━━━━━━━\n"
                         f"📍 Fiyat: {fiyat:.4f}\n"
                         f"🧠 AI: %{guven:.1f} ({tespit})\n"
                         f"📈 ADX: {adx_val:.2f} (Güçlü) | 📉 EMA50 Trendi: ONAYLI\n"
                         f"🛑 SL: {sl_f:.4f} | ✅ TP: {tp_f:.4f}")
                tel_mod.resim_gonder(yol, rapor)
        else:
            # İşleme girilmediyse neden girilmediğini (\r ile "inceleniyor" yazısını silerek) ekrana bas
            print(f"[{zaman}] 📡 {coin:<10} [{p_bar}] AI:%{guven:05.1f} | RSI:{rsi_val:05.2f} | ADX:{adx_val:05.2f} | ⏳ Pas ({pas_sebebi})", flush=True)

    except Exception as e:
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] ❌ {coin} Analiz Hatası: {e}", flush=True)
def ana_dongu():
    tel_mod.dinlemeyi_baslat()
    time.sleep(2)
    tel_mod.mesaj_gonder("🤖 *GURU AI V23 Multi-Sniper Aktif!* \nLoglar terminalde akıyor.")
    sayac, k_timer = 0, time.time()
    
    while True:
        try:
            is_aktif = tel_mod.ayarlar.get("trading_aktif", False)
            manual_mi = tel_mod.ayarlar.get("manual_trigger", False)
            aktif_mod = tel_mod.ayarlar.get("mod", "NORMAL")
            
            # 1. Kasa Koruma
            if is_aktif and aktif_mod == "KAMIKAZE":
                baslangic = tel_mod.ayarlar.get("baslangic_bakiyesi", 1000)
                durum, toplam_v = port_man.kasa_durumu_kontrol(baslangic, 40, 35) 
                if durum == "TARGET_REACHED":
                    tel_mod.mesaj_gonder(f"💰 *HEDEF 1400 TAMAM!* Bakiye: {toplam_v:.2f}"); tel_mod.ayarlar["trading_aktif"] = False
                elif durum == "MAX_LOSS_REACHED":
                    tel_mod.mesaj_gonder(f"🛑 *KASA KORUMA!* Bakiye: {toplam_v:.2f}"); tel_mod.ayarlar["trading_aktif"] = False

            # 2. Çoklu Tarama Merkezi
            if is_aktif:
                if sayac <= 0 or manual_mi:
                    radar = tel_mod.ayarlar.get("radar_listesi", [])
                    if not radar:
                        print("\n⚠️ RADAR BOŞ! Telegram'dan /kesfet yapın.", flush=True); sayac = 10
                    else:
                        print(f"\n{'='*40}\n🔄 YENİ TARAMA ({datetime.now().strftime('%H:%M:%S')})\n{'='*40}", flush=True)
                        for coin in radar:
                            cuzdan = port_man.cuzdan_yukle()
                            if len(cuzdan.get("aktif_pozisyonlar", [])) < 5 and not port_man.bu_coin_acik_mi(coin):
                                analiz_motoru(coin, aktif_mod)
                        tel_mod.ayarlar["manual_trigger"] = False
                        sayac = 60 # 60 saniyede bir agresif tarama
            
            # 3. Bekçi (Supervisor) ve 🟢 CANLI PNL AKIŞI 🔴
            cuzdan = port_man.cuzdan_yukle()
            pozlar = cuzdan.get("aktif_pozisyonlar", [])
            
            if pozlar:
                canli_pnl_listesi = []
                for islem in pozlar:
                    try:
                        f = borsa.fetch_ticker(islem["coin"])['last']
                        
                        # --- CANLI EKRAN İÇİN PNL HESAPLAMA ---
                        oran = ((f - islem["giris_fiyati"]) / islem["giris_fiyati"]) * 100
                        if islem["tip"] == "SELL": oran *= -1
                        ikon = "🟢" if oran > 0 else "🔴"
                        canli_pnl_listesi.append(f"{islem['coin']} {ikon} %{oran:.2f}")

                        # --- BEKÇİ MÜDAHALESİ ---
                        durum_sup, veri_sup = ai_supervisor.denetle(islem, f, 0)
                        if durum_sup == "CLOSE":
                            port_man.islem_kapat(islem["coin"], f, veri_sup)
                            tel_mod.mesaj_gonder(f"✅ *KAPANDI:* {islem['coin']} \nNeden: {veri_sup}")
                            print(f"\n✅ {islem['coin']} KAPANDI: {veri_sup}", flush=True)
                        elif durum_sup == "UPDATE_SL":
                            if port_man.sl_guncelle(islem["coin"], veri_sup):
                                print(f"\n🛡️ {islem['coin']} Kâr kilitlendi! Yeni SL: {veri_sup}", flush=True)
                    except: pass
                
                # SADECE 5 SANİYEDE BİR EKRANA BAS Kİ ÇOK HIZLI AKIP GÖZÜ YORMASIN
                if is_aktif and sayac % 5 == 0:
                    durum_metni = " | ".join(canli_pnl_listesi)
                    print(f"👁️ [CANLI TAKİP] {durum_metni}", flush=True)
            else:
                # EĞER İÇERİDE İŞLEM YOKSA GERİ SAYIM YAP
                if is_aktif and sayac % 5 == 0:
                    print(f"⏳ Sonraki taramaya: {sayac:02d} sn... [İçerideki: 0/5]", flush=True)

        except Exception as e:
            print(f"\n⚠️ Döngü Hatası: {e}", flush=True); time.sleep(5)
            
        time.sleep(1); sayac -= 1
if __name__ == "__main__":
    ana_dongu()