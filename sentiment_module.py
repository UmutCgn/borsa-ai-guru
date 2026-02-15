from textblob import TextBlob
import news_scraper
import nltk

# NLTK verilerini ilk açılışta kontrol et (Hata almamak için)
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt')

def haber_analizi_yap(coin_sembol):
    """
    Haberleri çeker, duygu analizi yapar ve 'Piyasa Baskınlığı' skorunu belirler.
    """
    try:
        # 1. Haberleri Çek (Hata durumunda boş dönmemesi için önlem)
        try:
            haber_metni, ham_etki = news_scraper.haberleri_getir(coin_sembol)
        except Exception as e:
            print(f"⚠️ Scraper Hatası: {e}")
            haber_metni, ham_etki = "", 0

        if not haber_metni or len(haber_metni) < 10:
            print(f"🌍 {coin_sembol} için güncel haber bulunamadı. Nötr geçiliyor.")
            return "NEUTRAL", 50.0, 0

        analiz_metni = haber_metni.lower()

        # 2. Kelime Bazlı Duygu Puanlaması (Sözlüğü genişlettik)
        pozitif_kelimeler = ['bullish', 'pump', 'surge', 'growth', 'gain', 'support', 'etf', 'buy', 'high', 'breakout', 'listing', 'partnership']
        negatif_kelimeler = ['bearish', 'dump', 'crash', 'drop', 'fall', 'resistance', 'sec', 'sell', 'low', 'lawsuit', 'hack', 'scam', 'delisting']

        kelime_skoru = 0
        for p in pozitif_kelimeler: 
            kelime_skoru += analiz_metni.count(p) * 4 # Ağırlık artırıldı
        for n in negatif_kelimeler: 
            kelime_skoru -= analiz_metni.count(n) * 4

        # 3. TextBlob NLP Analizi
        blob = TextBlob(analiz_metni)
        # Polarity -1 (negatif) ile +1 (pozitif) arasındadır.
        blob_skor = blob.sentiment.polarity * 25 

        # 4. Final Sentiment Skoru (0-100)
        final_puan = 50 + kelime_skoru + blob_skor
        final_puan = max(0, min(100, final_puan))

        # 5. Durum Belirleme
        durum = "NEUTRAL"
        if final_puan > 60: durum = "POSITIVE"
        elif final_puan < 40: durum = "NEGATIVE"

        print(f"🌍 Sentiment: {durum} ({final_puan:.2f}) | Baskınlık Etkisi: %{ham_etki}")
        return durum, round(final_puan, 2), ham_etki

    except Exception as e:
        print(f"⚠️ Sentiment modülünde kritik hata: {e}")
        return "NEUTRAL", 50.0, 0