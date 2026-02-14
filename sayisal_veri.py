# sayisal_veri.py
import ccxt

def verileri_cek(borsa_objesi, sembol):
    """
    AI'ın Sayısal Kolu (Numerical Branch) için Tahta ve Hacim verilerini hesaplar.
    """
    try:
        # 1. EMİR DEFTERİ (ORDER BOOK) DENGESİZLİĞİ
        # En yakın 20 alım ve satım emrini çekiyoruz (Derinlik)
        tahta = borsa_objesi.fetch_order_book(sembol, limit=20)
        
        # Alıcıların ve satıcıların toplam USD baskısı (Fiyat * Miktar)
        alici_baskisi = sum([fiyat * miktar for fiyat, miktar in tahta['bids']])
        satici_baskisi = sum([fiyat * miktar for fiyat, miktar in tahta['asks']])
        
        # Dengesizlik Oranı: 
        # > 1 ise alıcılar baskın (Örn: 1.5 ise alıcılar %50 daha fazla)
        # < 1 ise satıcılar baskın
        dengesizlik = alici_baskisi / satici_baskisi if satici_baskisi > 0 else 1.0

        # 2. HACİM DELTASI (VOLUME DELTA)
        # Piyasada anlık gerçekleşen son 100 işlemi çekiyoruz
        islemler = borsa_objesi.fetch_trades(sembol, limit=100)
        
        alim_hacmi = sum([islem['amount'] * islem['price'] for islem in islemler if islem['side'] == 'buy'])
        satim_hacmi = sum([islem['amount'] * islem['price'] for islem in islemler if islem['side'] == 'sell'])
        
        # Hacim Deltası: Pozitifse piyasaya para giriyor, negatifse çıkıyor
        hacim_deltasi = alim_hacmi - satim_hacmi 

        print(f"📊 [Sayısal Kol] Tahta Gücü: {dengesizlik:.2f} | Hacim Deltası: {hacim_deltasi:.0f} USD")
        
        # AI'a göndermek üzere vektör (liste) olarak dönüyoruz
        return [dengesizlik, hacim_deltasi]
        
    except Exception as e:
        print(f"⚠️ Sayısal Veri Çekme Hatası: {e}")
        # Hata olursa AI'ın kafası karışmasın diye "Nötr" değerler (1.0 ve 0.0) dönüyoruz
        return [1.0, 0.0]