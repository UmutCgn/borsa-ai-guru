import os
import ccxt
import pandas as pd
import pandas_ta as ta
import mplfinance as mpf
import time
import json

DATASET_YOLU = "v6_dataset"
SINIFLAR = ["BUY", "SELL", "HOLD"]
# Zaman dilimlerini genişlettik (Düşüşleri daha hızlı yakalamak için)
ZAMAN_DILIMLERI = ['5m', '15m', '30m', '1h', '2h', '4h'] 
HEDEF_SAYI = 5000

def en_volatiliteli_100_coini_al(borsa):
    print("🌪️ Binance üzerinden EN VOLATİL (Oynak) 100 coin seçiliyor...")
    try:
        tickers = borsa.fetch_tickers()
        adaylar = []
        for symbol, data in tickers.items():
            if '/USDT' in symbol and "UP/" not in symbol and "DOWN/" not in symbol:
                vol = data.get('quoteVolume', 0)
                # Mutlak yüzde değişimi (Düşüş veya çıkış fark etmez, hareketlilik arıyoruz)
                degisim = abs(data.get('percentage', 0)) 
                
                if vol > 2000000: # En az 2 Milyon $ hacim (Ölü coinlerde sahte formasyon olmasın)
                    adaylar.append({'symbol': symbol, 'volatilite': degisim})
        
        # En oynak olanlara göre sırala
        sirali = sorted(adaylar, key=lambda x: x['volatilite'], reverse=True)
        secilenler = [t['symbol'] for t in sirali][:100]
        print(f"🔥 Radar Kilitlendi! En tehlikeli coinler: {secilenler[:5]}...")
        return secilenler
    except Exception as e:
        print(f"⚠️ Hata: {e}")
        return ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'WIF/USDT']

def baslat():
    print("🚀 V6 ULTRA MADENCİ: Volatilite Radarı Aktif...")
    
    for s in SINIFLAR:
        os.makedirs(os.path.join(DATASET_YOLU, s), exist_ok=True)
        
    borsa = ccxt.binance({'enableRateLimit': True})
    coinler = en_volatiliteli_100_coini_al(borsa)
    
    guclu_formasyonlar = [
        'CDL_ENGULFING', 'CDL_SHOOTINGSTAR', 'CDL_EVENINGSTAR', 
        'CDL_DARKCLOUDCOVER', 'CDL_GRAVESTONEDOJI', 'CDL_HANGINGMAN', 
        'CDL_3BLACKCROWS', 'CDL_BELTHOLD', 'CDL_HARAMI', 'CDL_MARUBOZU',
        'CDL_HAMMER', 'CDL_MORNINGSTAR', 'CDL_PIERCING', 'CDL_3WHITESOLDIERS'
    ]
    
    for symbol in coinler:
        for tf in ZAMAN_DILIMLERI:
            try:
                buy_sayisi = len(os.listdir(os.path.join(DATASET_YOLU, "BUY"))) // 2
                sell_sayisi = len(os.listdir(os.path.join(DATASET_YOLU, "SELL"))) // 2
                hold_sayisi = len(os.listdir(os.path.join(DATASET_YOLU, "HOLD"))) // 2
                
                if buy_sayisi >= HEDEF_SAYI and sell_sayisi >= HEDEF_SAYI and hold_sayisi >= HEDEF_SAYI:
                    print("🎉 TÜM KOTALAR DOLDU! Veri setin eğitime hazır.")
                    return

                print(f"📡 İşleniyor: {symbol} | {tf} | BUY:{buy_sayisi}, SELL:{sell_sayisi}, HOLD:{hold_sayisi}")
                
                ohlcv = borsa.fetch_ohlcv(symbol, timeframe=tf, limit=1000)
                df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                df.set_index('timestamp', inplace=True)
                
                df['EMA20'] = ta.ema(df['close'], length=20)
                df['EMA50'] = ta.ema(df['close'], length=50)
                bbands = ta.bbands(df['close'], length=20, std=2)
                if bbands is not None: df = pd.concat([df, bbands], axis=1)
                    
                df['RSI'] = ta.rsi(df['close'], length=14)
                df['ATR'] = ta.atr(df['high'], df['low'], df['close'], length=14)
                df.dropna(inplace=True)

                cdl_df = df.ta.cdl_pattern(name="all")
                df_combined = pd.concat([df, cdl_df], axis=1).dropna()

                for index, row in df_combined.iterrows():
                    pos = df_combined.index.get_loc(index)
                    if pos < 20 or pos > len(df_combined) - 5: continue
                    
                    sinif = "HOLD"
                    is_sell, is_buy = False, False
                    
                    for col in guclu_formasyonlar:
                        if col in df_combined.columns:
                            if row[col] < 0: is_sell = True
                            elif row[col] > 0: is_buy = True

                    if is_sell: sinif = "SELL"
                    elif is_buy: sinif = "BUY"
                    
                    if sinif == "BUY" and buy_sayisi >= HEDEF_SAYI: continue
                    if sinif == "SELL" and sell_sayisi >= HEDEF_SAYI: continue
                    if sinif == "HOLD":
                        if hold_sayisi >= HEDEF_SAYI or pos % 15 != 0: continue

                    # Yeni zaman dilimlerine göre AI için ağırlıklandırma
                    tf_map = {'5m': 0.5, '15m': 1.0, '30m': 1.5, '1h': 2.0, '2h': 2.5, '4h': 3.0}
                    tf_degeri = tf_map.get(tf, 1.0)

                    sayisal = {
                        "tf_id": tf_degeri, "rsi": row['RSI'], "atr_yuzde": (row['ATR']/row['close'])*100,
                        "volume_z_score": 0.0, "body_size": abs(row['open']-row['close']),
                        "upper_wick": row['high'] - max(row['open'], row['close']),
                        "lower_wick": min(row['open'], row['close']) - row['low']
                    }

                    start, end = max(0, pos - 15), min(len(df_combined), pos + 2)
                    kesit = df_combined.iloc[start:end]
                    
                    ek_cizgiler = [
                        mpf.make_addplot(kesit['EMA20'], color='blue', width=1.5),
                        mpf.make_addplot(kesit['EMA50'], color='orange', width=1.5),
                        mpf.make_addplot(kesit[bbands.columns[0]], color='gray', alpha=0.5),
                        mpf.make_addplot(kesit[bbands.columns[2]], color='gray', alpha=0.5)
                    ]
                    
                    dosya_adi = f"{symbol.replace('/','_')}_{tf}_{pos}"
                    img_yol = os.path.join(DATASET_YOLU, sinif, f"{dosya_adi}.png")
                    json_yol = os.path.join(DATASET_YOLU, sinif, f"{dosya_adi}.json")
                    
                    if not os.path.exists(img_yol):
                        mpf.plot(kesit, type='candle', style='charles', axisoff=True, addplot=ek_cizgiler,
                                 savefig=dict(fname=img_yol, dpi=85, bbox_inches='tight'))
                        with open(json_yol, 'w') as f: json.dump(sayisal, f)
                        
                        if sinif == "BUY": buy_sayisi += 1
                        elif sinif == "SELL": sell_sayisi += 1
                        elif sinif == "HOLD": hold_sayisi += 1

                time.sleep(0.2)
            except Exception as e:
                pass

if __name__ == "__main__":
    baslat()