import pandas as pd
import numpy as np


def hesapla_risk_parametreleri(fiyat, sinyal, mod="NORMAL"):
    """
    Fiyata göre Stop-Loss ve Take-Profit seviyelerini hesaplar.
    Mod bilgisine göre risk seviyesini ayarlar.
    """
    # --- STANDART ORANLAR (NORMAL MOD) ---
    # %2 Zarar Durdur, %4 Kar Al (1:2 Risk-Ödül Oranı)
    sl_oran = 0.02
    tp_oran = 0.04

    # --- AGRESİF ORANLAR (KAMIKAZE MODU) ---
    # Zararı hemen kes (%1.5), karı sonuna kadar koştur (%10)
    if mod == "KAMIKAZE":
        sl_oran = 0.015 
        tp_oran = 0.10  

    sl = 0
    tp = 0

    # Sinyale göre yön tayini
    if "BUY" in sinyal.upper():
        sl = fiyat * (1 - sl_oran)
        tp = fiyat * (1 + tp_oran)
    elif "SELL" in sinyal.upper():
        sl = fiyat * (1 + sl_oran)
        tp = fiyat * (1 - tp_oran)
    else:
        # Sinyal belirsizse (WAIT/HOLD) seviyeleri sıfır dön
        return 0, 0

    return round(sl, 2), round(tp, 2)

def kasa_yonetimi(bakiye, risk_yuzdesi=0.05):
    """Her işlemde kasanın ne kadarının riske atılacağını hesaplar."""
    return bakiye * risk_yuzdesi

def atr_hesapla(df, periyot=14):
    """
    Geçmiş mum verilerinden piyasanın volatilitesini (hareketliliğini) hesaplar.
    """
    high = df['high']
    low = df['low']
    close = df['close']
    
    # TR (True Range) hesaplaması için 3 farklı formülün maksimumu alınır
    df['tr0'] = abs(high - low)
    df['tr1'] = abs(high - close.shift())
    df['tr2'] = abs(low - close.shift())
    
    tr = df[['tr0', 'tr1', 'tr2']].max(axis=1)
    
    # ATR hesaplaması (TR'nin hareketli ortalaması)
    atr = tr.rolling(window=periyot).mean()
    return atr.iloc[-1]

def piyasa_olumu_yasiyor_mu(df, mevcut_fiyat, min_hareket_yuzdesi=0.25):
    """
    ATR değerini mevcut fiyata oranlayarak piyasanın yeterince 
    hareketli olup olmadığını kontrol eder.
    """
    try:
        atr_degeri = atr_hesapla(df)
        
        # ATR'nin mevcut fiyata yüzde olarak oranı
        volatilite_yuzdesi = (atr_degeri / mevcut_fiyat) * 100
        
        print(f"🔍 [Risk Analizi] Anlık Piyasa Volatilitesi (ATR): %{volatilite_yuzdesi:.3f}")
        
        # Eğer piyasadaki hareket bizim minimum eşiğimizden düşükse True (Ölü) döner
        if volatilite_yuzdesi < min_hareket_yuzdesi:
            print("⚠️ [Risk] Piyasa çok yatay (Hacimsiz). İşlem riskli, analiz iptal ediliyor!")
            return True 
        
        return False 
        
    except Exception as e:
        print(f"⚠️ ATR Hesaplama Hatası: {e}")
        return False # Hata olursa varsayılan olarak analize devam etsin