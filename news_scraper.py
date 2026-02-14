# dosya: news_scraper.py
import requests
from bs4 import BeautifulSoup

# --- KRİTİK ETKİ ANAHTARLARI ---
CRITICAL_KEYWORDS = ["hack", "sec", "fed", "ban", "listing", "elon", "musk", "etf", "binance", "cz"]

def haberleri_getir(coin_adi="Bitcoin"):
    print(f"🌐 {coin_adi} için küresel haber radarı çalıştırılıyor...")
    arama_terimi = coin_adi.split('/')[0]
    url = f"https://www.google.com/search?q={arama_terimi}+crypto+news&tbm=nws"
    
    # Gerçek bir tarayıcı gibi davranması için User-Agent
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"}

    try:
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        basliklar = []
        for g in soup.find_all(['div', 'span'], class_=['BNeawe', 'n0vP9d', 'vvjwNb']):
            text = g.get_text()
            if len(text) > 15: 
                basliklar.append(text)
        
        if not basliklar:
            return "Stable market. No significant headlines found.", 0

        # ETKİ PUANI HESAPLAMA
        etki_puani = 0
        birlesik_metin = " ".join(basliklar).lower()
        for word in CRITICAL_KEYWORDS:
            if word in birlesik_metin:
                etki_puani += 20 
        
        etki_puani = min(etki_puani, 100)
        
        return ". ".join(basliklar[:5]), etki_puani

    except Exception as e:
        print(f"❌ Haber çekme hatası: {e}")
        return "Connection issues. Sentiment is neutral.", 0