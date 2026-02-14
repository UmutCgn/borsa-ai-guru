import os
import ccxt
import pandas as pd
import pandas_ta as ta
import mplfinance as mpf
import time
import json

# --- MÜHENDİSLİK AYARLARI ---
RESIM_SINIRI_PER_CLASS = 1500  # Her formasyon için hedef örnek sayısı
# Saniyelik işlemler için '1s' eklendi, ancak borsanın geçmiş veri limitine dikkat!
ZAMAN_DILIMLERI = ['1s', '15m', '1h', '4h', '1d'] 
DATASET_YOLU = "dataset"

# Zaman Dilimi Ağırlıklandırma (AI'ın zamanı öğrenmesi için tf_id)
TF_MAP = {"1s": 1, "15m": 2, "1h": 3, "4h": 4, "1d": 5}

def get_top_50_coins():
    """Binance üzerindeki en hacimli 50 USDT çiftini dinamik olarak çeker."""
    try:
        borsa = ccxt.binance()
        tickers = borsa.fetch_tickers()
        # Hacme göre sırala ve kaldıraçlı (UP/DOWN) olanları ele
        sorted_tickers = sorted(tickers.values(), key=lambda x: x.get('quoteVolume', 0), reverse=True)
        return [t['symbol'] for t in sorted_tickers if '/USDT' in t['symbol'] and "UP/" not in t['symbol'] and "DOWN/" not in t['symbol']][:50]
    except Exception as e:
        print(f"⚠️ Coin listesi alınamadı: {e}")
        return ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'XRP/USDT']

COIN_LISTESI = get_top_50_coins()

def madenciligi_baslat():
    print(f"🚀 [GURU MULTI-MODAL] Madencilik Başlıyor...")
    print(f"📊 Tarama Alanı: {len(COIN_LISTESI)} Coin x {len(ZAMAN_DILIMLERI)} Zaman Dilimi")
    
    if not os.path.exists(DATASET_YOLU):
        os.makedirs(DATASET_YOLU)
    
    # API sınırlarına takılmamak için RateLimit aktif
    borsa = ccxt.binance({'enableRateLimit': True})
    
    for symbol in COIN_LISTESI:
        for tf in ZAMAN_DILIMLERI:
            try:
                print(f"🔍 İşleniyor: {symbol} | {tf}")
                # Geçmişe dönük maksimum veriyi (1500 mum) çekiyoruz
                ohlcv = borsa.fetch_ohlcv(symbol, timeframe=tf, limit=1500)
                df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                df.set_index('timestamp', inplace=True)
                
                # --- SAYISAL GÖSTERGELER ---
                df['RSI'] = ta.rsi(df['close'], length=14)
                df['ATR'] = ta.atr(df['high'], df['low'], df['close'], length=14)
                # Hacim Z-Score (Son 20 muma göre hacim patlaması)
                df['VOL_MEAN'] = df['volume'].rolling(20).mean()
                df['VOL_STD'] = df['volume'].rolling(20).std()
                
                # Tüm Mum Formasyonlarını Tespit Et (70+ Formasyon)
                cdl_df = df.ta.cdl_pattern(name="all")
                df_combined = pd.concat([df, cdl_df], axis=1)
                
                for col in cdl_df.columns:
                    # Formasyon tespiti (Boğa=100, Ayı=-100)
                    matches = df_combined[df_combined[col] != 0]
                    if matches.empty: continue
                    
                    class_name = col.replace('CDL_', '')
                    klasor = os.path.join(DATASET_YOLU, class_name)
                    if not os.path.exists(klasor): os.makedirs(klasor)
                    
                    mevcut_sayi = len(os.listdir(klasor)) // 2 # PNG+JSON olduğu için
                    if mevcut_sayi >= RESIM_SINIRI_PER_CLASS: continue
                    
                    for index, row in matches.iterrows():
                        if mevcut_sayi >= RESIM_SINIRI_PER_CLASS: break
                        
                        pos = df_combined.index.get_loc(index)
                        if pos < 20: continue # Teknik göstergelerin oturması için
                        
                        # --- 🚀 SAYISAL VEKTÖR (JSON) ---
                        # AI'ın "Zaman Algısını" ve "Hacim Gücünü" öğrendiği yer burası
                        v_zscore = (row['volume'] - row['VOL_MEAN']) / row['VOL_STD'] if row['VOL_STD'] > 0 else 0
                        
                        sayisal_veriler = {
                            "tf_id": TF_MAP.get(tf, 0), # Zamanın ağırlığı
                            "symbol": symbol,
                            "formasyon": class_name,
                            "yon": "BULL" if row[col] > 0 else "BEAR",
                            "rsi": float(row['RSI']) if not pd.isna(row['RSI']) else 50.0,
                            "atr_yuzde": float((row['ATR'] / row['close']) * 100) if not pd.isna(row['ATR']) else 0.0,
                            "volume_z_score": float(v_zscore),
                            "body_size": float(abs(row['open'] - row['close'])),
                            "upper_wick": float(row['high'] - max(row['open'], row['close'])),
                            "lower_wick": float(min(row['open'], row['close']) - row['low'])
                        }
                        
                        # --- 🖼️ GÖRSEL VERİ (PNG) ---
                        start = max(0, pos - 12) # Biraz daha geniş perspektif
                        end = min(len(df_combined), pos + 4)
                        kesit = df_combined.iloc[start:end]
                        
                        file_id = f"{symbol.replace('/','_')}_{tf}_{pos}_{int(row[col])}"
                        img_path = os.path.join(klasor, f"{file_id}.png")
                        json_path = os.path.join(klasor, f"{file_id}.json")
                        
                        if os.path.exists(img_path): continue
                        
                        # Grafiği tertemiz (eksensiz) kaydet
                        mpf.plot(kesit, type='candle', style='charles', axisoff=True, 
                                 savefig=dict(fname=img_path, dpi=85, bbox_inches='tight'))
                        
                        # Sayısal eşini kaydet
                        with open(json_path, 'w') as f:
                            json.dump(sayisal_veriler, f, indent=4)
                        
                        mevcut_sayi += 1
                
                print(f"✅ {symbol} | {tf} tamamlandı. Sınıf sayıları güncellendi.")
                time.sleep(0.3) # API ban koruması
                
            except Exception as e:
                print(f"⚠️ {symbol} hatası: {e}")
                continue

if __name__ == "__main__":
    t_start = time.time()
    madenciligi_baslat()
    print(f"\n💎 MADENCİLİK BİTTİ! Toplam Süre: {(time.time()-t_start)/60:.2f} dakika.")