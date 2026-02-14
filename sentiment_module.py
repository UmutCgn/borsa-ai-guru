from textblob import TextBlob
import news_scraper

def haber_analizi_yap(coin_sembol):
    """
    Haberleri çeker, duygu analizi yapar ve 'Piyasa Baskınlığı' skorunu belirler.
    """
    try:
        # 1. Haberleri ve Ham Etki Puanını Getir
        haber_metni, ham_etki = news_scraper.haberleri_getir(coin_sembol)
        analiz_metni = haber_metni.lower()

        # 2. Kelime Bazlı Duygu Puanlaması
        pozitif_kelimeler = ['bullish', 'pump', 'surge', 'growth', 'gain', 'support', 'etf', 'buy', 'high', 'breakout']
        negatif_kelimeler = ['bearish', 'dump', 'crash', 'drop', 'fall', 'resistance', 'sec', 'sell', 'low', 'lawsuit']

        kelime_skoru = 0
        for p in pozitif_kelimeler: kelime_skoru += analiz_metni.count(p) * 3
        for n in negatif_kelimeler: kelime_skoru -= analiz_metni.count(n) * 3

        # 3. TextBlob NLP Analizi
        blob = TextBlob(analiz_metni)
        blob_skor = blob.sentiment.polarity * 15 # Ağırlığı artırıldı

        # 4. Final Sentiment Skoru (0-100)
        final_puan = 50 + kelime_skoru + blob_skor
        final_puan = max(0, min(100, final_puan))

        # 5. DURUM VE BASKINLIK (Dominance)
        # Eğer etki_puani > 80 ise bu haber piyasayı TEKNİK ANALİZDEN daha çok etkiler.
        durum = "NEUTRAL"
        if final_puan > 65: durum = "POSITIVE"
        elif final_puan < 35: durum = "NEGATIVE"

        print(f"🌍 Sentiment: {durum} ({final_puan}) | Baskınlık Etkisi: %{ham_etki}")
        
        return durum, round(final_puan, 2), ham_etki

    except Exception as e:
        print(f"⚠️ Sentiment hatası: {e}")
        return "NEUTRAL", 50.0, 0