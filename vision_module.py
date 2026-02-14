import ccxt
import pandas as pd
import pandas_ta as ta
import mplfinance as mpf
import cv2

def veri_cek_ve_grafik_olustur(sembol='BTC/USDT', zaman_dilimi='15m', limit=96):
    print(f"📡 {sembol} için canlı kalem & kağıt grafiği çiziliyor...")
    
    borsa = ccxt.binance()
    mumlar = borsa.fetch_ohlcv(sembol, timeframe=zaman_dilimi, limit=limit)
    
    df = pd.DataFrame(mumlar, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df.set_index('timestamp', inplace=True)
    
    # --- CANLI ÇİZİMLER ---
    df['EMA20'] = ta.ema(df['close'], length=20)
    df['EMA50'] = ta.ema(df['close'], length=50)
    bbands = ta.bbands(df['close'], length=20, std=2)
    if bbands is not None:
        df = pd.concat([df, bbands], axis=1)
        
    df.dropna(inplace=True)
    
    ek_cizgiler = [
        mpf.make_addplot(df['EMA20'], color='blue', width=1.5),
        mpf.make_addplot(df['EMA50'], color='orange', width=1.5)
    ]
    # Bollinger bantları varsa ekle
    if bbands is not None:
        ek_cizgiler.extend([
            mpf.make_addplot(df[bbands.columns[0]], color='gray', alpha=0.5),
            mpf.make_addplot(df[bbands.columns[2]], color='gray', alpha=0.5)
        ])

    dosya_adi = 'aktif_grafik.png'
    mpf.plot(df, type='candle', style='charles', axisoff=True, addplot=ek_cizgiler, savefig=dosya_adi)
    return dosya_adi

def grafigi_hazirla(dosya_yolu='aktif_grafik.png'):
    # V6 modelimiz MobileNet renkli görüntü (RGB) sevdiği için griye çevirmeyi (cv2.COLOR_BGR2GRAY) İPTAL ETTİK.
    # Çizgilerin renklerini (mavi EMA, turuncu EMA) görebilmesi çok önemli!
    img = cv2.imread(dosya_yolu)
    if img is None: return None

    yukseklik, genislik, _ = img.shape
    baslangic_x = int(genislik * 0.40) 
    son_yuzde_atmis = img[:, baslangic_x:]
    
    islenmis_dosya = 'islenmis_grafik.png'
    cv2.imwrite(islenmis_dosya, son_yuzde_atmis) # Renkli kaydediyoruz
    return islenmis_dosya