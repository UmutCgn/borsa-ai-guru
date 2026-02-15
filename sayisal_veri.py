import pandas as pd
import pandas_ta as ta

def verileri_cek(borsa_objesi, sembol):
    """
    AI'ın Sayısal Kolu (Numerical Branch) için JSON dataset ile %100 uyumlu 7'li veriyi hesaplar.
    """
    try:
        # 15m zaman dilimi kullanıyoruz
        ohlcv = borsa_objesi.fetch_ohlcv(sembol, timeframe='15m', limit=50)
        df = pd.DataFrame(ohlcv, columns=['Date','Open','High','Low','Close','Volume'])
        
        df['ATR'] = ta.atr(df['High'], df['Low'], df['Close'], length=14)
        df['RSI'] = ta.rsi(df['Close'], length=14)
        df.dropna(inplace=True)
        
        curr = df.iloc[-1]
        
        # V6 Dataset Formatı: [tf_id, rsi, atr_yuzde, volume_z_score, body_size, upper_wick, lower_wick]
        # 15m için tf_id = 1.0 kabul etmiştik
        sayisal_vektor = [
            1.0, 
            curr['RSI'], 
            (curr['ATR'] / curr['Close']) * 100, 
            0.0, 
            abs(curr['Open'] - curr['Close']), 
            curr['High'] - max(curr['Open'], curr['Close']), 
            min(curr['Open'], curr['Close']) - curr['Low']
        ]
        
        print(f"📊 [Sayısal Kol] V6 Elite Vektörü Hazır: {sayisal_vektor[1]:.2f} RSI")
        return sayisal_vektor
        
    except Exception as e:
        print(f"⚠️ Sayısal Veri Hatası: {e}")
        return [1.0, 50.0, 0.5, 0.0, 0.0, 0.0, 0.0]